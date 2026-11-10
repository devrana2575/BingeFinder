"""
Auth gates for catalog/discovery APIs.

The product is login-to-explore: the SPA redirects guests to /login, and the
API must enforce the same rule so the catalog cannot be read by bypassing the
UI. Auth, regions, and health/readiness stay public.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import series_service
from backend.services.auth_service import create_access_token

client = TestClient(app)

PROTECTED_PATHS = [
    "/api/series/count",
    "/api/series/filters",
    "/api/series/search?q=test",
    "/api/series/suggest?q=test",
    "/api/series/1",
    "/api/series/1/recommendations",
    "/api/series/1/watch-providers",
    "/api/watch-providers/available",
    "/api/recommendations/personalized",
    "/api/discover/tonights-binge",
    "/api/discover/trending",
    "/api/discover/vibes",
    "/api/discover/surprise",
    "/api/events/status",
]

PUBLIC_PATHS = [
    "/api/health",
    "/api/regions",
    "/api/regions/in",
]


@pytest.mark.parametrize("path", PROTECTED_PATHS)
def test_exploration_requires_login(path):
    resp = client.get(path)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Authentication required"


def test_invalid_token_is_rejected():
    resp = client.get(
        "/api/series/count",
        headers={"Authorization": "Bearer definitely-not-a-valid-token"},
    )
    assert resp.status_code == 401


def test_valid_token_can_read_catalog(monkeypatch):
    monkeypatch.setattr(series_service, "get_series_count", lambda: 42)
    token = create_access_token("test-user")

    resp = client.get(
        "/api/series/count",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"total": 42}


@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_public_endpoints_stay_public(path):
    resp = client.get(path)
    assert resp.status_code == 200
