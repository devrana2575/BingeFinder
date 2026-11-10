"""
backend/routes/events.py
==========================
POST /events/recommendation  — record user interaction event
GET  /events/status           — adaptive ranker status for current user
"""

from fastapi import APIRouter, Depends, HTTPException

from backend.dependencies import require_auth
from backend.schemas.events import RecommendationEventRequest, EventResponse, AdaptiveStatusResponse
from backend.services import event_service

router = APIRouter()


@router.post("/recommendation", response_model=EventResponse)
def record_recommendation_event(
    req: RecommendationEventRequest,
    user_id: str = Depends(require_auth),
):
    """
    Record a user interaction event.

    The reward is computed server-side from event_type — never from the client.
    """
    reward, err = event_service.record_event(
        user_id=user_id,
        event_type=req.event_type,
        series_id=req.series_id,
        source_series_id=req.source_series_id,
        session_id=req.session_id,
        position=req.position,
        context=req.context,
    )
    if err:
        raise HTTPException(status_code=500, detail=err)

    return EventResponse(status="recorded", reward=reward)


@router.get("/status", response_model=AdaptiveStatusResponse)
def adaptive_status(user_id: str = Depends(require_auth)):
    """Get the adaptive ranker status for the current user."""
    result = event_service.get_adaptive_status(user_id)
    return AdaptiveStatusResponse(**result)
