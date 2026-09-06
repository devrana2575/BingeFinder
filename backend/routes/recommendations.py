"""
backend/routes/recommendations.py
===================================
GET /series/{id}/recommendations
GET /recommendations/personalized
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.dependencies import get_current_user
from backend.schemas.recommendations import RecommendationItem, RecommendationResponse
from backend.services import rec_service, series_service

router = APIRouter()


@router.get("/series/{series_id}/recommendations", response_model=RecommendationResponse)
def series_recommendations(series_id: int):
    source_doc, err = series_service.get_series_by_id(series_id)
    if err:
        raise HTTPException(status_code=404, detail=err)

    recs, rec_err = rec_service.get_recommendations_for_series(series_id)
    if rec_err:
        raise HTTPException(status_code=503, detail=rec_err)

    items = []
    for r in recs:
        why = rec_service.build_why_reasons(source_doc, r)
        items.append(RecommendationItem(
            series_id=r["series_id"],
            title=r.get("title"),
            rating=r.get("rating"),
            genres=r.get("genres", []),
            image=r.get("image"),
            relevance_score=r["relevance_score"],
            why_recommended=why,
        ))

    return RecommendationResponse(
        source_id=series_id,
        source_title=source_doc.get("name") or f"Series #{series_id}",
        recommendations=items,
    )


@router.get("/recommendations/personalized", response_model=List[RecommendationItem])
def personalized_recommendations(
    user_id: Optional[str] = Depends(get_current_user),
    region: Optional[str] = None,
):
    if not user_id:
        raise HTTPException(status_code=401, detail="Login required for personalized recommendations.")

    recs, err = rec_service.get_personalized_recommendations(user_id, region=region)
    if err:
        raise HTTPException(status_code=503, detail=err)

    return [
        RecommendationItem(
            series_id=r["series_id"],
            title=r.get("title"),
            rating=r.get("rating"),
            genres=r.get("genres", []),
            image=r.get("image"),
            relevance_score=r["relevance_score"],
        )
        for r in recs
    ]
