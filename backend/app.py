import asyncio
import json
import logging
import os
import sys
import contextlib
from datetime import datetime, timezone
from typing import Dict, Any, Set, Optional

import httpx

try:
    import redis.asyncio as redis
except Exception as e:
    raise RuntimeError(
        "Missing dependency 'redis'. "
        "Please install backend/requirements.txt: "
        "pip install -r backend/requirements.txt"
    ) from e
from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    Depends,
    HTTPException,
    Body,
)
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import REDIS_URL, POLL_INTERVAL, SYMBOLS
from backend.database import AsyncSessionLocal, init_db
from backend.models.price_model import Price
from backend.services.services import fetch_coingecko_price, fetch_cusd_price

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("backend.app")

app = FastAPI(title="Crypto Dashboard (Realtime)")

# CORS for frontend during development
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # narrow this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis client (initialized only in live mode)
redis_client = None

# simple in-memory set of connected websockets
connected_websockets: Set[WebSocket] = set()


# dependency for getting DB session
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


# Normalize various symbol inputs to canonical coin ids used in the app (e.g. BTC -> bitcoin)
def normalize_symbol(symbol: str) -> str:
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol is required")
    key = symbol.strip().lower()
    # Build alias map from SYMBOLS
    alias_map = {}
    for s in SYMBOLS:
        alias_map[s] = s
    # common abbreviations
    if "bitcoin" in SYMBOLS:
        alias_map["btc"] = "bitcoin"
    if "ethereum" in SYMBOLS:
        alias_map["eth"] = "ethereum"
    if "cusd" in SYMBOLS:
        alias_map["cusd"] = "cusd"

    if key in alias_map:
        return alias_map[key]
    raise HTTPException(
        status_code=400,
        detail=f"Unsupported symbol '{symbol}'. Supported: {', '.join(SYMBOLS)}",
    )


def _prompt_yes_no(prompt: str, default: bool) -> bool:
    try:
        if not sys.stdin or not sys.stdin.isatty():
            return default
        val = input(prompt).strip().lower()
        if val in ("y", "yes"):
            return True
        if val in ("n", "no"):
            return False
        return default
    except Exception:
        return default


def _prompt_int(prompt: str, default_value: int) -> int:
    try:
        if not sys.stdin or not sys.stdin.isatty():
            return default_value
        val = input(prompt).strip()
        return int(val) if val else default_value
    except Exception:
        return default_value


def _load_runtime_config():
    env_live = os.getenv("LIVE_MODE")
    env_interval = os.getenv("FETCH_INTERVAL")
    env_retention = os.getenv("CACHE_RETENTION")

    live_default = False
    interval_default = 30
    retention_default = 300

    live_mode = (
        env_live.lower() in ("1", "true", "yes", "y")
        if env_live is not None
        else live_default
    )
    try:
        fetch_interval = int(env_interval) if env_interval else interval_default
    except Exception:
        fetch_interval = interval_default
    try:
        cache_retention = int(env_retention) if env_retention else retention_default
    except Exception:
        cache_retention = retention_default

    if env_live is None and sys.stdin and sys.stdin.isatty():
        live_mode = _prompt_yes_no(
            f"Enable live fetching? (y/n) [default {'y' if live_default else 'n'}]: ",
            live_default,
        )
        if live_mode:
            fetch_interval = _prompt_int(
                f"Fetch interval seconds [default {interval_default}]: ",
                interval_default,
            )
            cache_retention = _prompt_int(
                f"Cache retention seconds [default {retention_default}]: ",
                retention_default,
            )

    return live_mode, fetch_interval, cache_retention


