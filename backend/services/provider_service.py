"""
backend/services/provider_service.py
=====================================
Wraps watch_providers.py for the API layer.
"""

from typing import Any, Dict, Optional


def get_watch_providers(
    series_id: int,
    imdb_id: Optional[str],
    series_name: str,
    premiered: Optional[str],
    region: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get watch providers for a series, scoped to the requested region.

    Returns:
        A dict shaped like `get_watch_providers_for_series`, or a marker:
          {"error": "tmdb_key_missing"}  - availability service has no key
    """
    try:
        from config import get_tmdb_api_key
        get_tmdb_api_key()
    except Exception:
        return {"error": "tmdb_key_missing"}

    try:
        # Route through the shared TTL-backed cache
        # (backend.services.watch_provider_cache, CACHE_TTL_SECONDS = 600).
        from backend.services.watch_provider_cache import _cached_watch_providers
        result = _cached_watch_providers(
            series_id, imdb_id=imdb_id, series_name=series_name, premiered=premiered,
            region=region,
        )
        if not result:
            # Empty dict => the lookup itself failed (no external series ID
            # resolved, or the availability request errored). A *successful*
            # lookup with no providers still returns a dict that carries a
            # "providers" key (all categories empty), so this branch is
            # genuinely a failure, not "no streaming options".
            return {"error": "provider_lookup_failed"}
        return result
    except Exception:
        # Availability lookup failed (network/parse). The frontend should
        # show a "temporarily unavailable" state, NOT "no providers exist".
        return {"error": "provider_lookup_failed"}


def get_available_providers(region: Optional[str] = None) -> Dict[str, Any]:
    """
    Get the list of watch providers available for TV in a region.

    Returns:
        {"region": code, "providers": [...]} on success, or a marker:
          {"error": "tmdb_key_missing"}      - availability service has no key
          {"error": "provider_lookup_failed"} - availability request failed
    """
    try:
        from config import get_tmdb_api_key
        get_tmdb_api_key()
    except Exception:
        return {"error": "tmdb_key_missing"}

    from regions import normalize_region

    effective_region = normalize_region(region)

    try:
        from api.watch_providers import get_available_providers as _get_available_providers
        providers = _get_available_providers(region=effective_region)
        if not providers:
            return {"error": "provider_lookup_failed"}
        return {"region": effective_region, "providers": providers}
    except Exception:
        return {"error": "provider_lookup_failed"}


def get_justwatch_url(series_name: str, region: Optional[str] = None) -> Optional[str]:
    """Get JustWatch page URL for a series, scoped to a region."""
    try:
        from api.watch_providers import get_provider_page_url
        return get_provider_page_url(series_name, region=region)
    except Exception:
        return None
