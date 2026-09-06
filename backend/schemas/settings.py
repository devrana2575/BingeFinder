"""
backend/schemas/settings.py
============================
Pydantic schemas for user preferences / settings.
"""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from regions import DEFAULT_REGION, SUPPORTED_REGIONS

_SUPPORTED_REGION_CODES = {r["code"] for r in SUPPORTED_REGIONS}

# Curated language list for the settings UI (kept compact and stable).
SUPPORTED_LANGUAGES = [
    "English", "Hindi", "Spanish", "French", "German", "Korean",
    "Japanese", "Chinese", "Italian", "Portuguese", "Arabic", "Russian",
]

# Shared with the recommender's feature space.
PREFERRED_GENRES = [
    "Action", "Adventure", "Animation", "Comedy", "Crime", "Drama",
    "Fantasy", "Horror", "Mystery", "Romance", "Science-Fiction",
    "Thriller", "Documentary", "Family", "History", "War",
]

MAX_LANGUAGES = 5
MAX_GENRES = 8
MAX_SERVICES = 15


class UserSettings(BaseModel):
    """User preferences used to personalise discovery and availability."""

    region: Optional[str] = Field(default=None, description="ISO 3166-1 region code")
    languages: List[str] = Field(default_factory=list, max_length=MAX_LANGUAGES)
    genres: List[str] = Field(default_factory=list, max_length=MAX_GENRES)
    services: List[int] = Field(default_factory=list, max_length=MAX_SERVICES)

    @field_validator("region")
    @classmethod
    def _validate_region(cls, value: Optional[str]) -> str:
        from regions import normalize_region
        if value is None:
            return DEFAULT_REGION
        return normalize_region(value)

    @field_validator("languages")
    @classmethod
    def _dedupe_languages(cls, values: List[str]) -> List[str]:
        seen = set()
        cleaned = []
        for v in values or []:
            key = str(v).strip()
            low = key.lower()
            if not low or low in seen:
                continue
            seen.add(low)
            cleaned.append(key)
        return cleaned[:MAX_LANGUAGES]

    @field_validator("genres")
    @classmethod
    def _dedupe_genres(cls, values: List[str]) -> List[str]:
        seen = set()
        cleaned = []
        for v in values or []:
            key = str(v).strip()
            low = key.lower()
            if not low or low in seen:
                continue
            seen.add(low)
            cleaned.append(key)
        return cleaned[:MAX_GENRES]

    @field_validator("services")
    @classmethod
    def _clean_services(cls, values: List[int]) -> List[int]:
        seen = set()
        cleaned: List[int] = []
        for v in values or []:
            try:
                val = int(v)
            except Exception:
                continue
            if val in seen:
                continue
            seen.add(val)
            cleaned.append(val)
        return cleaned[:MAX_SERVICES]