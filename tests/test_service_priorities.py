"""
tests/test_service_priorities.py
=================================
Tests for the "Available on your services" recommendation boost.

The fork is deliberate: re-ranking must ONLY happen when genuine provider
data is available. When the availability source is unconfigured or fails,
the ranking must stay untouched (never a fabricated claim).
"""

import pytest

from backend.services.rec_service import _get_service_matches


def _cached(series_lookup):
    """Return a function pretending to be the provider cache for series ids."""
    def fake(sid, *args, **kwargs):
        return series_lookup.get(sid)
    return fake


def test_matches_on_genuine_provider_data(monkeypatch):
    import backend.services.watch_provider_cache as wpc

    providers_8 = {
        "region": "US",
        "providers": {
            "flatrate": [{"provider_id": 8, "provider_name": "Netflix"}],
        },
    }
    providers_337 = {
        "region": "US",
        "providers": {
            "flatrate": [{"provider_id": 337, "provider_name": "Disney Plus"}],
        },
    }
    monkeypatch.setattr(
        wpc, "_cached_watch_providers",
        _cached({1: providers_8, 2: providers_337}),
    )

    matches, got_signal = _get_service_matches([1, 2], [8, 337], region="US")
    assert got_signal is True
    assert matches[1] == ["Netflix"]
    assert matches[2] == ["Disney Plus"]


def test_no_match_when_services_not_available(monkeypatch):
    import backend.services.watch_provider_cache as wpc

    providers = {
        "region": "US",
        "providers": {
            "flatrate": [{"provider_id": 337, "provider_name": "Disney Plus"}],
        },
    }
    monkeypatch.setattr(wpc, "_cached_watch_providers", _cached({1: providers}))

    matches, got_signal = _get_service_matches([1], [8], region="US")
    assert got_signal is True
    assert matches == {}


def test_unconfigured_source_never_signals(monkeypatch):
    import backend.services.watch_provider_cache as wpc

    monkeypatch.setattr(
        wpc, "_cached_watch_providers",
        _cached({1: {"error": "tmdb_key_missing"}}),
    )

    matches, got_signal = _get_service_matches([1], [8], region="US")
    assert got_signal is False
    assert matches == {}


def test_failed_lookup_never_signals(monkeypatch):
    import backend.services.watch_provider_cache as wpc

    monkeypatch.setattr(
        wpc, "_cached_watch_providers",
        _cached({1: {"error": "provider_lookup_failed"}}),
    )

    matches, got_signal = _get_service_matches([1], [8], region="US")
    assert got_signal is False
    assert matches == {}


def test_exception_among_lookups_is_safe(monkeypatch):
    import backend.services.watch_provider_cache as wpc

    def boom(sid, *args, **kwargs):
        raise RuntimeError("timeout")

    monkeypatch.setattr(wpc, "_cached_watch_providers", boom)
    matches, got_signal = _get_service_matches([1, 2, 3], [8], region="US")
    assert got_signal is False
    assert matches == {}