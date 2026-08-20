"""
database/recently_viewed.py
============================
Tracks recently viewed series for logged-in users, backed by MongoDB.

Design notes:
    - A compound unique index on ``(user_id, tvmaze_id)`` ensures each
      series appears at most once per user.
    - Viewing a series again updates the ``viewed_at`` timestamp.
    - Maximum 50 entries per user (oldest pruned automatically).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List

from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from database.mongo_client import MongoDatabaseError, MongoDBManager
from utils.logger import get_logger

logger = get_logger(__name__)

RECENTLY_VIEWED_COLLECTION_NAME = "recently_viewed"
MAX_RECENTLY_VIEWED = 50


class RecentlyViewedManager:
    """
    Tracks recently viewed series per user.

    Usage:
        mongo_manager = MongoDBManager()
        rvm = RecentlyViewedManager(mongo_manager)
        rvm.record_view("user_id_abc", 1234)
        recent = rvm.get_recently_viewed("user_id_abc", limit=10)
    """

    def __init__(self, mongo_manager: MongoDBManager) -> None:
        self._mongo = mongo_manager
        try:
            self._collection: Collection = mongo_manager._db[RECENTLY_VIEWED_COLLECTION_NAME]
        except PyMongoError as exc:
            logger.error("Failed to access recently_viewed collection: %s", exc)
            raise MongoDatabaseError(
                f"Failed to access recently_viewed collection: {exc}"
            ) from exc

        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """Create compound unique index and sort index."""
        try:
            self._collection.create_index(
                [("user_id", 1), ("tvmaze_id", 1)],
                unique=True,
                name="uniq_recently_viewed_user_series",
            )
            self._collection.create_index(
                [("user_id", 1), ("viewed_at", -1)],
                name="idx_recently_viewed_user_time",
            )
        except PyMongoError as exc:
            logger.error("Failed to create indexes on recently_viewed: %s", exc)
            raise MongoDatabaseError(
                f"Failed to create indexes on recently_viewed: {exc}"
            ) from exc

    def record_view(self, user_id: str, tvmaze_id: int) -> None:
        """
        Record that a user viewed a series.  If the series is already
        in the user's recently viewed list, its timestamp is updated.

        Prunes entries beyond MAX_RECENTLY_VIEWED per user.
        """
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            self._collection.update_one(
                {"user_id": user_id, "tvmaze_id": tvmaze_id},
                {"$set": {"viewed_at": now}},
                upsert=True,
            )
            self._prune(user_id)
        except PyMongoError as exc:
            logger.error(
                "Failed to record view for user %s, tvmaze_id=%s: %s",
                user_id, tvmaze_id, exc,
            )

    def _prune(self, user_id: str) -> None:
        """Remove oldest entries if the user exceeds MAX_RECENTLY_VIEWED."""
        try:
            count = self._collection.count_documents({"user_id": user_id})
            if count > MAX_RECENTLY_VIEWED:
                excess = count - MAX_RECENTLY_VIEWED
                oldest = self._collection.find(
                    {"user_id": user_id}
                ).sort("viewed_at", 1).limit(excess)
                ids_to_remove = [doc["_id"] for doc in oldest]
                if ids_to_remove:
                    self._collection.delete_many({"_id": {"$in": ids_to_remove}})
        except PyMongoError:
            pass

    def get_recently_viewed(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Return the most recently viewed series for a user.

        Args:
            user_id: The user's ID.
            limit: Maximum entries to return (default 10).

        Returns:
            List of documents sorted by viewed_at descending.
        """
        try:
            return list(
                self._collection.find({"user_id": user_id})
                .sort("viewed_at", -1)
                .limit(limit)
            )
        except PyMongoError as exc:
            logger.error("Failed to get recently viewed for user %s: %s", user_id, exc)
            return []

    def get_recently_viewed_ids(self, user_id: str, limit: int = 10) -> List[int]:
        """Return just the tvmaze_ids of recently viewed series."""
        recent = self.get_recently_viewed(user_id, limit)
        return [r["tvmaze_id"] for r in recent if "tvmaze_id" in r]

    def is_viewed(self, user_id: str, tvmaze_id: int) -> bool:
        """Check if a user has viewed a series."""
        try:
            return self._collection.find_one(
                {"user_id": user_id, "tvmaze_id": tvmaze_id}
            ) is not None
        except PyMongoError:
            return False
