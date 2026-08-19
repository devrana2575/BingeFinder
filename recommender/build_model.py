"""
recommender/build_model.py
=============================
Builds the content-based recommendation model:

    MongoDB `series` documents
        -> content soup per series (recommender/preprocess.py)
        -> TF-IDF matrix (scikit-learn)
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
from recommender.preprocess import build_content_soup
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
    get_recommendations() returns alongside each similarity score, so
    recommending doesn't need a fresh MongoDB read per result.

    Args:
        doc: A `series` MongoDB document.

    Returns:
        Dict with title / rating / genres / image, using None or []
        for anything the document doesn't have.
    """
    genres = doc.get("genres")
    return {
        "title": doc.get("name"),
        "rating": doc.get("rating"),
        "genres": genres if isinstance(genres, list) else [],
        "image": doc.get("image_medium") or doc.get("image_original"),
    }


def build_recommendation_model(save_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Read every series from MongoDB, build the TF-IDF representation, and
    save the resulting model artifact to disk.

    Series with no usable text content at all (no summary, genres, cast,
    or network/web_channel) are skipped — they can't be meaningfully
    compared to anything and would only pollute the vocabulary — but this
    is never treated as a fatal error unless it leaves too few series to
    build a model from at all.

    Args:
        save_path: Optional override for where the artifact is written.
            Defaults to MODEL_PATH.

    Returns:
        Stats dict: {"total_in_db", "used", "skipped", "vocabulary_size",
        "model_path", "built_at"}.

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
        tvmaze_id = doc.get("tvmaze_id")
        if tvmaze_id is None:
            skipped += 1
            continue

        soup = build_content_soup(doc)
        if not soup:
            # No summary, genres, cast, or channel at all — nothing to
            # compare this series against.
            skipped += 1
            continue

        series_ids.append(tvmaze_id)
        corpus.append(soup)
        metadata[tvmaze_id] = _extract_metadata(doc)

    if len(corpus) < MIN_USABLE_SERIES:
        raise InsufficientDataError(
            f"Only {len(corpus)} series have usable text content "
            f"(need at least {MIN_USABLE_SERIES}). Sync more shows first "
            f"via `python -m database.update_mongo`."
        )

    vectorizer = TfidfVectorizer(stop_words="english", max_features=20000)
    tfidf_matrix = vectorizer.fit_transform(corpus)

    model_bundle = {
        "vectorizer": vectorizer,
        "tfidf_matrix": tfidf_matrix,
        "series_ids": series_ids,
        "metadata": metadata,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    joblib.dump(model_bundle, save_path)

    stats = {
        "total_in_db": len(docs),
        "used": len(series_ids),
        "skipped": skipped,
        "vocabulary_size": len(vectorizer.vocabulary_),
        "model_path": str(save_path),
        "built_at": model_bundle["built_at"],
    }
    logger.info(
        "Model built: %d used / %d skipped / vocabulary=%d -> %s",
        stats["used"], stats["skipped"], stats["vocabulary_size"], save_path,
    )
    return stats


def _print_summary(stats: Dict[str, Any]) -> None:
    print("Total series in MongoDB:", stats["total_in_db"])
    print("Series used in model:", stats["used"])
    print("Series skipped (no usable content):", stats["skipped"])
    print("TF-IDF vocabulary size:", stats["vocabulary_size"])
    print("Model saved to:", stats["model_path"])
    print("Built at:", stats["built_at"])


if __name__ == "__main__":
    try:
        _print_summary(build_recommendation_model())
    except (MongoDatabaseError, InsufficientDataError) as exc:
        logger.error("Model build failed: %s", exc)
        print(f"Model build failed: {exc}")
        sys.exit(1)
