"""
backend/services/discovery_service.py
=======================================
Wraps vibe-based discovery logic from backend.services.vibes and provides
fresh-pick / hidden-gem / free-to-watch helpers over a series catalog.
"""

import datetime
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


def get_surprise(
    docs: List[Dict],
    vibe_key: Optional[str] = None,
    user_signals: Optional[Dict[str, Any]] = None,
    rng: Optional[random.Random] = None,
) -> Optional[Dict]:
    return pick_surprise(docs, vibe_key=vibe_key, user_signals=user_signals, rng=rng)


def _premiere_year(doc: Dict) -> Optional[int]:
    """Extract an integer premiere year from a document, if present."""
    value = doc.get("premiered") or doc.get("ended")
    if isinstance(value, str) and len(value) >= 4 and value[:4].isdigit():
        return int(value[:4])
    return None


def _index_score(doc: Dict) -> float:
    """Blended popularity + quality score in [0, 1] used to rank index rails."""
    rating = doc.get("rating") if isinstance(doc.get("rating"), (int, float)) else 0.0
    weight = doc.get("weight") if isinstance(doc.get("weight"), (int, float)) else 0.0
    popularity = min(max(weight, 0.0), 500.0) / 500.0
    quality = min(max(rating, 0.0), 10.0) / 10.0
    return 0.6 * popularity + 0.4 * quality


def get_trending(docs: List[Dict], seen_ids: Optional[set] = None, limit: int = 6) -> List[Dict]:
    """
    Trending rail: highest blended popularity+quality first, diversified
    lightly across genre/language so the row never becomes one genre wall.
    """
    seen_ids = seen_ids or set()
    pool = [
        d for d in docs
        if d.get("series_id") not in seen_ids
        and (d.get("image_medium") or d.get("image_original"))
    ]
    pool.sort(key=_index_score, reverse=True)
    return _diversify(pool, limit)


def get_new_and_noteworthy(docs: List[Dict], limit: int = 6, within_years: int = 2, min_rating: float = 6.5) -> List[Dict]:
    """
    New & Noteworthy rail: well-received titles that premiered within the
    last few years, best-rated first. Falls back to the overall best-rated
    series when nothing sufficiently recent qualifies yet.
    """
    current_year = datetime.datetime.now().year
    cutoff = current_year - max(within_years, 0)

    pool = [
        d for d in docs
        if (d.get("image_medium") or d.get("image_original"))
        and isinstance(d.get("rating"), (int, float))
        and d["rating"] >= min_rating
        and (_premiere_year(d) or 0) >= cutoff
    ]
    if not pool:
        pool = [
            d for d in docs
            if (d.get("image_medium") or d.get("image_original"))
            and isinstance(d.get("rating"), (int, float))
            and d["rating"] >= min_rating
        ]

    def sort_key(d: Dict):
        rating = d.get("rating") if isinstance(d.get("rating"), (int, float)) else 0.0
        weight = d.get("weight") if isinstance(d.get("weight"), (int, float)) else 0.0
        return (rating, weight)

    pool.sort(key=sort_key, reverse=True)
    return _diversify(pool, limit)


def _diversify(sorted_pool: List[Dict], limit: int, max_genre: int = 2, max_lang: int = 1) -> List[Dict]:
    """
    Walk a relevance/popularity-sorted pool in order and accept titles while
    each genre appears at most `max_genre` times and each language at most
    `max_lang` times. Relevance order is preserved: we never push a weaker
    title above a stronger one to force diversity.
    """
    if not sorted_pool:
        return []
    selected: List[Dict] = []
    genre_count: Dict[str, int] = {}
    lang_count: Dict[str, int] = {}
    for d in sorted_pool:
        genres = d.get("genres") or []
        lang = d.get("language") or "Unknown"
        genre_ok = all(genre_count.get(g, 0) < max_genre for g in genres) if genres else True
        lang_ok = lang_count.get(lang, 0) < max_lang
        if genre_ok and lang_ok:
            selected.append(d)
            for g in genres:
                genre_count[g] = genre_count.get(g, 0) + 1
            lang_count[lang] = lang_count.get(lang, 0) + 1
        if len(selected) >= limit:
            break
    return selected


def get_vibe_filtered(docs: List[Dict], vibe_key: str, limit: int = 12) -> List[Dict]:
    return filter_by_vibe(docs, vibe_key, limit=limit)


def get_vibes_info() -> Dict[str, Dict]:
    info = {}
    for k, v in VIBES.items():
        info[k] = {"label": v["label"]}
    info[SURPRISE_KEY] = {"label": "Surprise me"}
    return info


def get_free_to_watch(docs: List[Dict], limit: int = 6, region: Optional[str] = None) -> List[Dict]:
    """Free/ads provider availability for sampled series, scoped to a region."""
    try:
        from config import is_tmdb_configured
        if not is_tmdb_configured():
            return []
    except Exception:
        return []

    from regions import normalize_region
    from backend.services.watch_provider_cache import _cached_watch_providers

    effective_region = normalize_region(region)

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
                region=effective_region,
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
            # Store clean product-level fields: a nominal tier (highest
            # priority free type present) plus the platform names.
            entry["_free_tier"] = "free" if free else "free_with_ads"
            entry["_free_providers"] = (free + ads)[:3]
            entry["_free_provider_names"] = [
                (p.get("provider_name") or "Unknown") for p in (free + ads)[:3]
            ]
            free_series.append(entry)

    return free_series
