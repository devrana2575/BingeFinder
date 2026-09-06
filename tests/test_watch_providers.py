"""
tests/test_watch_providers.py
=============================
Tests for the Where-To-Watch availability pipeline (region-scoped):

    - a shared, supported default region exists (never hard-coded to India)
    - unknown/empty region codes fall back gracefully to the default
    - the route threads the requested region through the provider service
    - combined free + free-with-ads providers are capped (MAX_FREE_PROVIDERS = 3)
    - per-category paid caps are respected
    - only categories that are actually present are rendered
    - watch_now_url is a real, derived TMDB URL (never fabricated)
    - justwatch fallback URL is a real JustWatch link, scoped to a region
    - graceful handling when the TMDB key / providers are missing

Run with:
    pytest tests/test_watch_providers.py -v
"""

import pytest

from api.watch_providers import (
    MAX_FREE_PROVIDERS,
    MAX_PAID_PROVIDERS,
    get_provider_page_url,
)
from backend.routes.watch_providers import watch_providers, available_providers
from regions import DEFAULT_REGION, normalize_region, SUPPORTED_REGIONS


# ---------------------------------------------------------------------------
# Constants / shape
# ---------------------------------------------------------------------------

def test_default_region_is_supported_and_not_india_only():
    codes = {r["code"] for r in SUPPORTED_REGIONS}
    assert DEFAULT_REGION in codes
    # The pipeline is region-scoped; India is one supported option, not the
    # only market.
    assert "IN" in codes
    assert len(codes) > 20


def test_normalize_region_fallback_and_case():
    assert normalize_region("in") == "IN"
    assert normalize_region("us") == "US"
    # Unknown/empty codes fall back to the shared default (never crash).
    assert normalize_region("") == DEFAULT_REGION
    assert normalize_region(None) == DEFAULT_REGION
    assert normalize_region("zz") == DEFAULT_REGION


def test_free_provider_cap_is_three():
    assert MAX_FREE_PROVIDERS == 3


def test_paid_caps_are_defined():
    assert MAX_PAID_PROVIDERS["flatrate"] >= 1
    assert MAX_PAID_PROVIDERS["rent"] >= 1
    assert MAX_PAID_PROVIDERS["buy"] >= 1


# ---------------------------------------------------------------------------
# Real URLs (never fabricated)
# ---------------------------------------------------------------------------

def test_justwatch_url_is_real_domain():
    url = get_provider_page_url("Breaking Bad", region="IN")
    assert url is not None
    assert "justwatch.com" in url
    assert "breaking-bad" in url
    assert "/in/tv-show/" in url


def test_justwatch_url_empty_name_is_none():
    assert get_provider_page_url("") is None


# ---------------------------------------------------------------------------
# Route behaviour (provider_service mocked so no TMDB key needed)
# ---------------------------------------------------------------------------

def _craft_provider_data(free=6, ads=6, flatrate=2, rent=1, buy=1, region="IN"):
    def _mk(n, prefix="P"):
        return [{"provider_name": f"{prefix}{i}", "logo_path": f"/x{i}.png"} for i in range(n)]

    return {
        "region": region,
        "providers": {
            "free": _mk(free, "F"),
            "ads": _mk(ads, "A"),
            "flatrate": _mk(flatrate, "S"),
            "rent": _mk(rent, "R"),
            "buy": _mk(buy, "B"),
        },
        "link": "https://www.themoviedb.org/tv/999",
        "watch_now_url": "https://www.themoviedb.org/tv/999/watch?locale=IN",
        "tmdb_id": 999,
    }


def test_route_caps_combined_free_plus_ads_at_three(seeded_mongo_manager, monkeypatch):
    import backend.services.provider_service as ps

    def fake_get(series_id, imdb_id, series_name, premiered, region=None):
        return _craft_provider_data(free=6, ads=6)

    monkeypatch.setattr(ps, "get_watch_providers", fake_get)

    resp = watch_providers(1001)
    combined_free = len(resp.providers.get("free", [])) + len(resp.providers.get("ads", []))
    assert 0 < combined_free <= MAX_FREE_PROVIDERS
    assert resp.free_count == combined_free


