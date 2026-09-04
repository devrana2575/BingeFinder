"""
backend/schemas/recommendations.py
====================================
Pydantic schemas for recommendation endpoints.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel


class RecommendationItem(BaseModel):
    series_id: int
    title: Optional[str] = None
    rating: Optional[float] = None
    genres: List[str] = []
    image: Optional[str] = None
    relevance_score: float
    why_recommended: List[str] = []


class RecommendationResponse(BaseModel):
    source_id: int
    source_title: str
    recommendations: List[RecommendationItem]
