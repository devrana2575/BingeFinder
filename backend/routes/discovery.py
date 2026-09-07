"""
backend/routes/discovery.py
=============================
GET /discover, /tonights-binge, /trending, /hidden-gems, /free-tonight,
/new-noteworthy, /surprise, /vibes
"""

from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, Depends, HTTPException

from backend.dependencies import get_current_user
from backend.schemas.discovery import SurprisePick
from backend.schemas.series import SeriesSummary
from backend.services import series_service, discovery_service, user_service
from api.tmdb import build_poster_url

router = APIRouter()

# Per-session seen IDs (in-memory, resets on server restart — acceptable)
_seen_ids: Set[int] = set()


def _doc_to_summary(doc: dict) -> SeriesSummary:
    return SeriesSummary(
        series_id=doc["series_id"],
        name=doc.get("name") or "Untitled",
        content_type=doc.get("content_type") or "tv_series",
        rating=doc.get("rating"),
        genres=doc.get("genres") or [],
        image=build_poster_url(doc.get("image_medium") or doc.get("image_original")),
        language=doc.get("language"),
        premiered=doc.get("premiered"),
        status=doc.get("status"),
        free_tier=doc.get("_free_tier"),
        free_provider_names=doc.get("_free_provider_names") or [],
    )


def _doc_to_pick(doc: dict) -> SurprisePick:
    network = doc.get("network")
    network_name = None
    if isinstance(network, dict):
        network_name = network.get("name")
    elif isinstance(network, str):
        network_name = network
    return SurprisePick(
        series_id=doc["series_id"],
        name=doc.get("name") or "Untitled",
        content_type=doc.get("content_type") or "tv_series",
        rating=doc.get("rating"),
        genres=doc.get("genres") or [],
        image=build_poster_url(doc.get("image_medium") or doc.get("image_original")),
        language=doc.get("language"),
        premiered=doc.get("premiered"),
        status=doc.get("status"),
        summary=doc.get("summary"),
        runtime=doc.get("runtime"),
        average_runtime=doc.get("average_runtime") or doc.get("runtime"),
        network=network_name,
        why=doc.get("_surprise_reasons") or [],
    )


def _build_surprise_signals(user_id: Optional[str]) -> Dict[str, Any]:
    """
    Assemble the signals used to make a Surprise Me pick taste-aware.
    Best-effort: any sub-lookup that fails (e.g. Mongo briefly down) is
    skipped, and the pick simply falls back to quality/popularity.
    """
    signals: Dict[str, Any] = {}
    if not user_id:
        return signals

    preferences, _ = user_service.get_settings(user_id)
    signals["preferences"] = preferences or {}

    seen: Set[int] = set()
    for resolver in (
        user_service.get_likes,
        user_service.get_watchlist,
        lambda uid: user_service.get_recently_viewed(uid, limit=20),
    ):
        try:
            items, _ = resolver(user_id)
            if items:
                seen.update(s.get("series_id") for s in items if isinstance(s, dict))
        except Exception:
            continue
    signals["seen_ids"] = seen
    return signals


def _load_catalog():
    docs, err = series_service.get_all_series()
    if err:
        raise HTTPException(status_code=503, detail=err)
    return docs


def _catalog_for_type(docs: List[Dict[str, Any]], content_type: Optional[str]) -> List[Dict[str, Any]]:
    """Scope a catalog to one content type (legacy docs count as tv_series)."""
    if not content_type:
        return docs
    return [d for d in docs if (d.get("content_type") or "tv_series") == content_type]


def _rail(content_type: Optional[str]) -> List[Dict[str, Any]]:
    return _catalog_for_type(_load_catalog(), content_type)


@router.get("/tonights-binge", response_model=List[SeriesSummary])
def tonights_binge(content_type: Optional[str] = None):
    docs = _rail(content_type)
    tonights = discovery_service.get_tonights_binge(docs, seen_ids=_seen_ids)
    for d in tonights:
        tid = d.get("series_id")
        if tid:
            _seen_ids.add(tid)
    return [_doc_to_summary(d) for d in tonights]


@router.get("/trending", response_model=List[SeriesSummary])
def trending(content_type: Optional[str] = None):
    docs = _rail(content_type)
    items = discovery_service.get_trending(docs, seen_ids=_seen_ids)
    for d in items:
        tid = d.get("series_id")
        if tid:
            _seen_ids.add(tid)
    return [_doc_to_summary(d) for d in items]


@router.get("/new-noteworthy", response_model=List[SeriesSummary])
def new_noteworthy(content_type: Optional[str] = None):
    docs = _rail(content_type)
    items = discovery_service.get_new_and_noteworthy(docs)
    return [_doc_to_summary(d) for d in items]


@router.get("/hidden-gems", response_model=List[SeriesSummary])
def hidden_gems(content_type: Optional[str] = None):
    docs = _rail(content_type)
    gems = discovery_service.get_hidden_gems(docs)
    return [_doc_to_summary(d) for d in gems]


@router.get("/free-tonight", response_model=List[SeriesSummary])
def free_tonight(region: Optional[str] = None, content_type: Optional[str] = None):
    docs = _rail(content_type)
    free = discovery_service.get_free_to_watch(docs, limit=6, region=region)
    return [_doc_to_summary(d) for d in free]


@router.get("/surprise", response_model=SurprisePick)
def surprise(
    user_id: Optional[str] = Depends(get_current_user),
    vibe: Optional[str] = None,
):
    docs = _load_catalog()
    signals = _build_surprise_signals(user_id)
    pick = discovery_service.get_surprise(docs, vibe_key=vibe, user_signals=signals)
    if pick is None:
        raise HTTPException(status_code=404, detail="No series available to surprise you with.")
    return _doc_to_pick(pick)


@router.get("/vibes")
def vibes():
    return discovery_service.get_vibes_info()


@router.get("/vibes/{vibe_key}", response_model=List[SeriesSummary])
def vibe_filtered(vibe_key: str):
    docs, err = series_service.get_all_series()
    if err:
        raise HTTPException(status_code=503, detail=err)
    filtered = discovery_service.get_vibe_filtered(docs, vibe_key)
    return [_doc_to_summary(d) for d in filtered]