@app.on_event("startup")
async def startup_event():
    logger.info("Starting up application")
    # runtime config (live/static, interval, retention)
    live_mode, fetch_interval, cache_retention = _load_runtime_config()
    app.state.live_mode = live_mode
    app.state.poll_interval = float(fetch_interval or POLL_INTERVAL)
    app.state.cache_retention = int(cache_retention)
    app.state.backoff_multiplier = 1.0
    logger.info(
        f"Runtime config: live_mode={app.state.live_mode}, interval={app.state.poll_interval}s, retention={app.state.cache_retention}s"
    )
    # create tables
    await init_db()
    # initialize Redis and poller only in live mode
    global redis_client
    if app.state.live_mode:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        for symbol in SYMBOLS:
            await redis_client.hset(
                "latest_prices", symbol, json.dumps({"price": None, "timestamp": None})
            )
        app.state.poller_task = asyncio.create_task(price_poller())
        logger.info("Startup complete: DB initialized, Redis primed, poller started")
    else:
        redis_client = None
        app.state.poller_task = None
        logger.info("Startup complete: Static mode (no Redis, no poller)")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down application")
    task = app.state.poller_task
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    if redis_client is not None:
        await redis_client.close()
    logger.info("Shutdown complete")


# REST: health
@app.get("/health")
async def health():
    logger.debug("Health check requested")
    return {"status": "ok"}


# REST: latest price
@app.get("/prices/{symbol}/latest")
async def latest_price(symbol: str):
    sym = normalize_symbol(symbol)
    logger.info(f"Latest price requested for {sym}")
    # live mode: read from Redis cache
    if getattr(app.state, "live_mode", True):
        if redis_client is None:
            raise HTTPException(status_code=503, detail="Cache unavailable")
        data = await redis_client.hget("latest_prices", sym)
        if not data or data == "null":
            logger.warning(f"Latest price not found in Redis for {sym}")
            raise HTTPException(status_code=404, detail="Price not found")
        payload = json.loads(data)
        # If cache exists but price is missing, treat as not found so frontend won't attempt to render null
        if payload is None or payload.get("price") is None:
            logger.warning(f"Latest price in Redis for {sym} has no value: {payload}")
            raise HTTPException(status_code=404, detail="Price not found")
        logger.debug(f"Latest price hit for {sym}: {payload}")
        return JSONResponse(content=payload)
    # static mode: fetch most recent from Postgres
    async with AsyncSessionLocal() as db:
        q = select(Price).where(Price.symbol == sym).order_by(Price.timestamp.desc())
        res = await db.execute(q)
        row = res.scalars().first()
        if not row:
            logger.warning(f"No price rows in Postgres for {sym}")
            raise HTTPException(status_code=404, detail="Price not found")
        payload = {
            "symbol": row.symbol,
            "price": row.price,
            "timestamp": row.timestamp.isoformat(),
            "id": row.id,
        }
        logger.debug(f"Latest price from Postgres for {sym}: {payload}")
        return JSONResponse(content=payload)


# REST: historical from Postgres
from fastapi import Query


