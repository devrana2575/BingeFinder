"""
tests/test_free_availability.py
=================================
Free/provider availability selection for the Free to Watch surface.
"""


def test_get_free_to_watch_respects_limit_and_sets_product_fields(monkeypatch):
    import config
    import backend.services.tmdb_reachability as reachability
    import backend.services.watch_provider_cache as provider_cache
    from backend.services.discovery_service import get_free_to_watch

    monkeypatch.setattr(config, "is_tmdb_configured", lambda: True)
    monkeypatch.setattr(reachability, "tmdb_available", lambda: True)

    calls = []

    def fake_lookup(series_id, imdb_id, series_name, premiered, region=None):
        calls.append(region)
        return {
            "providers": {
                "free": [{"provider_name": "Tubi TV"}],
                "ads": [],
            }
        }

    monkeypatch.setattr(provider_cache, "_cached_watch_providers", fake_lookup)

    docs = [
        {"series_id": i, "name": f"Free Show {i}", "rating": 8.0, "weight": 100}
        for i in range(10)
    ]

    result = get_free_to_watch(docs, limit=3, region="in")

    assert len(result) == 3
    assert calls and all(region == "IN" for region in calls)
    for item in result:
        assert item["_free_tier"] == "free"
        assert item["_free_provider_names"] == ["Tubi TV"]
        assert item["_free_providers"] == [{"provider_name": "Tubi TV"}]


def test_get_free_to_watch_returns_empty_without_tmdb(monkeypatch):
    import config
    from backend.services.discovery_service import get_free_to_watch

    monkeypatch.setattr(config, "is_tmdb_configured", lambda: False)

    docs = [{"series_id": 1, "name": "Show", "rating": 8.0, "weight": 100}]
    assert get_free_to_watch(docs, limit=6, region="US") == []
