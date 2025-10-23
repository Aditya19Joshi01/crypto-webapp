from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx
import json
import asyncio
import logging
from datetime import datetime, timezone

from starlette.middleware.cors import CORSMiddleware

from backend.services.price_service import price_service
from backend.database import AsyncSessionLocal, init_db
from backend.models.price_model import Price

# Add missing imports and configuration
from fastapi import Body
import contextlib
import redis.asyncio as redis
from backend.config import REDIS_URL, POLL_INTERVAL, SYMBOLS
from typing import Any, cast, Optional
from backend.services.coingecko_provider import CoinGeckoProvider
from backend.services.celo_provider import CeloStablecoinProvider
from backend.services.binance_provider import BinanceProvider
from pydantic import BaseModel, Field

app = FastAPI(title="Modular Crypto Dashboard")

# Expose a typed-any alias for app.state to avoid static analysis warnings
app_state = cast(Any, getattr(app, "state"))

# Module-level redis client (initialized when live mode is enabled)
# Annotate with Optional to aid static analysis
redis_client: Optional[redis.Redis] = None

# Only configure basic logging if no handlers have been configured already. This
# prevents double-printing when the application is run under servers (uvicorn)
# that configure logging themselves.
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO)
else:
    # Ensure root logger level is set to INFO without adding handlers
    logging.getLogger().setLevel(logging.INFO)

