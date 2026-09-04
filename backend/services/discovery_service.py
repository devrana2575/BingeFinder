"""
backend/services/discovery_service.py
=======================================
Wraps vibe-based discovery logic from backend.services.vibes and provides
fresh-pick / hidden-gem / free-to-watch helpers over a series catalog.
"""

import random
from typing import Any, Dict, List, Optional

from backend.services.vibes import pick_surprise, filter_by_vibe, VIBES, SURPRISE_KEY


def get_tonights_binge(docs: List[Dict], seen_ids: Optional[set] = None, limit: int = 6) -> List[Dict]:
    """Fresh discovery picks."""
    seen_ids = seen_ids or set()
    qualified = [
        d for d in docs
        if isinstance(d.get("rating"), (int, float))
        and d["rating"] >= 7.0
        and (d.get("image_medium") or d.get("image_original"))
        and d.get("series_id") not in seen_ids
    ]
    if not qualified:
        qualified = [
            d for d in docs
            if isinstance(d.get("rating"), (int, float))
            and d["rating"] >= 7.0
            and (d.get("image_medium") or d.get("image_original"))
        ]

    for d in qualified:
        d["_random_score"] = random.random()

    qualified.sort(
        key=lambda d: (d["_random_score"] * 0.4 + (d["rating"] / 10.0) * 0.3 + 0.3),
        reverse=True,
    )

    selected = []
    genre_count: Dict[str, int] = {}
    lang_count: Dict[str, int] = {}
    for d in qualified:
        genres = d.get("genres") or []
        lang = d.get("language") or "Unknown"
        genre_ok = all(genre_count.get(g, 0) < 2 for g in genres) if genres else True
        lang_ok = lang_count.get(lang, 0) < 1
        if genre_ok and lang_ok:
            selected.append(d)
            for g in genres:
                genre_count[g] = genre_count.get(g, 0) + 1
            lang_count[lang] = lang_count.get(lang, 0) + 1
        if len(selected) >= limit:
            break
    return selected


def get_hidden_gems(docs: List[Dict], limit: int = 8) -> List[Dict]:
    gems = [
        d for d in docs
        if isinstance(d.get("rating"), (int, float))
        and d["rating"] >= 7.5
        and (not isinstance(d.get("weight"), (int, float)) or d["weight"] < 500)
    ]
    return sorted(gems, key=lambda d: d["rating"], reverse=True)[:limit]


def get_surprise(docs: List[Dict]) -> Optional[Dict]:
    return pick_surprise(docs)


def get_vibe_filtered(docs: List[Dict], vibe_key: str, limit: int = 12) -> List[Dict]:
    return filter_by_vibe(docs, vibe_key, limit=limit)


def get_vibes_info() -> Dict[str, Dict]:
    info = {}
    for k, v in VIBES.items():
        info[k] = {"emoji": v["emoji"], "label": v["label"]}
    info[SURPRISE_KEY] = {"emoji": "🎲", "label": "Surprise me"}
    return info


def get_free_to_watch(docs: List[Dict], limit: int = 6) -> List[Dict]:
    """Free/ads provider availability for sampled series."""
    try:
        from config import get_tmdb_api_key
        get_tmdb_api_key()
    except Exception:
        return []

    from backend.services.watch_provider_cache import _cached_watch_providers

    rated = [d for d in docs if isinstance(d.get("rating"), (int, float)) and d["rating"] >= 6.0]
    if not rated:
        rated = [d for d in docs if isinstance(d.get("rating"), (int, float))]
    sample_size = min(30, len(rated))
    sampled = random.sample(rated, sample_size) if sample_size > 0 else []

    free_series = []
    for doc in sampled:
        if len(free_series) >= limit:
            break
        try:
            providers_data = _cached_watch_providers(
                doc.get("series_id"),
                doc.get("imdb_id"),
                doc.get("name", ""),
                doc.get("premiered"),
            )
        except Exception:
            continue
        if not providers_data or not providers_data.get("providers"):
            continue
        providers = providers_data["providers"]
        free = providers.get("free") or []
        ads = providers.get("ads") or []
        if free or ads:
            entry = dict(doc)
            entry["_free_providers"] = (free + ads)[:3]
            free_series.append(entry)

    return free_series