@app.get("/prices/{symbol}")
async def historical_prices(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    sym = normalize_symbol(symbol)
    return await _historical_prices_impl(db, sym, limit=limit, offset=offset)


async def _historical_prices_impl(
    db: AsyncSession, sym: str, limit: int = 100, offset: int = 0
):
    # sanitize pagination
    lim = min(max(1, int(limit)), 1000)
    off = max(0, int(offset))
    logger.info(f"Historical prices requested for {sym}")
    # total count
    total_res = await db.execute(
        select(func.count()).select_from(Price).where(Price.symbol == sym)
    )
    total_count = int(total_res.scalar() or 0)
    # page
    q = (
        select(Price)
        .where(Price.symbol == sym)
        .order_by(Price.timestamp.asc())
        .offset(off)
        .limit(lim)
    )
    res = await db.execute(q)
    rows = res.scalars().all()
    out = [
        {
            "symbol": r.symbol,
            "price": r.price,
            "timestamp": r.timestamp.isoformat(),
            "id": r.id,
        }
        for r in rows
    ]
    logger.debug(
        f"Historical rows returned for {sym}: {len(out)} (offset={off}, limit={lim}, total={total_count})"
    )
    # Return a plain list as the frontend expects an array of items
    return out


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


# REST: on-demand fetch and persist latest price (used in static mode)
@app.post("/prices/{symbol}/fetch")
async def fetch_price_now(symbol: str):
    sym = normalize_symbol(symbol)
    logger.info(f"On-demand fetch requested for {sym}")
    value = None
    async with httpx.AsyncClient() as client:
        if sym in ("bitcoin", "ethereum"):
            value = await _retry_coingecko(client, sym)
        elif sym == "cusd":
            value = await _retry_cusd()

    if value is None:
        raise HTTPException(status_code=502, detail="Failed to fetch price")

    timestamp = datetime.now(tz=timezone.utc)
    async with AsyncSessionLocal() as db:
        try:
            p = Price(symbol=sym, price=float(value))
            db.add(p)
            await db.commit()
            await db.refresh(p)
            logger.info(f"On-demand DB insert for {sym}: {value}")
        except Exception:
            await db.rollback()
            logger.exception("On-demand DB write failed")
            raise HTTPException(status_code=500, detail="DB write failed")

    # If live mode, optionally update Redis and broadcast immediately
    if getattr(app.state, "live_mode", True) and redis_client is not None:
        try:
            obj = {"symbol": sym, "price": value, "timestamp": timestamp.isoformat()}
            await redis_client.hset("latest_prices", sym, json.dumps(obj))
            ttl = int(getattr(app.state, "cache_retention", 300))
            await redis_client.expire("latest_prices", ttl)
            await broadcast_message(obj)
            logger.debug(f"On-demand cache/broadcast updated for {sym}")
        except Exception:
            logger.exception("On-demand Redis/broadcast failed")

    return {"symbol": sym, "price": value, "timestamp": timestamp.isoformat()}


# Websocket endpoint: clients connect to receive live price updates
@app.websocket("/ws/prices")
async def ws_prices(ws: WebSocket):
    await ws.accept()
    connected_websockets.add(ws)
    logger.info(f"WebSocket client connected. Total={len(connected_websockets)}")
    try:
        while True:
            # Send keepalive ping every 30s
            await ws.send_text(
                json.dumps(
                    {
                        "type": "ping",
                        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                    }
                )
            )
            await asyncio.sleep(30)
    except WebSocketDisconnect:
        connected_websockets.discard(ws)
        logger.info(f"WebSocket client disconnected. Total={len(connected_websockets)}")


# Internal helper: broadcast to connected websockets
async def broadcast_message(message: Dict[str, Any]):
    if not connected_websockets:
        return
    payload = json.dumps(message)
    to_remove = []
    for ws in list(connected_websockets):
        try:
            await ws.send_text(payload)
        except Exception:
            to_remove.append(ws)
    for ws in to_remove:
        connected_websockets.discard(ws)
    logger.debug(f"Broadcasted update: {message['symbol']} -> {message['price']}")


@app.get("/mode")
async def get_mode():
    return {
        "live_mode": bool(getattr(app.state, "live_mode", False)),
        "poll_interval": float(getattr(app.state, "poll_interval", POLL_INTERVAL)),
        "cache_retention": int(getattr(app.state, "cache_retention", 300)),
    }


class ModeUpdate(BaseModel):
    live: bool = True


@app.post("/mode")
async def set_mode(payload: ModeUpdate = Body(...)):
    global redis_client
    desired = bool(payload.live)
    current = bool(getattr(app.state, "live_mode", False))
    logger.info(f"Mode toggle requested: {current} -> {desired}")
    if desired == current:
        return {"live_mode": current}

    # Stop existing poller if any
    if getattr(app.state, "poller_task", None):
        t = app.state.poller_task
        t.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await t
        app.state.poller_task = None

    if desired:
        # starting live mode: init redis and poller
        if redis_client is None:
            redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        for symbol in SYMBOLS:
            await redis_client.hset(
                "latest_prices", symbol, json.dumps({"price": None, "timestamp": None})
            )
        app.state.live_mode = True
        app.state.backoff_multiplier = 1.0
        app.state.poller_task = asyncio.create_task(price_poller())
        logger.info("Live mode enabled: poller started")
    else:
        # switching to static: close redis
        if redis_client is not None:
            try:
                await redis_client.close()
            except Exception:
                pass
        redis_client = None
        app.state.live_mode = False
        logger.info("Static mode enabled: poller stopped, redis closed")

    return {"live_mode": app.state.live_mode}


# Background poller
async def price_poller():
    """
    Poll prices every POLL_INTERVAL seconds and:
    - write row to Postgres
    - update Redis latest cache (hash 'latest_prices')
    - broadcast to connected websockets
    """
    if not getattr(app.state, "live_mode", True):
        logger.info("Price poller invoked but live_mode is disabled; exiting poller")
        return
    logger.info("Price poller started")
    async with httpx.AsyncClient() as client:
        while True:
            start = asyncio.get_event_loop().time()
            results = {}
            for coin in ["bitcoin", "ethereum"]:
                price = await _retry_coingecko(client, coin)
                if price is not None:
                    results[coin] = price
                    logger.info(f"Fetched {coin} price: {price}")
                else:
                    logger.warning(f"Failed to fetch {coin} price from CoinGecko")
            cusd_price = await _retry_cusd()
            if cusd_price is not None:
                results["cusd"] = cusd_price
                logger.info(f"Fetched cusd price: {cusd_price}")
            else:
                logger.warning("Failed to fetch cUSD price from blockchain")

            if not results:
                logger.warning("No prices fetched in this poller cycle (results empty)")

            timestamp = datetime.now(tz=timezone.utc).isoformat()

            # write-through: update Redis first, then persist to DB
            try:
                pipe = redis_client.pipeline()
                for sym, pr in results.items():
                    obj = {"symbol": sym, "price": pr, "timestamp": timestamp}
                    pipe.hset("latest_prices", sym, json.dumps(obj))
                await pipe.execute()
                ttl = int(getattr(app.state, "cache_retention", 300))
                await redis_client.expire("latest_prices", ttl)
                for sym, pr in results.items():
                    await broadcast_message(
                        {"symbol": sym, "price": pr, "timestamp": timestamp}
                    )
                logger.info(
                    f"Redis updated and broadcasted {len(results)} symbols (write-through)"
                )
            except Exception:
                logger.exception("Redis write-through failed")

            async with AsyncSessionLocal() as db:
                try:
                    for sym, pr in results.items():
                        db.add(Price(symbol=sym, price=float(pr)))
                    await db.commit()
                    logger.info(f"DB commit: inserted {len(results)} rows")
                except Exception:
                    await db.rollback()
                    logger.exception("DB write failed")

            elapsed = asyncio.get_event_loop().time() - start
            base_interval = float(getattr(app.state, "poll_interval", POLL_INTERVAL))
            fetched_core = sum(1 for s in ("bitcoin", "ethereum") if s in results)
            if fetched_core == 0:
                app.state.backoff_multiplier = min(
                    4.0, getattr(app.state, "backoff_multiplier", 1.0) * 2.0
                )
            else:
                app.state.backoff_multiplier = max(
                    1.0, getattr(app.state, "backoff_multiplier", 1.0) * 0.5
                )
            wait = max(0, base_interval * app.state.backoff_multiplier - elapsed)
            logger.debug(
                f"Poller cycle took {elapsed:.3f}s; sleeping {wait:.3f}s (multiplier={app.state.backoff_multiplier:.2f})"
            )
            await asyncio.sleep(wait)


# --- Retry helpers for external calls ---
async def _retry_coingecko(client: httpx.AsyncClient, coin: str) -> Optional[float]:
    attempt = 0
    while attempt < 3:
        if attempt > 0:
            logger.debug(f"Retrying CoinGecko for {coin}, attempt {attempt}")
        val = await fetch_coingecko_price(client, coin)
        if val is not None:
            return val
        attempt += 1
        await asyncio.sleep(2 ** (attempt - 1))
    logger.error(f"CoinGecko failed after retries for {coin}")
    return None


async def _retry_cusd() -> Optional[float]:
    attempt = 0
    while attempt < 3:
        if attempt > 0:
            logger.debug(f"Retrying cUSD blockchain fetch, attempt {attempt}")
        val = await fetch_cusd_price()
        if val is not None:
            return val
        attempt += 1
        await asyncio.sleep(2 ** (attempt - 1))
    logger.error("cUSD blockchain fetch failed after retries")
    return None
