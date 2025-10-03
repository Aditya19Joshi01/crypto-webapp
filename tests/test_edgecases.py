import pytest
from fastapi.testclient import TestClient


from backend import app as app_module


@pytest.fixture
def client():
    return TestClient(app_module.app)


def test_invalid_symbol_fetch(client):
    r = client.post("/prices/unknowncoin/fetch")
    assert r.status_code == 400


def test_fetch_price_upstream_failure(monkeypatch, client):
    # Force _retry_coingecko to fail (return None) so fetch_price_now returns 502
    async def _fail(*a, **k):
        return None

    monkeypatch.setattr(app_module, "_retry_coingecko", _fail)

    r = client.post("/prices/bitcoin/fetch")
    assert r.status_code == 502


def test_tvl_all_retries_fail(monkeypatch, client):
    # AsyncClient that always raises
    class BadClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **k):
            raise Exception("network down")

    monkeypatch.setattr(
        app_module,
        "httpx",
        type("M", (), {"AsyncClient": BadClient, "HTTPStatusError": Exception}),
    )

    r = client.get("/tvl/someprotocol")
    assert r.status_code == 502


def test_tvl_scalar_text_parsed(monkeypatch, client):
    # AsyncClient that returns a response with text numeric content
    class Resp:
        def __init__(self, text):
            self.status_code = 200
            self.text = text

        def json(self):
            raise ValueError("not json")

        def raise_for_status(self):
            return None

    class GoodClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **k):
            return Resp("12345")

    monkeypatch.setattr(app_module, "httpx", type("M", (), {"AsyncClient": GoodClient}))

    r = client.get("/tvl/someprotocol")
    assert r.status_code == 200
    j = r.json()
    assert j.get("tvl") == 12345.0
