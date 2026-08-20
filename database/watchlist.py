"""
database/watchlist.py
======================
User-specific watchlist backed by MongoDB.

Design notes:
    - Each document includes a ``user_id`` field, so User A never sees
      User B's watchlist.
    - A compound unique index on ``(user_id, tvmaze_id)`` prevents the
      same series from appearing twice in one user's watchlist.
    - The module reuses the existing ``MongoDBManager`` connection.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List

from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from database.mongo_client import MongoDatabaseError, MongoDBManager
from utils.logger import get_logger

logger = get_logger(__name__)

WATCHLIST_COLLECTION_NAME = "watchlist"


class WatchlistManager:
    """
    Manages a user's watchlist in the ``watchlist`` collection.

    Usage:
        mongo_manager = MongoDBManager()
        wl = WatchlistManager(mongo_manager)
        wl.add_to_watchlist("user_id_abc", 1234)
        items = wl.get_watchlist("user_id_abc")
    """

    def __init__(self, mongo_manager: MongoDBManager) -> None:
        self._mongo = mongo_manager
        try:
            self._collection: Collection = mongo_manager._db[WATCHLIST_COLLECTION_NAME]
        except PyMongoError as exc:
            logger.error("Failed to access watchlist collection: %s", exc)
            raise MongoDatabaseError(f"Failed to access watchlist collection: {exc}") from exc

        self._ensure_indexes()

    # ------------------------------------------------------------------
    # Index helpers
    # ------------------------------------------------------------------

    def _ensure_indexes(self) -> None:
        """Create compound unique index on (user_id, tvmaze_id) and drop
        the old single-field index if it exists."""
        try:
            existing = self._collection.index_information()
            if "uniq_watchlist_tvmaze_id" in existing:
                self._collection.drop_index("uniq_watchlist_tvmaze_id")
        except PyMongoError:
            pass

        try:
            self._collection.create_index(
                [("user_id", 1), ("tvmaze_id", 1)],
                unique=True,
                name="uniq_watchlist_user_series",
            )
        except PyMongoError as exc:
            logger.error("Failed to create compound index on watchlist: %s", exc)
            raise MongoDatabaseError(
                f"Failed to create compound index on watchlist: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_to_watchlist(self, user_id: str, tvmaze_id: int) -> str:
        """
        Add a series to a user's watchlist.

        Returns:
            ``"added"`` or ``"already_exists"``.
        """
        document = {
            "user_id": user_id,
            "tvmaze_id": tvmaze_id,
            "added_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        try:
            self._collection.insert_one(document)
            logger.info("Added tvmaze_id=%s to watchlist for user %s.", tvmaze_id, user_id)
            return "added"
        except PyMongoError as exc:
            if exc.code == 11000:
                logger.info("tvmaze_id=%s already in watchlist for user %s.", tvmaze_id, user_id)
                return "already_exists"
            logger.error("Failed to add tvmaze_id=%s to watchlist: %s", tvmaze_id, exc)
            raise MongoDatabaseError(
                f"Failed to add tvmaze_id={tvmaze_id} to watchlist: {exc}"
            ) from exc

    def remove_from_watchlist(self, user_id: str, tvmaze_id: int) -> str:
        """
        Remove a series from a user's watchlist.

        Returns:
            ``"removed"`` or ``"not_found"``.
        """
        try:
            result = self._collection.delete_one(
                {"user_id": user_id, "tvmaze_id": tvmaze_id}
            )
            if result.deleted_count:
                logger.info("Removed tvmaze_id=%s from watchlist for user %s.", tvmaze_id, user_id)
                return "removed"
            logger.info("tvmaze_id=%s not found in watchlist for user %s.", tvmaze_id, user_id)
            return "not_found"
        except PyMongoError as exc:
            logger.error("Failed to remove tvmaze_id=%s from watchlist: %s", tvmaze_id, exc)
            raise MongoDatabaseError(
                f"Failed to remove tvmaze_id={tvmaze_id} from watchlist: {exc}"
            ) from exc

    def get_watchlist(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Return all watchlist documents for a user, sorted by added_at
        descending (most recently added first).
        """
        try:
            return list(
                self._collection.find({"user_id": user_id}).sort("added_at", -1)
            )
        except PyMongoError as exc:
            logger.error("Failed to fetch watchlist for user %s: %s", user_id, exc)
            raise MongoDatabaseError(f"Failed to fetch watchlist: {exc}") from exc

    def is_in_watchlist(self, user_id: str, tvmaze_id: int) -> bool:
        """Check whether a series is in a user's watchlist."""
        try:
            return self._collection.find_one(
                {"user_id": user_id, "tvmaze_id": tvmaze_id}
            ) is not None
        except PyMongoError as exc:
            logger.error("Failed to check watchlist for user %s, tvmaze_id=%s: %s", user_id, tvmaze_id, exc)
            raise MongoDatabaseError(
                f"Failed to check watchlist for tvmaze_id={tvmaze_id}: {exc}"
            ) from exc

    def get_watchlist_count(self, user_id: str) -> int:
        """Return the total number of items in a user's watchlist."""
        try:
            return self._collection.count_documents({"user_id": user_id})
        except PyMongoError as exc:
            logger.error("Failed to count watchlist documents for user %s: %s", user_id, exc)
            raise MongoDatabaseError(f"Failed to count watchlist documents: {exc}") from exc
