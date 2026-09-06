"""
backend/routes/users.py
=========================
GET/POST/DELETE /user/watchlist/{id}
GET/POST/DELETE /user/likes/{id}
GET/POST /user/recently-viewed
GET/PUT /user/settings
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.dependencies import get_current_user, require_auth
from backend.schemas.series import SeriesSummary
from backend.schemas.settings import UserSettings
from backend.services import user_service
from api.tmdb import build_poster_url

router = APIRouter()


def _doc_to_summary(doc: dict) -> SeriesSummary:
    return SeriesSummary(
        series_id=doc["series_id"],
        name=doc.get("name") or "Untitled",
        rating=doc.get("rating"),
        genres=doc.get("genres") or [],
        image=build_poster_url(doc.get("image_medium") or doc.get("image_original")),
        language=doc.get("language"),
        premiered=doc.get("premiered"),
        status=doc.get("status"),
    )


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------

@router.get("/watchlist", response_model=List[SeriesSummary])
def get_watchlist(user_id: str = Depends(require_auth)):
    docs, err = user_service.get_watchlist(user_id)
    if err:
        raise HTTPException(status_code=503, detail=err)
    return [_doc_to_summary(d) for d in docs]


@router.post("/watchlist/{series_id}")
def add_to_watchlist(series_id: int, user_id: str = Depends(require_auth)):
    ok, err = user_service.add_to_watchlist(user_id, series_id)
    if err:
        raise HTTPException(status_code=503, detail=err)
    return {"status": "added"}


@router.delete("/watchlist/{series_id}")
def remove_from_watchlist(series_id: int, user_id: str = Depends(require_auth)):
    ok, err = user_service.remove_from_watchlist(user_id, series_id)
    if err:
        raise HTTPException(status_code=503, detail=err)
    return {"status": "removed"}


# ---------------------------------------------------------------------------
# Likes
# ---------------------------------------------------------------------------

@router.get("/likes", response_model=List[SeriesSummary])
def get_likes(user_id: str = Depends(require_auth)):
    docs, err = user_service.get_likes(user_id)
    if err:
        raise HTTPException(status_code=503, detail=err)
    return [_doc_to_summary(d) for d in docs]


@router.post("/likes/{series_id}")
def like_series(series_id: int, user_id: str = Depends(require_auth)):
    ok, err = user_service.like_series(user_id, series_id)
    if err:
        raise HTTPException(status_code=503, detail=err)
    return {"status": "liked"}


@router.delete("/likes/{series_id}")
def unlike_series(series_id: int, user_id: str = Depends(require_auth)):
    ok, err = user_service.unlike_series(user_id, series_id)
    if err:
        raise HTTPException(status_code=503, detail=err)
    return {"status": "unliked"}


# ---------------------------------------------------------------------------
# Recently Viewed
# ---------------------------------------------------------------------------

@router.get("/recently-viewed", response_model=List[SeriesSummary])
def get_recently_viewed(user_id: str = Depends(require_auth)):
    docs, err = user_service.get_recently_viewed(user_id)
    if err:
        raise HTTPException(status_code=503, detail=err)
    return [_doc_to_summary(d) for d in docs]


@router.post("/recently-viewed/{series_id}")
def record_view(series_id: int, user_id: str = Depends(require_auth)):
    user_service.record_view(user_id, series_id)
    return {"status": "recorded"}


# ---------------------------------------------------------------------------
# Settings / preferences
# ---------------------------------------------------------------------------

@router.get("/settings")
def get_settings(user_id: str = Depends(require_auth)):
    settings, err = user_service.get_settings(user_id)
    if err:
        raise HTTPException(status_code=503, detail=err)
    return settings


@router.put("/settings")
def update_settings(
    payload: UserSettings, user_id: str = Depends(require_auth)
):
    ok, err = user_service.update_settings(user_id, payload.model_dump())
    if err:
        raise HTTPException(status_code=503, detail=err)
    return {"status": "saved", "settings": payload.model_dump()}
