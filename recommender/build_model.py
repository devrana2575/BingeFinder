"""
recommender/build_model.py
=============================
Builds the hybrid recommendation model:

    MongoDB `series` documents
        -> content soup per series (recommender/preprocess.py)
        -> TF-IDF matrix (scikit-learn)
        -> semantic embeddings (sentence-transformers)
        -> saved to disk (joblib) as a single reusable artifact

The saved artifact bundles everything get_recommendations() needs
(recommender/recommend.py) so that recommending never has to touch
MongoDB again, and doesn't depend on this build step's process still
being alive.

Rebuild whenever the database changes:
    python -m recommender.build_model

Reuses the existing database layer only (database.mongo_client) — no
new database/connection logic is introduced here.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer

if __name__ == "__main__" and __package__ is None:
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from database.mongo_client import MongoDatabaseError, MongoDBManager
from recommender.exceptions import InsufficientDataError
from recommender.preprocess import build_content_soup, get_genre_list, get_channel_names
from utils.logger import get_logger

logger = get_logger(__name__)

# Where the trained model artifact is saved / loaded from.
ARTIFACT_DIR: Path = Path(__file__).resolve().parent / "artifacts"
MODEL_PATH: Path = ARTIFACT_DIR / "recommendation_model.joblib"

# A model built from fewer than this many usable series can't produce
# meaningful similarities (and scikit-learn's TF-IDF needs at least 2
# documents to build a vocabulary at all).
MIN_USABLE_SERIES = 2


def _extract_metadata(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pull the small, display-ready subset of a series document that
    get_recommendations() returns alongside each relevance score, so
    recommending doesn't need a fresh MongoDB read per result.

    Args:
        doc: A `series` MongoDB document.

    Returns:
        Dict with title / rating / genres / image / genres_set /
        channel_names, using None or [] for anything missing.
    """
    genres = doc.get("genres")
    genres_list = genres if isinstance(genres, list) else []
    return {
        "title": doc.get("name"),
        "rating": doc.get("rating"),
        "genres": genres_list,
        "image": doc.get("image_medium") or doc.get("image_original"),
        "genres_set": set(genres_list),
        "channel_names": get_channel_names(doc),
    }


def check_model_freshness(model_path: Optional[Path] = None) -> bool:
    """
    Check whether the saved model artifact is still fresh.

    Returns True if the model exists and was built after the most
    recent data sync.  Returns False if the model is missing, stale,
    or cannot be read.
    """
    from config import REBUILD_MODEL_TTL_HOURS

    path = Path(model_path) if model_path else MODEL_PATH
    if not path.exists():
        return False

    try:
        bundle = joblib.load(path)
    except Exception:
        return False

    built_at_str = bundle.get("built_at")
    if not built_at_str:
        return False

    try:
        built_at = datetime.fromisoformat(built_at_str)
        now = datetime.now(timezone.utc)
        age_hours = (now - built_at).total_seconds() / 3600
        return age_hours < REBUILD_MODEL_TTL_HOURS
    except (ValueError, TypeError):
        return False


def build_recommendation_model(save_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Read every series from MongoDB, build the hybrid TF-IDF + semantic
    representation, and save the resulting model artifact to disk.

    Series with no usable text content at all are skipped — they can't
    be meaningfully compared to anything and would only pollute the
    vocabulary — but this is never treated as a fatal error unless it
    leaves too few series to build a model from at all.

    Args:
        save_path: Optional override for where the artifact is written.
            Defaults to MODEL_PATH.

    Returns:
        Stats dict: {"total_in_db", "used", "skipped", "vocabulary_size",
        "embedding_dim", "model_path", "built_at"}.

    Raises:
        MongoDatabaseError: If reading from MongoDB fails.
        InsufficientDataError: If fewer than MIN_USABLE_SERIES series
            have usable text content.
    """
    save_path = Path(save_path) if save_path else MODEL_PATH
    save_path.parent.mkdir(parents=True, exist_ok=True)

    mongo_manager = MongoDBManager()
    try:
        docs = mongo_manager.get_all_series()
    finally:
        mongo_manager.close()

    logger.info("Fetched %d series document(s) from MongoDB.", len(docs))

    series_ids: List[int] = []
    corpus: List[str] = []
    metadata: Dict[int, Dict[str, Any]] = {}
    skipped = 0

    for doc in docs:
        series_id = doc.get("series_id")
        if series_id is None:
            skipped += 1
            continue

        soup = build_content_soup(doc)
        if not soup:
            skipped += 1
            continue

        series_ids.append(series_id)
        corpus.append(soup)
        metadata[series_id] = _extract_metadata(doc)

    if len(corpus) < MIN_USABLE_SERIES:
        raise InsufficientDataError(
            f"Only {len(corpus)} series have usable text content "
            f"(need at least {MIN_USABLE_SERIES}). Sync more series "
            f"into MongoDB first."
        )

    vectorizer = TfidfVectorizer(stop_words="english", max_features=20000)
    tfidf_matrix = vectorizer.fit_transform(corpus)

    logger.info("TF-IDF matrix built: %d x %d", tfidf_matrix.shape[0], tfidf_matrix.shape[1])

    # --- Semantic embeddings ---
    logger.info("Generating semantic embeddings for %d series...", len(corpus))
    from recommender.embeddings import encode_texts
    semantic_embeddings = encode_texts(corpus, show_progress=True)
    embedding_dim = semantic_embeddings.shape[1]
    logger.info("Semantic embeddings: shape %s", semantic_embeddings.shape)

    model_bundle = {
        "vectorizer": vectorizer,
        "tfidf_matrix": tfidf_matrix,
        "series_ids": series_ids,
        "metadata": metadata,
        "semantic_embeddings": semantic_embeddings,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    joblib.dump(model_bundle, save_path)

    stats = {
        "total_in_db": len(docs),
        "used": len(series_ids),
        "skipped": skipped,
        "vocabulary_size": len(vectorizer.vocabulary_),
        "embedding_dim": embedding_dim,
        "model_path": str(save_path),
        "built_at": model_bundle["built_at"],
    }
    logger.info(
        "Hybrid model built: %d used / %d skipped / vocab=%d / emb_dim=%d -> %s",
        stats["used"], stats["skipped"], stats["vocabulary_size"],
        stats["embedding_dim"], save_path,
    )
    return stats


def _print_summary(stats: Dict[str, Any]) -> None:
    print("Total series in MongoDB:", stats["total_in_db"])
    print("Series used in model:", stats["used"])
    print("Series skipped (no usable content):", stats["skipped"])
    print("TF-IDF vocabulary size:", stats["vocabulary_size"])
    print("Embedding dimension:", stats["embedding_dim"])
    print("Model saved to:", stats["model_path"])
    print("Built at:", stats["built_at"])


if __name__ == "__main__":
    try:
        _print_summary(build_recommendation_model())
    except (MongoDatabaseError, InsufficientDataError) as exc:
        logger.error("Model build failed: %s", exc)
        print(f"Model build failed: {exc}")
        sys.exit(1)
