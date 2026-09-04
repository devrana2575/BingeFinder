"""
backend/schemas/events.py
===========================
Pydantic schemas for event endpoints.
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel


class RecommendationEventRequest(BaseModel):
    series_id: int
    source_series_id: Optional[int] = None
    event_type: str
    position: Optional[int] = None
    session_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class EventResponse(BaseModel):
    status: str
    reward: float


class AdaptiveStatusResponse(BaseModel):
    status: str  # cold_start | collecting_data | trained
    event_count: int
    reward_matrix_size: int