def test_route_renders_only_present_categories(seeded_mongo_manager, monkeypatch):
    import backend.services.provider_service as ps

    def fake_get(series_id, imdb_id, series_name, premiered, region=None):
        data = _craft_provider_data(free=1, ads=0, flatrate=0, rent=0, buy=0)
        return data

    monkeypatch.setattr(ps, "get_watch_providers", fake_get)
    resp = watch_providers(1001)
    assert resp.providers.get("free")
    assert "ads" not in resp.providers
    assert "flatrate" not in resp.providers
    assert "rent" not in resp.providers
    assert "buy" not in resp.providers


def test_route_uses_derived_tmdb_watch_url(seeded_mongo_manager, monkeypatch):
    import backend.services.provider_service as ps

    def fake_get(series_id, imdb_id, series_name, premiered, region=None):
        return _craft_provider_data(free=1, ads=0, flatrate=0, rent=0, buy=0)

    monkeypatch.setattr(ps, "get_watch_providers", fake_get)
    resp = watch_providers(1001)
    assert resp.watch_now_url
    assert "themoviedb.org" in resp.watch_now_url
    assert "watch" in resp.watch_now_url
    assert resp.region == "IN"


def test_route_threads_requested_region_to_service(seeded_mongo_manager, monkeypatch):
    """The region query param must reach the provider service."""
    import backend.services.provider_service as ps

    captured = {}

    def fake_get(series_id, imdb_id, series_name, premiered, region=None):
        captured["region"] = region
        return _craft_provider_data(free=1, ads=0, flatrate=0, rent=0, buy=0)

    monkeypatch.setattr(ps, "get_watch_providers", fake_get)
    monkeypatch.setattr(ps, "get_justwatch_url", lambda *a, **k: None)
    resp = watch_providers(1001, region="DE")
    assert captured.get("region") == "DE"
    # Service data overrides the default region in the response.
    assert resp.region == "IN"


def test_route_provider_items_are_normalized(seeded_mongo_manager, monkeypatch):
    import backend.services.provider_service as ps

    def fake_get(series_id, imdb_id, series_name, premiered, region=None):
        return _craft_provider_data(free=1, ads=1, flatrate=1, rent=0, buy=0)

    monkeypatch.setattr(ps, "get_watch_providers", fake_get)
    resp = watch_providers(1001)
    free_item = resp.providers["free"][0]
    assert free_item.is_free is True
    assert free_item.is_ads_supported is False
    assert free_item.provider_logo == free_item.logo_url
    ads_item = resp.providers["ads"][0]
    assert ads_item.is_ads_supported is True
    assert ads_item.is_free is True
    flatrate_item = resp.providers["flatrate"][0]
    assert flatrate_item.is_free is False


def test_route_handles_missing_tmdb_key_gracefully(seeded_mongo_manager, monkeypatch):
    import backend.services.provider_service as ps

    def fake_get(series_id, imdb_id, series_name, premiered, region=None):
        return {"error": "tmdb_key_missing"}

    monkeypatch.setattr(ps, "get_watch_providers", fake_get)
    resp = watch_providers(1001)
    assert resp.tmdb_configured is False
    assert resp.providers == {}
    assert resp.free_count == 0


def test_route_handles_empty_providers(seeded_mongo_manager, monkeypatch):
    import backend.services.provider_service as ps

    def fake_get(series_id, imdb_id, series_name, premiered, region=None):
        return {}

    monkeypatch.setattr(ps, "get_watch_providers", fake_get)
    resp = watch_providers(1001)
    assert resp.providers == {}
    assert resp.free_count == 0


# ---------------------------------------------------------------------------
# Clean status state machine (drives the user-facing messages)
# ---------------------------------------------------------------------------

