"""
recommender/recommend.py
==========================
Loads the saved hybrid recommendation model artifact and serves
recommendations using a multi-signal relevance score.

The hybrid score combines:
    - Semantic similarity (sentence-transformers embeddings)
    - TF-IDF similarity (existing content-based)
    - Genre compatibility (Jaccard similarity)
    - Quality signal (normalized rating)

After ranking, weak candidates are filtered and diversity is applied
to avoid recommending 10 nearly identical copies.

Does not touch MongoDB: everything needed was already captured by
recommender/build_model.py.
"""

import os as _os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import joblib
from sklearn.metrics.pairwise import cosine_similarity

if __name__ == "__main__" and __package__ is None:
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from recommender.build_model import MODEL_PATH
from recommender.exceptions import ModelNotBuiltError, SeriesNotFoundError
from utils.logger import get_logger

logger = get_logger(__name__)

# Hybrid scoring weights — initial values, tunable.
W_SEMANTIC = 0.50
W_TFIDF = 0.20
W_GENRE = 0.20
W_QUALITY = 0.10

# ---------------------------------------------------------------------------
# Ranking thresholds (configurable via environment; defaults calibrated from
# the measured hybrid-score distribution of the real 3,534-series catalog).
#
# The adaptive cutoff used is:
#     cutoff = max(MIN_RECOMMENDATION_SCORE,
#                  RECOMMENDATION_ELBOW_FACTOR * top_candidate_score)
#
# MIN_RECOMMENDATION_SCORE is an absolute relevance floor derived from the
# real score distribution (90th percentile = 0.28, NOT an arbitrary "60%").
# It drops the noise tail of weak matches (the measured median pair score is
# only 0.165, so admitting everything near the old 0.15 floor pulled in
# unrelated titles).
#
# RECOMMENDATION_ELBOW_FACTOR preserves a proportional band around the
# strongest match so a series with no strong candidates still returns its
# relatively-best few options rather than an empty list.
# ---------------------------------------------------------------------------
MIN_RECOMMENDATION_SCORE = float(_os.getenv("MIN_RECOMMENDATION_SCORE", "0.28"))
RECOMMENDATION_ELBOW_FACTOR = float(_os.getenv("RECOMMENDATION_ELBOW_FACTOR", "0.55"))

# Legacy alias kept for backwards-compat with imports (rec_service, tests).
RELEVANCE_FLOOR = MIN_RECOMMENDATION_SCORE

# Diversity: max recommendations from the same genre cluster or network.
_MAX_PER_GENRE = 3
_MAX_PER_NETWORK = 2

# Kept in-process so repeated calls don't re-read the artifact file from disk.
_model_cache: Optional[Dict[str, Any]] = None
_model_cache_path: Optional[Path] = None


def load_model(model_path: Optional[Path] = None, force_reload: bool = False) -> Dict[str, Any]:
    """
    Load the saved recommendation model artifact, caching it in memory.

    Args:
        model_path: Optional override for the artifact path.
        force_reload: If True, bypass the in-memory cache.

    Returns:
        The model bundle dict.

    Raises:
        ModelNotBuiltError: If the artifact file doesn't exist or fails to load.
    """
    global _model_cache, _model_cache_path

    path = Path(model_path) if model_path else MODEL_PATH

    if not force_reload and _model_cache is not None and _model_cache_path == path:
        return _model_cache

    if not path.exists():
        raise ModelNotBuiltError(
            f"No recommendation model found at {path}. "
            f"Build it first with `python -m recommender.build_model`."
        )

    try:
        bundle = joblib.load(path)
    except Exception as exc:
        logger.error("Failed to load recommendation model from %s: %s", path, exc)
        raise ModelNotBuiltError(f"Failed to load recommendation model from {path}: {exc}") from exc

    _model_cache = bundle
    _model_cache_path = path
    return bundle


def _genre_jaccard(genres_a: set, genres_b: set) -> float:
    """Jaccard similarity between two genre sets."""
    if not genres_a and not genres_b:
        return 0.0
    intersection = len(genres_a & genres_b)
    union = len(genres_a | genres_b)
    return intersection / union if union > 0 else 0.0


