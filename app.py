"""
app.py
======
Backend entry point for BingeFinder.

IMPORTANT: This is ONLY the backend-foundation phase. Recommendation logic
and the Streamlit UI are intentionally NOT implemented here yet — they will
be added in a later phase, likely living in `recommender/` and `pages/`
respectively.

Running this script performs a sync of TVmaze TV/web-series data into the
local MongoDB database, and prints a short summary. This is useful for
manually verifying the backend foundation works end-to-end before building
anything on top of it.

NOTE: TMDb is currently unreachable from this network, so the active
ingestion backend is TVmaze + MongoDB (api/tvmaze.py, database/mongo_client.py,
database/update_mongo.py) rather than the original TMDb + SQLite pipeline
(api/tmdb.py, database/database.py, database/update_database.py). The
original modules are left in place, unused, until this migration is fully
verified.
"""

from database.mongo_client import MongoDBManager
from database.update_mongo import run_update
from utils.logger import get_logger

logger = get_logger(__name__)


def main() -> None:
    """Run a full TVmaze -> MongoDB sync and print a summary of the resulting database."""
    logger.info("Starting BingeFinder backend sync (TVmaze -> MongoDB)...")

    stats = run_update()
    logger.info(
        "Sync finished. Fetched %d, inserted %d, updated %d, failed %d.",
        stats["fetched"], stats["inserted"], stats["updated"], stats["failed"],
    )

    mongo_manager = MongoDBManager()
    total_series = mongo_manager.get_series_count()
    mongo_manager.close()
    logger.info("MongoDB now contains %d total series.", total_series)


if __name__ == "__main__":
    main()
