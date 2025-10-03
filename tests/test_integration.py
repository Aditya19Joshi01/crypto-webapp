import os
import time
import pytest
import requests


pytestmark = pytest.mark.integration


def _skip_if_needed():
    if os.getenv("RUN_INTEGRATION", "0") != "1":
        pytest.skip("Integration tests disabled. Set RUN_INTEGRATION=1 to enable.")


def test_backend_end_to_end_fetch_and_latest():
    _skip_if_needed()
    # Expect docker-compose to expose backend at localhost:8000, postgres at 5432, redis at 6379
    base = os.getenv("BACKEND_URL", "http://localhost:8000")

    # Wait a short while for services to be ready (in CI the workflow will wait separately)
    time.sleep(2)

    # Toggle live mode on (ensure backend will use Redis)
    r = requests.post(f"{base}/mode", json={"live": True}, timeout=5)
    assert r.status_code in (200, 204)

    # Trigger on-demand fetch for bitcoin
    r = requests.post(f"{base}/prices/bitcoin/fetch", timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("symbol") == "bitcoin"

    # Allow brief propagation then request latest
    time.sleep(1)
    r2 = requests.get(f"{base}/prices/bitcoin/latest", timeout=5)
    assert r2.status_code == 200
    latest = r2.json()
    assert "price" in latest
