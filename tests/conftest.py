import asyncio
import types
import os
import sys
import pytest

# Ensure the project root (crypto-dashboard) is on sys.path so tests can import backend
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Ensure missing optional packages used at import time don't break tests
import types as _types

if "redis" not in sys.modules:
    fake_redis = _types.ModuleType("redis")
    fake_redis_asyncio = _types.ModuleType("redis.asyncio")
    # place both entries so `import redis.asyncio as redis` resolves
    sys.modules["redis"] = fake_redis
    sys.modules["redis.asyncio"] = fake_redis_asyncio

# Provide lightweight stubs for backend.database and model/service modules to avoid
# importing heavy dependencies (asyncpg, sqlalchemy) at test import time.
# Ensure the app runs in live mode for tests so code paths use Redis stubs
os.environ.setdefault("LIVE_MODE", "1")
if "backend.database" not in sys.modules:
    fake_db = _types.ModuleType("backend.database")

    async def _fake_init_db(*a, **k):
        return None

    class _FakeAsyncSessionLocal:
        def __call__(self, *a, **k):
            return AsyncSessionStub()

    fake_db.init_db = _fake_init_db
    fake_db.AsyncSessionLocal = _FakeAsyncSessionLocal()
    sys.modules["backend.database"] = fake_db

if "backend.models.price_model" not in sys.modules:
    fake_model = _types.ModuleType("backend.models.price_model")

    class Price:
        def __init__(self, symbol=None, price=None, timestamp=None):
            self.symbol = symbol
            self.price = price
            self.timestamp = timestamp
            self.id = 1

    class Base:
        pass

    fake_model.Price = Price
    fake_model.Base = Base
    sys.modules["backend.models.price_model"] = fake_model

if "backend.services.services" not in sys.modules:
    fake_services = _types.ModuleType("backend.services.services")

    async def fetch_coingecko_price(client, sym):
        return 100.0

    async def fetch_defillama_tvl(protocol):
        return {"tvl": 1000}

    async def fetch_cusd_price():
        return 1.0

    fake_services.fetch_coingecko_price = fetch_coingecko_price
    fake_services.fetch_defillama_tvl = fetch_defillama_tvl
    fake_services.fetch_cusd_price = fetch_cusd_price
    sys.modules["backend.services.services"] = fake_services


# Provide a simple redis.from_url implementation on the fake redis.asyncio module
class _FakeRedisClient:
    def __init__(self):
        self.store = {"latest_prices": {}}

    async def hset(self, name, key, value):
        self.store.setdefault(name, {})[key] = value

    async def hget(self, name, key):
        return self.store.get(name, {}).get(key)

    async def expire(self, name, ttl):
        return True

    async def close(self):
        return None


def _fake_from_url(url, decode_responses=True):
    return _FakeRedisClient()


sys.modules["redis.asyncio"].from_url = _fake_from_url


async def _async_noop(*a, **k):
    return None


class AsyncSessionStub:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def add(self, obj):
        # mimic SQLAlchemy add
        self._added = obj

    async def commit(self):
        return None

    async def refresh(self, obj):
        return None


class FakeResp:
    def __init__(self, status_code=200, data=None, text=None):
        self.status_code = status_code
        self._data = data
        self.text = text or (str(data) if data is not None else "")

    def json(self):
        return self._data


class AsyncClientMock:
    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, timeout=10.0):
        # return a simple JSON-like object with methods used by app
        class Resp:
            def __init__(self):
                self.status_code = 200
                self.text = "1000"

            def json(self):
                return {"tvl": 1000}

            def raise_for_status(self):
                return None

        return Resp()


@pytest.fixture(autouse=True)
def patch_backend(monkeypatch):
    """Patch backend internals to avoid network and DB during tests."""
    import backend.app as app_module

    # stub init_db to avoid creating tables
    monkeypatch.setattr(app_module, "init_db", lambda *a, **k: _async_noop())

    # stub AsyncSessionLocal used in endpoints
    monkeypatch.setattr(
        app_module, "AsyncSessionLocal", lambda *a, **k: AsyncSessionStub()
    )

    # stub retry helpers to return deterministic prices
    async def _rc(client, coin):
        return 123.45

    async def _rcusd():
        return 1.0

    monkeypatch.setattr(app_module, "_retry_coingecko", _rc)
    monkeypatch.setattr(app_module, "_retry_cusd", _rcusd)

    # stub historical impl to return a predictable list
    async def _hist(db, sym, limit=100, offset=0):
        return [
            {
                "symbol": sym,
                "price": 100.0,
                "timestamp": "2025-10-01T00:00:00Z",
                "id": 1,
            }
        ]

    monkeypatch.setattr(app_module, "_historical_prices_impl", _hist)

    # stub httpx.AsyncClient with a simple mock for tvl endpoint
    import httpx

    monkeypatch.setattr(
        app_module, "httpx", types.SimpleNamespace(AsyncClient=AsyncClientMock)
    )

    yield