def _compute_hybrid_scores(
    target_idx: int,
    tfidf_matrix,
    semantic_embeddings: np.ndarray,
    series_ids: List[int],
    metadata: Dict[int, Dict[str, Any]],
    candidate_rows: np.ndarray,
) -> np.ndarray:
    """
    Compute hybrid relevance scores for a set of candidate rows.

    Returns an array of hybrid scores aligned with candidate_rows.
    """
    # TF-IDF cosine similarities (vectorized, single matrix multiply)
    tfidf_scores = cosine_similarity(
        tfidf_matrix[target_idx], tfidf_matrix[candidate_rows]
    ).flatten()

    # Semantic cosine similarities (dot product since embeddings are L2-normalized)
    sem_scores = np.dot(
        semantic_embeddings[target_idx], semantic_embeddings[candidate_rows].T
    ).flatten()

    # Genre and quality scores (per-candidate loop is fine for the filtered set)
    target_id = series_ids[target_idx]
    target_meta = metadata.get(target_id, {})
    target_genres = target_meta.get("genres_set", set())

    genre_scores = np.zeros(len(candidate_rows), dtype=np.float32)
    quality_scores = np.zeros(len(candidate_rows), dtype=np.float32)

    for i, row in enumerate(candidate_rows):
        cand_id = series_ids[row]
        cand_meta = metadata.get(cand_id, {})
        cand_genres = cand_meta.get("genres_set", set())
        genre_scores[i] = _genre_jaccard(target_genres, cand_genres)

        rating = cand_meta.get("rating")
        quality_scores[i] = (rating / 10.0) if isinstance(rating, (int, float)) else 0.5

    hybrid = (
        W_SEMANTIC * sem_scores
        + W_TFIDF * tfidf_scores
        + W_GENRE * genre_scores
        + W_QUALITY * quality_scores
    )

    return hybrid


def _apply_diversity(
    ranked_indices: np.ndarray,
    candidate_rows: np.ndarray,
    scores: np.ndarray,
    series_ids: List[int],
    metadata: Dict[int, Dict[str, Any]],
) -> List[int]:
    """
    Apply light diversity re-ranking. Returns row indices in final order.

    Relevance remains primary — diversity only demotes, never promotes.
    Limits: max _MAX_PER_GENRE per genre, max _MAX_PER_NETWORK per network.
    """
    genre_counts: Dict[str, int] = {}
    network_counts: Dict[str, int] = {}
    result: List[int] = []

    for idx in ranked_indices:
        row = candidate_rows[idx]
        cand_id = series_ids[row]
        cand_meta = metadata.get(cand_id, {})
        cand_genres = cand_meta.get("genres", [])
        cand_networks = cand_meta.get("channel_names", [])

        # Check genre diversity
        genre_ok = True
        for g in cand_genres:
            if genre_counts.get(g, 0) >= _MAX_PER_GENRE:
                genre_ok = False
                break
        if not genre_ok:
            continue

        # Check network diversity
        network_ok = True
        for n in cand_networks:
            if network_counts.get(n, 0) >= _MAX_PER_NETWORK:
                network_ok = False
                break
        if not network_ok:
            continue

        # Accept this candidate
        result.append(idx)
        for g in cand_genres:
            genre_counts[g] = genre_counts.get(g, 0) + 1
        for n in cand_networks:
            network_counts[n] = network_counts.get(n, 0) + 1

    return result


def _adaptive_cutoff(top_score: float) -> float:
    """
    Compute the relevance cutoff for one recommendation query.

    If the strongest candidate clears the absolute floor
    (MIN_RECOMMENDATION_SCORE), the cutoff is the stricter of:
        - MIN_RECOMMENDATION_SCORE (absolute floor, from real distribution)
        - RECOMMENDATION_ELBOW_FACTOR * top_score (proportional band)

    If no candidate clears the absolute floor (a sparse/weak target), fall
    back to just the proportional elbow (which is below the floor) so we
    return the relatively-best few titles instead of an empty list. Those
    results are flagged ``match_status="relative"`` by the caller.
    """
    if top_score >= MIN_RECOMMENDATION_SCORE:
        return max(MIN_RECOMMENDATION_SCORE, RECOMMENDATION_ELBOW_FACTOR * top_score)
    return RECOMMENDATION_ELBOW_FACTOR * top_score


