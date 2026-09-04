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
) -> Dict[str, Any]:
    """Get watch providers for a series. Returns {} if TMDB key is missing."""
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
            series_id, imdb_id=imdb_id, series_name=series_name, premiered=premiered
        )
        return result or {}
    except Exception:
        return {}


def get_justwatch_url(series_name: str) -> Optional[str]:
    """Get JustWatch page URL for a series."""
    try:
        from api.watch_providers import get_provider_page_url
        return get_provider_page_url(series_name)
    except Exception:
        return None