logger = logging.getLogger(__name__)

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

    # Initialize app state defaults to avoid attribute errors and provide observability
    app_state.live_mode = True
    app_state.poll_interval = float(getattr(app_state, "poll_interval", POLL_INTERVAL))
    app_state.cache_retention = int(getattr(app_state, "cache_retention", 300))
    app_state.backoff_multiplier = float(getattr(app_state, "backoff_multiplier", 1.0))
    app_state.poller_task = None

    # Start price poller
    app_state.poller_task = asyncio.create_task(price_poller())
    logger.info("Startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down...")
    if getattr(app_state, "poller_task", None):
        app_state.poller_task.cancel()
        try:
            await app_state.poller_task
        except asyncio.CancelledError:
            pass
    # close redis if open
    global redis_client
    if redis_client is not None:
        try:
            await redis_client.close()
        except Exception:
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
            "fetch_now": "/prices/{symbol}/fetch",
            "tvl": "/tvl/{protocol}",
            "mode": "/mode",
            "health": "/health"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "timestamp": datetime.now(tz=timezone.utc).isoformat()}


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
    # build SQLAlchemy condition as Any to avoid static type checker errors
    from typing import Any
    cond: Any = Price.symbol == symbol
    stmt = select(Price).where(cond).order_by(Price.timestamp.desc()).limit(1)
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
    # build condition as Any to satisfy static analyser
    from typing import Any
    cond: Any = Price.symbol == symbol
    stmt = (
        select(Price)
        .where(cond)
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
    Writes latest prices to Redis (if configured) and stores history in DB.
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
                                # persist history
                                db.add(Price(symbol=symbol, price=float(price)))
                                # update redis latest cache when available
                                if redis_client is not None:
                                    try:
                                        await redis_client.hset(
                                            "latest_prices",
                                            symbol,
                                            json.dumps({
                                                "price": float(price),
                                                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                                            }),
                                        )
                                    except Exception as e:
                                        logger.debug(f"Failed to update redis for {symbol}: {e}")
                            await db.commit()
                            logger.info(f"Stored {len(successful)} prices in database")
                        except Exception as e:
                            await db.rollback()
                            logger.error(f"Database error: {e}")
                else:
                    logger.warning("No prices fetched in this cycle")

                # Sleep until next cycle (respects configured poll interval and backoff)
                elapsed = asyncio.get_event_loop().time() - start_time
                poll_interval = float(getattr(app_state, "poll_interval", POLL_INTERVAL))
                backoff = float(getattr(app_state, "backoff_multiplier", 1.0))
                sleep_time = max(0.0, poll_interval * backoff - elapsed)
                logger.debug(f"Cycle took {elapsed:.2f}s, sleeping {sleep_time:.2f}s")
                await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                logger.info("Price poller cancelled")
                break
            except Exception as e:
                logger.error(f"Poller error: {e}", exc_info=True)
                await asyncio.sleep(2)


# REST: TVL
@app.get("/tvl/{protocol}")
async def tvl(protocol: str):
    logger.info(f"TVL requested for protocol={protocol}")
    # Custom retry with status handling
    url = f"https://api.llama.fi/tvl/{protocol}"
    attempt = 0
    last_exc = None
    async with httpx.AsyncClient() as client:
        while attempt < 3:
            try:
                if attempt > 0:
                    logger.debug(f"TVL retry attempt {attempt} for {protocol}")
                resp = await client.get(url, timeout=10.0)
                if resp.status_code == 404:
                    logger.error(f"TVL protocol not found: {protocol}")
                    raise HTTPException(status_code=404, detail="Protocol not found")
                resp.raise_for_status()
                # Try to parse JSON first
                try:
                    data = resp.json()
                except Exception:
                    # Not JSON — try to parse as a float/scalar from text
                    text = resp.text.strip()
                    try:
                        val = float(text)
                        logger.debug(
                            f"TVL scalar response parsed as float for {protocol}: {val}"
                        )
                        return {"tvl": val}
                    except Exception:
                        # fallback: return raw string under 'tvl_raw'
                        logger.debug(
                            f"TVL non-JSON/non-numeric response for {protocol}: {text}"
                        )
                        return {"tvl_raw": text}

                # If JSON parsed successfully, normalize into an object the frontend can consume
                if isinstance(data, (int, float)):
                    return {"tvl": float(data)}
                if isinstance(data, str):
                    # try numeric
                    try:
                        return {"tvl": float(data)}
                    except Exception:
                        return {"tvl_raw": data}
                if isinstance(data, list):
                    # Some endpoints may return arrays — wrap them
                    return {"items": data}
                if isinstance(data, dict):
                    # Common DeFiLlama structure may already be a dict with useful fields
                    # Ensure there is a numeric 'tvl' field if present; otherwise wrap entire dict
                    if "tvl" in data:
                        # make sure tvl is numeric when possible
                        try:
                            data["tvl"] = (
                                float(data["tvl"]) if data["tvl"] is not None else None
                            )
                        except Exception:
                            pass
                    return data
            except httpx.HTTPStatusError as e:
                last_exc = e
                attempt += 1
                if attempt >= 3:
                    logger.error(f"TVL fetch failed for {protocol}: {e}")
                    raise HTTPException(
                        status_code=502, detail="Upstream TVL service error"
                    )
                await asyncio.sleep(2 ** (attempt - 1))
            except Exception as e:
                last_exc = e
                attempt += 1
                if attempt >= 3:
                    logger.error(f"TVL fetch unreachable for {protocol}: {e}")
                    raise HTTPException(
                        status_code=502, detail="TVL service unreachable"
                    )
                await asyncio.sleep(2 ** (attempt - 1))


@app.get("/mode")
async def get_mode():
    return {
        "live_mode": bool(getattr(app_state, "live_mode", False)),
        "poll_interval": float(getattr(app_state, "poll_interval", POLL_INTERVAL)),
        "cache_retention": int(getattr(app_state, "cache_retention", 300)),
    }


class ModeUpdate(BaseModel):
    live: bool = True


@app.post("/mode")
async def set_mode(payload: ModeUpdate = Body(...)):
    global redis_client
    desired = bool(payload.live)
    current = bool(getattr(app_state, "live_mode", False))
    logger.info(f"Mode toggle requested: {current} -> {desired}")
    if desired == current:
        return {"live_mode": current}

    # Stop existing poller if any
    if getattr(app_state, "poller_task", None):
        t = app_state.poller_task
        t.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await t
        app_state.poller_task = None

    if desired:
        # starting live mode: init redis and poller
        if redis_client is None:
            redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        for symbol in SYMBOLS:
            await redis_client.hset(
                "latest_prices", symbol, json.dumps({"price": None, "timestamp": None})
            )
        app_state.live_mode = True
        app_state.backoff_multiplier = 1.0
        app_state.poller_task = asyncio.create_task(price_poller())
        logger.info("Live mode enabled: poller started")
    else:
        # switching to static: close redis
        if redis_client is not None:
            try:
                await redis_client.close()
            except Exception:
                pass
        redis_client = None
        app_state.live_mode = False
        logger.info("Static mode enabled: poller stopped, redis closed")

    return {"live_mode": app_state.live_mode}


class ProviderCreate(BaseModel):
    type: str = Field(..., description="Provider type: 'coingecko', 'celo', or 'binance'")
    symbol: str = Field(..., description="Unique backend symbol, e.g. 'solana'")
    display_name: Optional[str] = Field(None, description="Human readable name")
    # coinGecko specific
    coingecko_id: Optional[str] = None
    # celo specific
    token_address: Optional[str] = None
    # binance specific
    binance_symbol: Optional[str] = None


@app.get("/providers")
async def list_providers():
    """List registered providers (runtime)."""
    providers = []
    for p in price_service.get_all_providers():
        providers.append({
            "symbol": p.symbol,
            "name": p.get_display_name(),
            "provider": p.get_provider_name(),
        })
    return {"providers": providers, "count": len(providers)}


@app.post("/providers")
async def create_provider(payload: ProviderCreate):
    """Register a new provider at runtime. Not persisted across restarts."""
    symbol = payload.symbol
    if price_service.get_provider(symbol):
        raise HTTPException(status_code=400, detail=f"Symbol '{symbol}' already registered")

    typ = payload.type.lower().strip()
    display = payload.display_name or symbol

    if typ == "coingecko":
        if not payload.coingecko_id:
            raise HTTPException(status_code=400, detail="coingecko_id is required for coingecko provider")
        prov = CoinGeckoProvider(symbol=symbol, coingecko_id=payload.coingecko_id, display_name=display)
    elif typ == "celo":
        if not payload.token_address:
            raise HTTPException(status_code=400, detail="token_address is required for celo provider")
        prov = CeloStablecoinProvider(symbol=symbol, token_address=payload.token_address, display_name=display)
    elif typ == "binance":
        if not payload.binance_symbol:
            raise HTTPException(status_code=400, detail="binance_symbol is required for binance provider")
        prov = BinanceProvider(symbol=symbol, binance_symbol=payload.binance_symbol, display_name=display)
    else:
        raise HTTPException(status_code=400, detail="Unknown provider type")

    price_service.register_provider(prov)
    # Try to fetch an initial price immediately so frontend can show a value
    initial_price = None
    try:
        async with httpx.AsyncClient() as client:
            initial_price = await price_service.fetch_price(symbol, client)
    except Exception as e:
        logger.debug(f"Initial price fetch failed for {symbol}: {e}")

    if initial_price is not None:
        try:
            async with AsyncSessionLocal() as db:
                db.add(Price(symbol=symbol, price=float(initial_price)))
                await db.commit()
        except Exception as e:
            logger.debug(f"Failed to persist initial price for {symbol}: {e}")

    return {"message": "Provider registered", "symbol": prov.symbol, "name": prov.get_display_name(), "provider": prov.get_provider_name()}


# --- New config endpoint -------------------------------------------------
class ConfigUpdate(BaseModel):
    poll_interval: Optional[float] = None
    cache_retention: Optional[int] = None


@app.post("/config")
async def update_config(payload: ConfigUpdate = Body(...)):
    """Update runtime fetching configuration (poll interval, cache retention).

    Poll interval is clamped to a sensible minimum (1s) to avoid extremely
    tight polling that could hammer external APIs.
    """
    MIN_POLL = 1.0
    changed = {}
    if payload.poll_interval is not None:
        new_poll = float(payload.poll_interval)
        if new_poll < MIN_POLL:
            new_poll = MIN_POLL
        app_state.poll_interval = new_poll
        changed["poll_interval"] = app_state.poll_interval

    if payload.cache_retention is not None:
        app_state.cache_retention = int(payload.cache_retention)
        changed["cache_retention"] = app_state.cache_retention

    logger.info(f"Configuration updated: {changed}")
    return {"updated": changed}