def _rank_and_filter(
    hybrid: np.ndarray,
    candidate_rows: np.ndarray,
    series_ids: List[int],
    metadata: Dict[int, Dict[str, Any]],
    top_n: int,
    min_relevance: float,
    use_elbow: bool,
) -> Tuple[List[int], float]:
    """
    Rank candidates by hybrid score and apply threshold + diversity.

    Returns ``(row_idx_list, cutoff)``:
        - A list of candidate row indices in final recommendation order
          (already filtered by threshold and diversity, length <= top_n).
        - The effective cutoff that was applied (the "elbow" value or the
          provided min_relevance when the elbow is disabled).

    Diversity re-ranking happens AFTER thresholding so weak candidates that
    would otherwise be admitted purely to fill a genre slot are rejected.
    """
    ranked_local = np.argsort(hybrid)[::-1]

    # Apply the adaptive elbow cutoff first (keeps only the strong band).
    cutoff = min_relevance
    if use_elbow and len(ranked_local) > 0:
        top_score = float(hybrid[ranked_local[0]])
        cutoff = _adaptive_cutoff(top_score)
    elif len(ranked_local) == 0:
        cutoff = min_relevance

    thresholded: List[int] = []
    for idx in ranked_local:
        if float(hybrid[idx]) < cutoff:
            break  # remaining are even lower
        thresholded.append(idx)

    # Now apply diversity to the surviving (relevant) candidates.
    diverse_indices = _apply_diversity(
        thresholded, candidate_rows, hybrid, series_ids, metadata,
    )

    return diverse_indices[:top_n], cutoff