def test_status_is_not_configured_when_key_missing(seeded_mongo_manager, monkeypatch):
    import backend.services.provider_service as ps

    monkeypatch.setattr(
        ps, "get_watch_providers",
        lambda *a, **k: {"error": "tmdb_key_missing"},
    )
    resp = watch_providers(1001)
    assert resp.status == "not_configured"
    assert resp.tmdb_configured is False


def test_status_is_error_when_lookup_fails(seeded_mongo_manager, monkeypatch):
    import backend.services.provider_service as ps

    monkeypatch.setattr(
        ps, "get_watch_providers",
        lambda *a, **k: {"error": "provider_lookup_failed"},
    )
    resp = watch_providers(1001)
    assert resp.status == "error"
    assert resp.providers == {}


def test_status_is_ok_with_providers(seeded_mongo_manager, monkeypatch):
    import backend.services.provider_service as ps

    monkeypatch.setattr(
        ps, "get_watch_providers",
        lambda *a, **k: _craft_provider_data(free=1, ads=0, flatrate=0, rent=0, buy=0),
    )
    resp = watch_providers(1001)
    assert resp.status == "ok"
    assert resp.providers.get("free")
    assert resp.tmdb_configured is True


def test_status_is_ok_with_no_providers(seeded_mongo_manager, monkeypatch):
    import backend.services.provider_service as ps

    monkeypatch.setattr(
        ps, "get_watch_providers",
        lambda *a, **k: {"region": "US", "providers": {}},
    )
    resp = watch_providers(1001)
    assert resp.status == "ok"
    assert resp.providers == {}
    # A real "no providers" result is distinct from lookup failure.
    assert resp.tmdb_configured is True


# ---------------------------------------------------------------------------
# Available-providers endpoint (powers the optional "My Services" picker)
# ---------------------------------------------------------------------------

def test_available_providers_returns_normalized_items(monkeypatch):
    import backend.services.provider_service as ps

    def fake_get(region=None):
        return {
            "region": "US",
            "providers": [
                {"provider_id": 8, "provider_name": "Netflix", "logo_url": "https://image.tmdb.org/t/p/w92/x.jpg"},
                {"provider_id": 337, "provider_name": "Disney Plus", "logo_url": None},
            ],
        }

    monkeypatch.setattr(ps, "get_available_providers", fake_get)
    resp = available_providers("US")
    assert resp.status == "ok"
    assert resp.region == "US"
    assert [p.provider_id for p in resp.providers] == [8, 337]
    assert resp.providers[0].provider_name == "Netflix"


def test_available_providers_threads_region_to_service(monkeypatch):
    import backend.services.provider_service as ps

    captured = {}

    def fake_get(region=None):
        captured["region"] = region
        return {"region": "DE", "providers": [{"provider_id": 1, "provider_name": "P"}]}

    monkeypatch.setattr(ps, "get_available_providers", fake_get)
    available_providers("DE")
    assert captured.get("region") == "DE"


def test_available_providers_missing_key_raises_clean_error(monkeypatch):
    import pytest
    from fastapi import HTTPException
    import backend.services.provider_service as ps

    monkeypatch.setattr(
        ps, "get_available_providers", lambda *a, **k: {"error": "tmdb_key_missing"},
    )
    with pytest.raises(HTTPException) as exc_info:
        available_providers("US")
    assert exc_info.value.status_code == 503
    assert "not configured" in str(exc_info.value.detail).lower()


def test_available_providers_lookup_failure_raises_clean_error(monkeypatch):
    import pytest
    from fastapi import HTTPException
    import backend.services.provider_service as ps

    monkeypatch.setattr(
        ps, "get_available_providers", lambda *a, **k: {"error": "provider_lookup_failed"},
    )
    with pytest.raises(HTTPException) as exc_info:
        available_providers("US")
    assert exc_info.value.status_code == 503
    assert "temporarily unavailable" in str(exc_info.value.detail).lower()
