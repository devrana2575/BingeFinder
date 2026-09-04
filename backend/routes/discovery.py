"""
backend/routes/discovery.py
=============================
GET /discover, /tonights-binge, /free-tonight, /surprise, /vibes
"""

from typing import List, Optional, Set

from fastapi import APIRouter, HTTPException

from backend.schemas.series import SeriesSummary
from backend.services import series_service, discovery_service

router = APIRouter()

# Per-session seen IDs (in-memory, resets on server restart — acceptable)
_seen_ids: Set[int] = set()


def _doc_to_summary(doc: dict) -> SeriesSummary:
    return SeriesSummary(
        series_id=doc["series_id"],
        name=doc.get("name") or "Untitled",
        rating=doc.get("rating"),
        genres=doc.get("genres") or [],
        image=doc.get("image_medium") or doc.get("image_original"),
        language=doc.get("language"),
        premiered=doc.get("premiered"),
        status=doc.get("status"),
    )


@router.get("/tonights-binge", response_model=List[SeriesSummary])
def tonights_binge():
    docs, err = series_service.get_all_series()
    if err:
        raise HTTPException(status_code=503, detail=err)
    tonights = discovery_service.get_tonights_binge(docs, seen_ids=_seen_ids)
    for d in tonights:
        tid = d.get("series_id")
        if tid:
            _seen_ids.add(tid)
    return [_doc_to_summary(d) for d in tonights]


@router.get("/hidden-gems", response_model=List[SeriesSummary])
def hidden_gems():
    docs, err = series_service.get_all_series()
    if err:
        raise HTTPException(status_code=503, detail=err)
    gems = discovery_service.get_hidden_gems(docs)
    return [_doc_to_summary(d) for d in gems]


@router.get("/free-tonight", response_model=List[SeriesSummary])
def free_tonight():
    docs, err = series_service.get_all_series()
    if err:
        raise HTTPException(status_code=503, detail=err)
    free = discovery_service.get_free_to_watch(docs, limit=6)
    return [_doc_to_summary(d) for d in free]


@router.get("/surprise", response_model=SeriesSummary)
def surprise():
    docs, err = series_service.get_all_series()
    if err:
        raise HTTPException(status_code=503, detail=err)
    pick = discovery_service.get_surprise(docs)
    if pick is None:
        raise HTTPException(status_code=404, detail="No series available to surprise you with.")
    return _doc_to_summary(pick)


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
