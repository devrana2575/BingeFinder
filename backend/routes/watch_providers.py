"""
backend/routes/watch_providers.py
===================================
GET /api/series/{series_id}/watch-providers     (router)
GET /api/watch-providers/available              (provider_list_router, "My Services")
"""

from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException

from backend.schemas.watch_providers import (
    AvailableProviderItem,
    AvailableProvidersResponse,
    ProviderItem,
    WatchProviderResponse,
)
from backend.services import provider_service, series_service
from regions import DEFAULT_REGION, normalize_region
from api.watch_providers import MAX_FREE_PROVIDERS, MAX_PAID_PROVIDERS
from api.tmdb import build_image_url, DEFAULT_LOGO_SIZE

router = APIRouter()
# Second, dedicated router so the provider-list endpoint lives at
# /api/watch-providers/available (a /available path under /api/series
# would be swallowed by the series router's /{series_id} route).
provider_list_router = APIRouter()


def _provider_item(
    name: str, logo_path: Optional[str], category: str, watch_url: Optional[str]
) -> ProviderItem:
    """Build a normalised provider item with a full logo URL."""
    full_logo = build_image_url(logo_path, DEFAULT_LOGO_SIZE)
    return ProviderItem(
        provider_name=name if name else "Unknown",
        logo_url=full_logo,
        provider_logo=full_logo,
        logo_path=logo_path,
        category=category,
        watch_url=watch_url,
        is_free=(category in ("free", "free_with_ads")),
        is_ads_supported=(category == "free_with_ads"),
    )


@router.get("/{series_id}/watch-providers", response_model=WatchProviderResponse)
def watch_providers(series_id: int, region: Optional[str] = None):
    effective_region = normalize_region(region)

    doc, err = series_service.get_series_by_id(series_id)
    if err:
        raise HTTPException(status_code=404, detail=err)

    providers_data = provider_service.get_watch_providers(
        series_id=doc.get("series_id"),
        imdb_id=doc.get("imdb_id"),
        series_name=doc.get("name") or "",
        premiered=doc.get("premiered"),
        region=effective_region,
    )

    justwatch_url = provider_service.get_justwatch_url(
        doc.get("name") or "", region=effective_region,
    )

    tmdb_missing = providers_data.get("error") == "tmdb_key_missing"
    lookup_failed = providers_data.get("error") == "provider_lookup_failed"
    effective_region = providers_data.get("region") or effective_region

    # Clean state machine for the frontend: distinguish "not configured",
    # "request failed" and "succeeded (with/without providers)".
    if tmdb_missing:
        status = "not_configured"
    elif lookup_failed:
        status = "error"
    else:
        # Availability succeeded. Even if every category is empty, this is a
        # valid result (e.g. "No streaming options found for Germany").
        status = "ok"

    providers_dict: Dict[str, List[ProviderItem]] = {}
    free_count = 0
    watch_now_url = None

    if status == "ok" and providers_data.get("providers"):
        raw = providers_data["providers"]
        # Free tier: keep the "free" vs "free-with-ads" labels for the UI, but
        # cap the COMBINED free+ads count at MAX_FREE_PROVIDERS total cards.
        # Genuinely free options take priority; ads fill any remaining slots.
        free = (raw.get("free") or [])
        ads = (raw.get("ads") or [])
        free_cards = free[:MAX_FREE_PROVIDERS]
        remaining = MAX_FREE_PROVIDERS - len(free_cards)
        ads_cards = ads[:remaining] if remaining > 0 else []
        free_count = len(free_cards) + len(ads_cards)

        # Real TMDB availability URL (never fabricated). Each provider card
        # points at this same real availability page as its action URL.
        watch_now_url = providers_data.get("watch_now_url")

        if free_cards:
            providers_dict["free"] = [
                _provider_item(
                    p.get("provider_name", "Unknown"),
                    p.get("logo_path"),
                    "free",
                    watch_now_url,
                )
                for p in free_cards
            ]
        if ads_cards:
            providers_dict["ads"] = [
                _provider_item(
                    p.get("provider_name", "Unknown"),
                    p.get("logo_path"),
                    "free_with_ads",
                    watch_now_url,
                )
                for p in ads_cards
            ]
        # Paid tiers: only render categories that are actually present.
        for key, cap in MAX_PAID_PROVIDERS.items():
            items = raw.get(key) or []
            if items:
                providers_dict[key] = [
                    _provider_item(
                        p.get("provider_name", "Unknown"),
                        p.get("logo_path"),
                        key,
                        watch_now_url,
                    )
                    for p in items[:cap]
                ]

    return WatchProviderResponse(
        series_id=series_id,
        providers=providers_dict,
        justwatch_url=justwatch_url,
        watch_now_url=watch_now_url,
        region=effective_region,
        free_count=free_count,
        tmdb_configured=not tmdb_missing,
        status=status,
    )


@provider_list_router.get("/available", response_model=AvailableProvidersResponse)
def available_providers(region: str = None):
    """
    Return the list of watch providers available for TV in a region.

    Used by the optional "My Services" preference picker. The provider
    list always comes straight from the availability data source — it is
    never hardcoded. If the availability service is unconfigured or the
    request fails, the section is simply hidden in the UI rather than
    breaking the settings page.
    """
    effective_region = normalize_region(region)
    result = provider_service.get_available_providers(effective_region)
    if result.get("error") == "tmdb_key_missing":
        raise HTTPException(status_code=503, detail="Watch availability is not configured.")
    if result.get("error"):
        raise HTTPException(status_code=503, detail="Watch availability is temporarily unavailable.")
    return AvailableProvidersResponse(
        region=result.get("region") or effective_region,
        providers=[
            AvailableProviderItem(
                provider_id=p["provider_id"],
                provider_name=p["provider_name"],
                logo_url=p.get("logo_url"),
            )
            for p in (result.get("providers") or [])
            if isinstance(p, dict) and p.get("provider_id") is not None
        ],
        status="ok",
    )
