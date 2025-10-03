import asyncio
import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    # import app lazily so conftest monkeypatches are applied
    from backend.app import app

    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_get_mode_default(client):
    r = client.get("/mode")
    assert r.status_code == 200
    # The app exposes 'live_mode' key
    j = r.json()
    assert "live_mode" in j


def test_set_mode(client):
    r = client.post("/mode", json={"live": True})
    # Should return a JSON indicating new mode or the same
    assert r.status_code == 200
    assert "live_mode" in r.json()


def test_fetch_price_and_historical(client):
    # fetch triggers the stubbed _retry_coingecko/_retry_cusd and DB stub
    r = client.post("/prices/bitcoin/fetch")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict)

    # historical
    r2 = client.get("/prices/bitcoin")
    assert r2.status_code == 200
    arr = r2.json()
    assert isinstance(arr, list)
    assert arr and "price" in arr[0]


def test_latest_not_found(client):
    # With our monkeypatch, latest may read redis; ensure it handles missing
    r = client.get("/prices/bitcoin/latest")
    # We allow either 200 (if set) or 404 when not set
    assert r.status_code in (200, 404)


def test_tvl_json(client):
    r = client.get("/tvl/uniswap")
    assert r.status_code == 200
    # Should be JSON-decodable and have expected fields
    j = r.json()
    assert isinstance(j, dict)
    assert "tvl" in j or "items" in j or "tvl_raw" in j
