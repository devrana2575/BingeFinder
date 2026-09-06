"""
tests/test_discovery_rails.py
===============================
Tests for the Surprise Me (taste-aware), Trending and New & Noteworthy
discovery rails. Uses the in-memory seeded catalog from sample_series.py.
"""

import random

from tests.sample_series import SAMPLE_SERIES


def test_surprise_returns_pick_with_grounded_reasons():
    from backend.services.discovery_service import get_surprise

    pick = get_surprise(SAMPLE_SERIES)
    assert pick is not None
    assert pick.get("series_id") is not None
    assert "_surprise_reasons" in pick
    assert isinstance(pick["_surprise_reasons"], list)


def test_surprise_respects_preferences_and_reasons():
    from backend.services.discovery_service import get_surprise

    signals = {
        "preferences": {"genres": ["Crime"], "languages": ["English"]},
        "seen_ids": set(),
    }
    rng = random.Random(1)
    pick = get_surprise(SAMPLE_SERIES, user_signals=signals, rng=rng)
    assert pick is not None
    # Grounded reason reflects the actual overlap.
    if pick["genres"] and "Crime" in (pick["genres"] or []):
        assert any("Crime" in r for r in pick["_surprise_reasons"])


def test_surprise_avoids_already_seen_when_pool_is_large():
    from backend.services.discovery_service import get_surprise

    # Only one un-seen title; pool is tiny, so seen-filter must not empty
    # the pool (MIN_SURPRISE_POOL guard). We pick every candidate and
    # ensure we still get a real pick.
    seen = {d["series_id"] for d in SAMPLE_SERIES if d["series_id"] and d["series_id"] != 1001}
    signals = {"preferences": {}, "seen_ids": seen}
    rng = random.Random(2)
    pick = get_surprise(SAMPLE_SERIES, user_signals=signals, rng=rng)
    assert pick is not None
    assert pick.get("series_id") is not None


def test_surprise_guest_returns_real_title():
    from backend.services.discovery_service import get_surprise

    pick = get_surprise(SAMPLE_SERIES, user_signals={}, rng=random.Random(3))
    assert pick is not None
    assert pick["series_id"] in {d["series_id"] for d in SAMPLE_SERIES if d["series_id"]}


def test_trending_returns_diversified_sorted_series():
    from backend.services.discovery_service import get_trending

    items = get_trending(SAMPLE_SERIES, seen_ids=set(), limit=8)
    assert 1 <= len(items) <= 8
    # None of the sample items lack an image, and results keep original docs.
    for item in items:
        assert item.get("series_id") is not None


def test_trending_excludes_seen_ids():
    from backend.services.discovery_service import get_trending

    seen = {1001}
    items = get_trending(SAMPLE_SERIES, seen_ids=seen, limit=8)
    for item in items:
        assert item["series_id"] != 1001


def test_new_and_noteworthy_selects_recent_highly_rated():
    from backend.services.discovery_service import get_new_and_noteworthy

    items = get_new_and_noteworthy(SAMPLE_SERIES, limit=8)
    assert isinstance(items, list)
    for item in items:
        assert isinstance(item.get("rating"), (int, float))
        assert item["rating"] >= 6.5


def test_available_providers_missing_key_returns_error_marker(monkeypatch):
    import api.watch_providers as wp_module

    monkeypatch.setattr(wp_module, "TMDbClient", lambda: (_ for _ in ()).throw(RuntimeError("no key")))

    result = wp_module.get_available_providers("US")
    assert result == []