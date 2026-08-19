"""
ui/vibes.py
=============
"WHAT'S YOUR VIBE?" mood picker + "BINGE SHUFFLE" random pick.

Pure, in-memory helpers over the catalog already returned by
`ui.data_access.load_all_series()`. No new database queries, no new
ML model, no new dependency: a mood is just a curated set of TVmaze
`genres` values, and "Surprise Me" is `random.choice()` over the
(optionally vibe-filtered) catalog — always a real MongoDB document,
never a hardcoded/fake title.

This module is standalone by design: streamlit_app.py and
ui/components.py only ever call the functions below through their
return values (a filtered list, or a chosen document/None). Deleting
this file and the vibe-selector block in streamlit_app.py's
render_home() is enough to remove the feature — Search, Discover,
Series Details and Recommendations don't import or depend on it.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

# Mood -> the existing TVmaze genre strings we already store per series
# (see database/update_mongo.py / recommender/preprocess.py). No new
# taxonomy, no scoring model — just a genre grouping.
VIBES: Dict[str, Dict[str, Any]] = {
    "hype": {
        "emoji": "🔥",
        "label": "Can't stop watching",
        "genres": {"Action", "Adventure", "Crime", "Thriller", "Sports"},
    },
    "think": {
        "emoji": "🧠",
        "label": "Make me think",
        "genres": {"Science-Fiction", "Mystery", "History", "Legal", "Espionage", "Anthology"},
    },
    "dark": {
        "emoji": "🌑",
        "label": "Dark & disturbing",
        "genres": {"Horror", "Thriller", "Crime", "Supernatural", "War"},
    },
    "chill": {
        "emoji": "😂",
        "label": "Just chill",
        "genres": {"Comedy", "Family", "Food", "Music", "Travel", "Children"},
    },
    "feels": {
        "emoji": "❤️",
        "label": "Need feelings",
        "genres": {"Romance", "Drama", "Family"},
    },
    "mindblown": {
        "emoji": "🤯",
        "label": "Mind = blown",
        "genres": {"Science-Fiction", "Fantasy", "Mystery", "Supernatural"},
    },
}

SURPRISE_KEY = "surprise"
SURPRISE_VIBE: Dict[str, str] = {"emoji": "🎲", "label": "Surprise me"}


def vibe_options() -> List[Tuple[str, Dict[str, Any]]]:
    """Ordered (key, vibe) pairs for the selector — moods first, Surprise Me last."""
    return list(VIBES.items()) + [(SURPRISE_KEY, SURPRISE_VIBE)]


def filter_by_vibe(docs: List[Dict[str, Any]], vibe_key: str, limit: int = 12) -> List[Dict[str, Any]]:
    """
    Series from the already-loaded catalog whose existing `genres` list
    overlaps this vibe's genre set, best-rated first.

    Falls back to the catalog's own top-rated titles if nothing in the
    current catalog happens to match this vibe's genres yet, so the
    section is never empty just because of small/incomplete data.
    """
    vibe = VIBES.get(vibe_key)
    if vibe is None:
        return []

    wanted = vibe["genres"]
    matches = [d for d in docs if wanted.intersection(d.get("genres") or [])]
    pool = matches if matches else docs

    def sort_key(d: Dict[str, Any]):
        rating = d.get("rating") if isinstance(d.get("rating"), (int, float)) else -1
        weight = d.get("weight") if isinstance(d.get("weight"), (int, float)) else -1
        return (rating, weight)

    return sorted(pool, key=sort_key, reverse=True)[:limit]


def pick_surprise(docs: List[Dict[str, Any]], vibe_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Binge Shuffle: randomly pick one real series document from the
    catalog. If a mood vibe is currently active, shuffle within that
    vibe's matches (so the surprise still fits the mood) whenever there
    are any; otherwise shuffle the whole catalog. Returns None only if
    the catalog has nothing pickable (e.g. it's empty).
    """
    pool = docs
    if vibe_key and vibe_key in VIBES:
        vibe_matches = filter_by_vibe(docs, vibe_key, limit=max(len(docs), 1))
        if vibe_matches:
            pool = vibe_matches

    candidates = [d for d in pool if d.get("tvmaze_id") is not None]
    if not candidates:
        return None
    return random.choice(candidates)
