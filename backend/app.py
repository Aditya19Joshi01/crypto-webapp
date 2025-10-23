from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx
import json
import asyncio
import logging
from datetime import datetime, timezone
from typing import List

from starlette.middleware.cors import CORSMiddleware

from backend.services.price_service import price_service
from backend.database import AsyncSessionLocal, init_db
from backend.models.price_model import Price

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Modular Crypto Dashboard")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


@app.on_event("startup")
async def startup_event():
    logger.info("Starting up...")
    await init_db()

    # Start price poller
    app.state.poller_task = asyncio.create_task(price_poller())
    logger.info("Startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down...")
    if hasattr(app.state, "poller_task"):
        app.state.poller_task.cancel()
        try:
            await app.state.poller_task
        except asyncio.CancelledError:
            pass
    logger.info("Shutdown complete")


# ============================================
# ENDPOINTS - Clean and Simple!
# ============================================

@app.get("/")
async def root():
    """Welcome endpoint"""
    return {
        "message": "Crypto Price Dashboard API",
        "endpoints": {
            "coins": "/coins",
            "latest_price": "/prices/{symbol}/latest",
            "historical": "/prices/{symbol}",
            "fetch_now": "/prices/{symbol}/fetch"
        }
    }


@app.get("/coins")
async def list_coins():
    """
    Get list of all supported cryptocurrencies.
    Automatically includes ALL registered providers!
    """
    coins = []
    for provider in price_service.get_all_providers():
        coins.append({
            "symbol": provider.symbol,
            "name": provider.get_display_name(),
            "provider": provider.get_provider_name()
        })
    return {"coins": coins, "count": len(coins)}


@app.get("/prices/{symbol}/latest")
async def get_latest_price(symbol: str, db: AsyncSession = Depends(get_db)):
    """
    Get latest price for any supported cryptocurrency.
    Reads from database (most recent entry).
    """
    # Validate symbol
    if not price_service.get_provider(symbol):
        supported = ", ".join(price_service.get_all_symbols())
        raise HTTPException(
            status_code=404,
            detail=f"Symbol '{symbol}' not found. Supported: {supported}"
        )

    # Get most recent price from database
    stmt = select(Price).where(Price.symbol == symbol).order_by(Price.timestamp.desc()).limit(1)
    result = await db.execute(stmt)
    price_record = result.scalar_one_or_none()

    if not price_record:
        raise HTTPException(
            status_code=404,
            detail=f"No price data found for {symbol}"
        )

    provider = price_service.get_provider(symbol)
    return {
        "symbol": price_record.symbol,
        "name": provider.get_display_name(),
        "price": price_record.price,
        "timestamp": price_record.timestamp.isoformat(),
        "provider": provider.get_provider_name()
    }


@app.get("/prices/{symbol}")
async def get_historical_prices(
        symbol: str,
        limit: int = 100,
        db: AsyncSession = Depends(get_db)
):
    """
    Get historical prices for any supported cryptocurrency.
    """
    # Validate symbol
    if not price_service.get_provider(symbol):
        supported = ", ".join(price_service.get_all_symbols())
        raise HTTPException(
            status_code=404,
            detail=f"Symbol '{symbol}' not found. Supported: {supported}"
        )

    # Get historical prices
    stmt = (
        select(Price)
        .where(Price.symbol == symbol)
        .order_by(Price.timestamp.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    prices = result.scalars().all()

    return {
        "symbol": symbol,
        "count": len(prices),
        "prices": [
            {
                "price": p.price,
                "timestamp": p.timestamp.isoformat()
            }
            for p in prices
        ]
    }


@app.post("/prices/{symbol}/fetch")
async def fetch_price_now(symbol: str, db: AsyncSession = Depends(get_db)):
    """
    Manually fetch and store current price for any supported cryptocurrency.
    """
    # Fetch price using PriceService
    async with httpx.AsyncClient() as client:
        price = await price_service.fetch_price(symbol, client)

    if price is None:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch price for {symbol}"
        )

    # Store in database
    timestamp = datetime.now(tz=timezone.utc)
    db_price = Price(symbol=symbol, price=float(price))
    db.add(db_price)
    await db.commit()
    await db.refresh(db_price)

    provider = price_service.get_provider(symbol)
    return {
        "symbol": symbol,
        "name": provider.get_display_name(),
        "price": price,
        "timestamp": timestamp.isoformat(),
        "provider": provider.get_provider_name(),
        "message": "Price fetched and stored successfully"
    }


# ============================================
# BACKGROUND PRICE POLLER - Super Clean!
# ============================================

async def price_poller():
    """
    Fetch prices for ALL registered cryptocurrencies periodically.
    No hardcoded lists! Automatically fetches everything in PriceService.
    """
    logger.info("Price poller started")

    async with httpx.AsyncClient() as client:
        while True:
            try:
                start_time = asyncio.get_event_loop().time()

                # Fetch ALL prices concurrently (one line!)
                results = await price_service.fetch_all_prices(client)

                # Filter successful fetches
                successful = {
                    sym: price
                    for sym, price in results.items()
                    if price is not None
                }

                if successful:
                    # Store in database
                    async with AsyncSessionLocal() as db:
                        try:
                            for symbol, price in successful.items():
                                db.add(Price(symbol=symbol, price=float(price)))
                            await db.commit()
                            logger.info(f"Stored {len(successful)} prices in database")
                        except Exception as e:
                            await db.rollback()
                            logger.error(f"Database error: {e}")
                else:
                    logger.warning("No prices fetched in this cycle")

                # Sleep until next cycle
                elapsed = asyncio.get_event_loop().time() - start_time
                sleep_time = max(0, 30 - elapsed)  # Poll every 30 seconds
                logger.debug(f"Cycle took {elapsed:.2f}s, sleeping {sleep_time:.2f}s")
                await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                logger.info("Price poller cancelled")
                break
            except Exception as e:
                logger.error(f"Poller error: {e}", exc_info=True)
                await asyncio.sleep(5)  # Wait before retry