def get_recommendations(
    series_id: int,
    top_n: int = 10,
    model_path: Optional[Path] = None,
    min_relevance: float = RELEVANCE_FLOOR,
    user_preference_embedding: Optional[np.ndarray] = None,
    user_preference_tfidf: Optional[Any] = None,
    use_elbow: bool = True,
) -> List[Dict[str, Any]]:
    """
    Return the top_n series most relevant to `series_id`, using hybrid
    scoring (semantic + TF-IDF + genre + quality).

    Candidate ranking now uses an adaptive cutoff:
        cutoff = max(MIN_RECOMMENDATION_SCORE,
                     RECOMMENDATION_ELBOW_FACTOR * top_candidate_score)

    This is deliberately stricter than the old uniform 0.15 floor so that
    weak, unrelated matches (the noise tail of the score distribution) are
    not surfaced as recommendations.

    Args:
        series_id: The `series_id` of the series to base recommendations on.
        top_n: How many recommendations to return (default 10).
        model_path: Optional override for which saved model to use.
        min_relevance: Minimum hybrid relevance score to include.
            Defaults to RELEVANCE_FLOOR (= MIN_RECOMMENDATION_SCORE).
            Set to 0.0 to disable filtering.
        user_preference_embedding: Optional pre-computed semantic user
            preference vector (for personalized recs).
        user_preference_tfidf: Optional pre-computed TF-IDF user
            preference vector (for personalized recs).
        use_elbow: If True (default), apply the proportional elbow cutoff
            in addition to the absolute min_relevance floor.

    Returns:
        A list of up to `top_n` dicts, sorted by descending relevance:
            {
                "series_id": int,
                "title": str | None,
                "rating": float | None,
                "genres": list[str],
                "image": str | None,
                "relevance_score": float,
                "component_scores": {
                    "semantic": float,
                    "tfidf": float,
                    "genre": float,
                    "quality": float,
                },
                "match_status": "strong" | "relative",
            }
        The requested series_id is never included in its own results.

    Raises:
        ModelNotBuiltError: If no model has been built yet.
        SeriesNotFoundError: If series_id isn't in the model.
    """
    bundle = load_model(model_path)
    series_ids = bundle["series_ids"]
    tfidf_matrix = bundle["tfidf_matrix"]
    metadata = bundle["metadata"]
    semantic_embeddings = bundle["semantic_embeddings"]

    try:
        target_row = series_ids.index(series_id)
    except ValueError:
        raise SeriesNotFoundError(
            f"series_id={series_id} was not found in the recommendation model "
            f"(invalid id, or added after the model was last built — try "
            f"rebuilding with `python -m recommender.build_model`)."
        ) from None

    # All candidate rows (excluding self)
    all_rows = np.arange(len(series_ids))
    mask = all_rows != target_row
    candidate_rows = all_rows[mask]

    if len(candidate_rows) == 0:
        return []

    # --- Compute hybrid scores ---
    if user_preference_embedding is not None and user_preference_tfidf is not None:
        # Personalized: use user preference vectors instead of target series vectors
        sem_scores = np.dot(user_preference_embedding, semantic_embeddings[candidate_rows].T).flatten()
        tfidf_scores = cosine_similarity(
            user_preference_tfidf, tfidf_matrix[candidate_rows]
        ).flatten()

        # For genre/quality, still use the source series
        target_id = series_ids[target_row]
        target_meta = metadata.get(target_id, {})
        target_genres = target_meta.get("genres_set", set())

        genre_scores = np.zeros(len(candidate_rows), dtype=np.float32)
        quality_scores = np.zeros(len(candidate_rows), dtype=np.float32)

        for i, row in enumerate(candidate_rows):
            cand_id = series_ids[row]
            cand_meta = metadata.get(cand_id, {})
            cand_genres = cand_meta.get("genres_set", set())
            genre_scores[i] = _genre_jaccard(target_genres, cand_genres)
            rating = cand_meta.get("rating")
            quality_scores[i] = (rating / 10.0) if isinstance(rating, (int, float)) else 0.5

        hybrid = (
            W_SEMANTIC * sem_scores
            + W_TFIDF * tfidf_scores
            + W_GENRE * genre_scores
            + W_QUALITY * quality_scores
        )
    else:
        hybrid = _compute_hybrid_scores(
            target_row, tfidf_matrix, semantic_embeddings,
            series_ids, metadata, candidate_rows,
        )

    # --- Rank, threshold (min_relevance + adaptive elbow) and diversify ---
    diverse_indices, cutoff = _rank_and_filter(
        hybrid, candidate_rows, series_ids, metadata,
        top_n=top_n, min_relevance=min_relevance, use_elbow=use_elbow,
    )

    # A series whose strongest candidate cleared the absolute floor has a
    # "strong" match; otherwise any returned titles are the relatively-best
    # few available (match_status == "relative").
    top_clears_floor = (
        len(hybrid) > 0 and float(hybrid[np.argmax(hybrid)]) >= MIN_RECOMMENDATION_SCORE
    )
    match_status = "strong" if top_clears_floor else "relative"

    # --- Build results ---
    recommendations: List[Dict[str, Any]] = []
    for idx in diverse_indices:
        score = float(hybrid[idx])

        row = candidate_rows[idx]
        candidate_id = series_ids[row]
        candidate_meta = metadata.get(candidate_id, {})

        # Per-component breakdown for debugging
        target_id = series_ids[target_row]
        target_meta_debug = metadata.get(target_id, {})
        cand_genres_set = candidate_meta.get("genres_set", set())
        target_genres_set = target_meta_debug.get("genres_set", set())

        component_scores = {
            "semantic": round(float(np.dot(semantic_embeddings[target_row], semantic_embeddings[row])), 4),
            "tfidf": round(float(cosine_similarity(tfidf_matrix[target_row], tfidf_matrix[row])[0, 0]), 4),
            "genre": round(_genre_jaccard(target_genres_set, cand_genres_set), 4),
            "quality": round((candidate_meta.get("rating", 5.0) or 5.0) / 10.0, 4),
        }

        recommendations.append({
            "series_id": candidate_id,
            "title": candidate_meta.get("title"),
            "rating": candidate_meta.get("rating"),
            "genres": candidate_meta.get("genres", []),
            "image": candidate_meta.get("image"),
            "relevance_score": round(score, 4),
            "component_scores": component_scores,
            "match_status": match_status,
        })

        if len(recommendations) >= top_n:
            break

    return recommendations
