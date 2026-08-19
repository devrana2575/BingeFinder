"""
recommender/recommend.py
===========================
Loads the saved TF-IDF model artifact and serves recommendations.

    get_recommendations(series_id, top_n=10)
        -> looks up `series_id` in the saved model
        -> computes cosine similarity against every other series
        -> returns the top_n most similar series (excluding itself)

Does not touch MongoDB: everything needed (vectors + display metadata)
was already captured by recommender/build_model.py, so recommending
only ever depends on the saved artifact.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
from sklearn.metrics.pairwise import cosine_similarity

if __name__ == "__main__" and __package__ is None:
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from recommender.build_model import MODEL_PATH
from recommender.exceptions import ModelNotBuiltError, SeriesNotFoundError
from utils.logger import get_logger

logger = get_logger(__name__)

# Kept in-process so repeated calls (e.g. one CLI session, or a future
# Streamlit app) don't re-read the artifact file from disk every time.
_model_cache: Optional[Dict[str, Any]] = None
_model_cache_path: Optional[Path] = None


def load_model(model_path: Optional[Path] = None, force_reload: bool = False) -> Dict[str, Any]:
    """
    Load the saved recommendation model artifact, caching it in memory.

    Args:
        model_path: Optional override for the artifact path. Defaults to
            recommender.build_model.MODEL_PATH.
        force_reload: If True, bypass the in-memory cache and re-read the
            file from disk (e.g. right after rebuilding the model).

    Returns:
        The model bundle dict (vectorizer, tfidf_matrix, series_ids,
        metadata, built_at).

    Raises:
        ModelNotBuiltError: If the artifact file doesn't exist yet, or
            fails to load.
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
    except Exception as exc:  # a corrupted/incompatible artifact must not crash the app
        logger.error("Failed to load recommendation model from %s: %s", path, exc)
        raise ModelNotBuiltError(f"Failed to load recommendation model from {path}: {exc}") from exc

    _model_cache = bundle
    _model_cache_path = path
    return bundle


def get_recommendations(
    series_id: int,
    top_n: int = 10,
    model_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Return the top_n series most similar to `series_id`, content-wise.

    Args:
        series_id: The `tvmaze_id` of the series to base recommendations
            on.
        top_n: How many recommendations to return (default 10).
        model_path: Optional override for which saved model to use.

    Returns:
        A list of up to `top_n` dicts, sorted by descending similarity,
        each shaped:
            {
                "series_id": int,
                "title": str | None,
                "rating": float | None,
                "genres": list[str],
                "image": str | None,
                "similarity_score": float,   # 0.0-1.0, NOT "accuracy"
            }
        The requested series_id is never included in its own results.

    Raises:
        ModelNotBuiltError: If no model has been built yet.
        SeriesNotFoundError: If series_id isn't in the currently loaded
            model (e.g. an invalid id, or a series added after the last
            build).
    """
    bundle = load_model(model_path)
    series_ids = bundle["series_ids"]
    tfidf_matrix = bundle["tfidf_matrix"]
    metadata = bundle["metadata"]

    try:
        target_row = series_ids.index(series_id)
    except ValueError:
        raise SeriesNotFoundError(
            f"series_id={series_id} was not found in the recommendation model "
            f"(invalid id, or added after the model was last built — try "
            f"rebuilding with `python -m recommender.build_model`)."
        ) from None

    # Similarity of the target row against every row, including itself.
    similarity_scores = cosine_similarity(tfidf_matrix[target_row], tfidf_matrix).flatten()

    # Sort all row indices by descending similarity.
    ranked_rows = similarity_scores.argsort()[::-1]

    recommendations: List[Dict[str, Any]] = []
    for row in ranked_rows:
        candidate_id = series_ids[row]
        if candidate_id == series_id:
            continue  # a series is never recommended to itself

        candidate_meta = metadata.get(candidate_id, {})
        recommendations.append(
            {
                "series_id": candidate_id,
                "title": candidate_meta.get("title"),
                "rating": candidate_meta.get("rating"),
                "genres": candidate_meta.get("genres", []),
                "image": candidate_meta.get("image"),
                "similarity_score": round(float(similarity_scores[row]), 4),
            }
        )
        if len(recommendations) >= top_n:
            break

    return recommendations
