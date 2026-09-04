"""
backend/services/rec_service.py
=================================
Wraps the existing recommendation engine with the adaptive ranking pipeline.

Pipeline:
    Candidate Generator (existing hybrid model)
        ↓
    Quality Threshold
        ↓
    Context Feature Builder (from user interaction history)
        ↓
    Adaptive Ranker (LinUCB contextual bandit)
        ↓
    Diversity Re-ranking
        ↓
    Final Top-K Results (with both relevance_score and adaptive_score)

The content model answers: "What series are similar?"
The adaptive ranker answers: "Which of these relevant series is this user most likely to engage with?"
"""

from typing import Any, Dict, List, Optional, Tuple

import numpy as np


# Genre and language feature spaces (shared with recommender/adaptive.py)
_ALL_GENRES = [
    "Action", "Adventure", "Animation", "Comedy", "Crime", "Drama",
    "Fantasy", "Horror", "Mystery", "Romance", "Science-Fiction",
    "Thriller", "Western", "Documentary", "Family", "History",
    "Musical", "War", "Biography", "Talk-Show",
]
_TOP_LANGUAGES = ["English", "Japanese", "Spanish", "Korean", "Hindi", "French", "German"]


def get_recommendations_for_series(
    series_id: int, top_n: int = 8
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Call the existing hybrid recommender (content-only, no adaptation)."""
    try:
        from recommender.exceptions import ModelNotBuiltError, SeriesNotFoundError, RecommenderError
        from recommender.recommend import get_recommendations, RELEVANCE_FLOOR
    except Exception as exc:
        return [], f"Recommendation engine could not be loaded: {exc}"

    try:
        # RELEVANCE_FLOOR == MIN_RECOMMENDATION_SCORE (absolute, distribution-derived).
        return get_recommendations(series_id, top_n=top_n, min_relevance=RELEVANCE_FLOOR), None
    except ModelNotBuiltError:
        return [], "The recommendation model hasn't been built yet. Run `python -m recommender.build_model` first."
    except SeriesNotFoundError:
        return [], "This series isn't in the recommendation model yet."
    except RecommenderError as exc:
        return [], f"Could not generate recommendations: {exc}"


def get_personalized_recommendations(
    user_id: str, top_n: int = 12
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Generate personalized recommendations with adaptive ranking.

    Pipeline:
        1. Build user preference vector from likes/watchlist/recently-viewed
        2. Generate candidate pool via hybrid model
        3. Apply adaptive ranking using contextual bandit
        4. Return top-K with both relevance and adaptive scores
    """
    try:
        from recommender.exceptions import ModelNotBuiltError
        from recommender.recommend import load_model, _genre_jaccard, W_SEMANTIC, W_TFIDF, W_GENRE, W_QUALITY, RELEVANCE_FLOOR, _rank_and_filter
        from sklearn.metrics.pairwise import cosine_similarity
    except Exception as exc:
        return [], f"Recommendation engine could not be loaded: {exc}"

    from backend.services.series_service import _connect

    _WEIGHT_LIKED = 3.0
    _WEIGHT_WATCHLIST = 2.0
    _WEIGHT_RECENTLY_VIEWED = 1.0

    manager, err = _connect()
    if err:
        return [], err

    weighted_ids: Dict[int, float] = {}
    try:
        from database.watchlist import WatchlistManager
        from database.likes import LikesManager
        from database.recently_viewed import RecentlyViewedManager

        wl = WatchlistManager(manager)
        for doc in wl.get_watchlist(user_id):
            sid = doc.get("series_id")
            if sid:
                weighted_ids[sid] = max(weighted_ids.get(sid, 0), _WEIGHT_WATCHLIST)

        lm = LikesManager(manager)
        for lid in lm.get_liked_series_ids(user_id):
            weighted_ids[lid] = max(weighted_ids.get(lid, 0), _WEIGHT_LIKED)

        rvm = RecentlyViewedManager(manager)
        for rid in rvm.get_recently_viewed_ids(user_id):
            weighted_ids[rid] = max(weighted_ids.get(rid, 0), _WEIGHT_RECENTLY_VIEWED)
    except Exception:
        pass
    finally:
        manager.close()

    if not weighted_ids:
        return [], None

    try:
        bundle = load_model()
    except ModelNotBuiltError:
        return [], "The recommendation model hasn't been built yet."

    series_ids = bundle["series_ids"]
    tfidf_matrix = bundle["tfidf_matrix"]
    semantic_embeddings = bundle.get("semantic_embeddings")
    metadata = bundle["metadata"]

    user_rows = []
    user_weights = []
    for sid, weight in weighted_ids.items():
        if sid in series_ids:
            row_idx = series_ids.index(sid)
            user_rows.append(row_idx)
            user_weights.append(weight)

    if not user_rows:
        return [], None

    weights = np.array(user_weights, dtype=np.float32)
    weights = weights / weights.sum()

    user_tfidf = np.asarray(tfidf_matrix[user_rows].multiply(weights[:, np.newaxis]).mean(axis=0))

    user_semantic = None
    if semantic_embeddings is not None and user_rows:
        user_semantic = np.average(semantic_embeddings[user_rows], axis=0, weights=weights)

    interacted_set = set(weighted_ids.keys())
    all_rows = np.arange(len(series_ids))
    mask = np.array([sid not in interacted_set for sid in series_ids])
    candidate_rows = all_rows[mask]

    if len(candidate_rows) == 0:
        return [], None

    if user_semantic is not None:
        sem_scores = np.dot(user_semantic, semantic_embeddings[candidate_rows].T).flatten()
    else:
        sem_scores = np.zeros(len(candidate_rows))
    tfidf_scores = cosine_similarity(user_tfidf, tfidf_matrix[candidate_rows]).flatten()

    genre_scores = np.zeros(len(candidate_rows), dtype=np.float32)
    quality_scores = np.zeros(len(candidate_rows), dtype=np.float32)
    for i, row in enumerate(candidate_rows):
        cand_id = series_ids[row]
        cand_meta = metadata.get(cand_id, {})
        cand_genres = cand_meta.get("genres_set", set())
        genre_scores[i] = _genre_jaccard(set(), cand_genres)
        rating = cand_meta.get("rating")
        quality_scores[i] = (rating / 10.0) if isinstance(rating, (int, float)) else 0.5

    hybrid = W_SEMANTIC * sem_scores + W_TFIDF * tfidf_scores + W_GENRE * genre_scores + W_QUALITY * quality_scores

    # Rank with the same calibrated threshold + elbow + diversity ordering as
    # the per-series path (threshold first, then diversity).
    diverse_indices, _cutoff = _rank_and_filter(
        hybrid, candidate_rows, series_ids, metadata,
        top_n=top_n * 2,  # extra candidates for the adaptive reranking layer
        min_relevance=RELEVANCE_FLOOR,
        use_elbow=True,
    )

    # Build candidate list with component scores
    candidates = []
    for idx in diverse_indices:
        score = float(hybrid[idx])
        row = candidate_rows[idx]
        cand_id = series_ids[row]
        cand_meta = metadata.get(cand_id, {})
        candidates.append({
            "series_id": cand_id,
            "title": cand_meta.get("title"),
            "rating": cand_meta.get("rating"),
            "genres": cand_meta.get("genres", []),
            "image": cand_meta.get("image"),
            "network": cand_meta.get("channel_names", [None])[0] if cand_meta.get("channel_names") else None,
            "relevance_score": round(score, 4),
        })

    # --- Adaptive Ranking Layer ---
    try:
        from recommender.adaptive import adaptive_rerank

        # Get reward matrix from interaction events
        reward_matrix = _get_reward_matrix(user_id)

        # Get free provider counts if available
        free_counts = _get_free_provider_counts([c["series_id"] for c in candidates])

        if reward_matrix:
            candidates = adaptive_rerank(
                candidates=candidates,
                reward_matrix=reward_matrix,
                series_metadata=metadata,
                all_genres=_ALL_GENRES,
                top_languages=_TOP_LANGUAGES,
                free_provider_counts=free_counts,
            )
    except Exception as exc:
        logger.warning("Adaptive reranking failed, using baseline: %s", exc)

    return candidates[:top_n], None


def _get_reward_matrix(user_id: str) -> List[Dict[str, Any]]:
    """Get reward matrix from MongoDB for the adaptive ranker."""
    try:
        from database.mongo_client import MongoDBManager
        manager = MongoDBManager()
        try:
            from database.interaction_events import InteractionEventManager
            iem = InteractionEventManager(manager)
            return iem.get_reward_matrix(user_id)
        finally:
            manager.close()
    except Exception:
        return []


def _get_free_provider_counts(series_ids: List[int]) -> Dict[int, int]:
    """Get free provider counts for a list of series. Best-effort."""
    try:
        from api.watch_providers import get_provider_page_url
        from backend.services.watch_provider_cache import _cached_watch_providers
        counts = {}
        for sid in series_ids[:10]:  # Limit to avoid API rate limits
            try:
                providers = _cached_watch_providers(sid, None, "", None)
                if providers and providers.get("providers"):
                    free = (providers["providers"].get("free") or []) + (providers["providers"].get("ads") or [])
                    counts[sid] = len(free)
            except Exception:
                counts[sid] = 0
        return counts
    except Exception:
        return {}


def build_why_reasons(source_doc: dict, rec: dict) -> list:
    """Same logic as backend.services.explain.build_why_reasons."""
    from backend.services.explain import build_why_reasons as _build
    return _build(source_doc, rec)


# Module-level logger
from utils.logger import get_logger
logger = get_logger(__name__)
