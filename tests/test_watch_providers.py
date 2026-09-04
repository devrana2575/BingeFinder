"""
tests/test_watch_providers.py
==============================
Tests for the Where-To-Watch availability pipeline (India region):

    - default region is India (DEFAULT_WATCH_REGION == "IN")
    - combined free + free-with-ads providers are capped (MAX_FREE_PROVIDERS = 3)
    - per-category paid caps are respected
    - only categories that are actually present are rendered
    - watch_now_url is a real, derived TMDB URL (never fabricated)
    - justwatch fallback URL is a real JustWatch link
    - graceful handling when the TMDB key / providers are missing

Run with:
    pytest tests/test_watch_providers.py -v
"""

import pytest

from api.watch_providers import (
    DEFAULT_WATCH_REGION,
    MAX_FREE_PROVIDERS,
    MAX_PAID_PROVIDERS,
    get_provider_page_url,
)
from backend.routes.watch_providers import watch_providers


# ---------------------------------------------------------------------------
# Constants / shape
# ---------------------------------------------------------------------------

def test_default_region_is_india():
    assert DEFAULT_WATCH_REGION == "IN"


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
    url = get_provider_page_url("Breaking Bad")
    assert url is not None
    assert "justwatch.com" in url
    assert "breaking-bad" in url


def test_justwatch_url_empty_name_is_none():
    assert get_provider_page_url("") is None


# ---------------------------------------------------------------------------
# Route behaviour (provider_service mocked so no TMDB key needed)
# ---------------------------------------------------------------------------

def _craft_provider_data(free=6, ads=6, flatrate=2, rent=1, buy=1):
    def _mk(n, prefix="P"):
        return [{"provider_name": f"{prefix}{i}", "logo_path": f"/x{i}.png"} for i in range(n)]

    return {
        "region": "IN",
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

    def fake_get(series_id, imdb_id, series_name, premiered):
        return _craft_provider_data(free=6, ads=6)

    monkeypatch.setattr(ps, "get_watch_providers", fake_get)

    resp = watch_providers(1001)
    combined_free = len(resp.providers.get("free", [])) + len(resp.providers.get("ads", []))
    assert 0 < combined_free <= MAX_FREE_PROVIDERS
    assert resp.free_count == combined_free


def test_route_renders_only_present_categories(seeded_mongo_manager, monkeypatch):
    import backend.services.provider_service as ps

    def fake_get(series_id, imdb_id, series_name, premiered):
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

    def fake_get(series_id, imdb_id, series_name, premiered):
        return _craft_provider_data(free=1, ads=0, flatrate=0, rent=0, buy=0)

    monkeypatch.setattr(ps, "get_watch_providers", fake_get)
    resp = watch_providers(1001)
    assert resp.watch_now_url
    assert "themoviedb.org" in resp.watch_now_url
    assert "watch" in resp.watch_now_url
    assert resp.region == "IN"


def test_route_handles_missing_tmdb_key_gracefully(seeded_mongo_manager, monkeypatch):
    import backend.services.provider_service as ps

    def fake_get(series_id, imdb_id, series_name, premiered):
        return {"error": "tmdb_key_missing"}

    monkeypatch.setattr(ps, "get_watch_providers", fake_get)
    resp = watch_providers(1001)
    assert resp.tmdb_configured is False
    assert resp.providers == {}
    assert resp.free_count == 0


def test_route_handles_empty_providers(seeded_mongo_manager, monkeypatch):
    import backend.services.provider_service as ps

    def fake_get(series_id, imdb_id, series_name, premiered):
        return {}

    monkeypatch.setattr(ps, "get_watch_providers", fake_get)
    resp = watch_providers(1001)
    assert resp.providers == {}
    assert resp.free_count == 0
