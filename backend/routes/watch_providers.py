"""
backend/routes/watch_providers.py
==================================
GET /series/{series_id}/watch-providers
"""

from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException

from backend.schemas.watch_providers import ProviderItem, WatchProviderResponse
from backend.services import provider_service, series_service
from api.watch_providers import DEFAULT_WATCH_REGION, MAX_FREE_PROVIDERS, MAX_PAID_PROVIDERS

router = APIRouter()


@router.get("/{series_id}/watch-providers", response_model=WatchProviderResponse)
def watch_providers(series_id: int, region: Optional[str] = None):
    doc, err = series_service.get_series_by_id(series_id)
    if err:
        raise HTTPException(status_code=404, detail=err)

    providers_data = provider_service.get_watch_providers(
        series_id=doc.get("series_id"),
        imdb_id=doc.get("imdb_id"),
        series_name=doc.get("name") or "",
        premiered=doc.get("premiered"),
    )

    justwatch_url = provider_service.get_justwatch_url(doc.get("name") or "")

    tmdb_missing = providers_data.get("error") == "tmdb_key_missing"
    effective_region = providers_data.get("region") or region or DEFAULT_WATCH_REGION

    providers_dict: Dict[str, List[ProviderItem]] = {}
    free_count = 0
    watch_now_url = None

    if providers_data and not tmdb_missing and providers_data.get("providers"):
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
        if free_cards:
            providers_dict["free"] = [
                ProviderItem(provider_name=p.get("provider_name", "Unknown"), logo_path=p.get("logo_path"))
                for p in free_cards
            ]
        if ads_cards:
            providers_dict["ads"] = [
                ProviderItem(provider_name=p.get("provider_name", "Unknown"), logo_path=p.get("logo_path"))
                for p in ads_cards
            ]
        # Paid tiers: only render categories that are actually present.
        for key, cap in MAX_PAID_PROVIDERS.items():
            items = raw.get(key) or []
            if items:
                providers_dict[key] = [
                    ProviderItem(
                        provider_name=p.get("provider_name", "Unknown"),
                        logo_path=p.get("logo_path"),
                    )
                    for p in items[:cap]
                ]

        # Real TMDB availability URL (never fabricated).
        watch_now_url = providers_data.get("watch_now_url")

    return WatchProviderResponse(
        series_id=series_id,
        providers=providers_dict,
        justwatch_url=justwatch_url,
        watch_now_url=watch_now_url,
        region=effective_region,
        free_count=free_count,
        tmdb_configured=not tmdb_missing,
    )
