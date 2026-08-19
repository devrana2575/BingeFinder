"""
database/watchlist.py
======================
Single-user watchlist backed by MongoDB.

Design notes:
    - All documents live in one `watchlist` collection; there is no
      per-user partitioning.
    - A unique index on `tvmaze_id` prevents the same series from
      appearing twice.
    - The module reuses the existing `MongoDBManager` connection rather
      than creating its own — call `MongoDBManager.db` from the caller
      and pass it into `WatchlistManager`.
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
    Manages the user's watchlist in the ``watchlist`` collection.

    Usage:
        mongo_manager = MongoDBManager()
        wl = WatchlistManager(mongo_manager)
        wl.add_to_watchlist(1234)
        items = wl.get_watchlist()
    """

    def __init__(self, mongo_manager: MongoDBManager) -> None:
        """
        Store a reference to the existing ``MongoDBManager`` and grab the
        watchlist collection.  Creates a unique index on ``tvmaze_id``
        so that duplicate inserts are impossible.

        Args:
            mongo_manager: An already-initialised ``MongoDBManager``
                whose connection is alive.

        Raises:
            MongoDatabaseError: If the collection or index cannot be
                obtained.
        """
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
        """Create a unique index on ``tvmaze_id`` (idempotent)."""
        try:
            self._collection.create_index(
                "tvmaze_id", unique=True, name="uniq_watchlist_tvmaze_id"
            )
        except PyMongoError as exc:
            logger.error("Failed to create unique index on watchlist.tvmaze_id: %s", exc)
            raise MongoDatabaseError(
                f"Failed to create unique index on watchlist.tvmaze_id: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_to_watchlist(self, tvmaze_id: int) -> str:
        """
        Add a series to the watchlist.

        Args:
            tvmaze_id: TVmaze show ID to add.

        Returns:
            ``"added"`` if the series was inserted, or
            ``"already_exists"`` if it is already in the watchlist.

        Raises:
            MongoDatabaseError: If the insert fails for a reason other
                than a duplicate key.
        """
        document = {
            "tvmaze_id": tvmaze_id,
            "added_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        try:
            self._collection.insert_one(document)
            logger.info("Added tvmaze_id=%s to watchlist.", tvmaze_id)
            return "added"
        except PyMongoError as exc:
            if exc.code == 11000:
                logger.info("tvmaze_id=%s already in watchlist.", tvmaze_id)
                return "already_exists"
            logger.error("Failed to add tvmaze_id=%s to watchlist: %s", tvmaze_id, exc)
            raise MongoDatabaseError(
                f"Failed to add tvmaze_id={tvmaze_id} to watchlist: {exc}"
            ) from exc

    def remove_from_watchlist(self, tvmaze_id: int) -> str:
        """
        Remove a series from the watchlist.

        Args:
            tvmaze_id: TVmaze show ID to remove.

        Returns:
            ``"removed"`` if the document was deleted, or
            ``"not_found"`` if no matching document existed.

        Raises:
            MongoDatabaseError: If the delete operation fails.
        """
        try:
            result = self._collection.delete_one({"tvmaze_id": tvmaze_id})
            if result.deleted_count:
                logger.info("Removed tvmaze_id=%s from watchlist.", tvmaze_id)
                return "removed"
            logger.info("tvmaze_id=%s not found in watchlist for removal.", tvmaze_id)
            return "not_found"
        except PyMongoError as exc:
            logger.error("Failed to remove tvmaze_id=%s from watchlist: %s", tvmaze_id, exc)
            raise MongoDatabaseError(
                f"Failed to remove tvmaze_id={tvmaze_id} from watchlist: {exc}"
            ) from exc

    def get_watchlist(self) -> List[Dict[str, Any]]:
        """
        Return all watchlist documents sorted by ``added_at`` descending
        (most recently added first).

        Returns:
            A list of watchlist document dicts.

        Raises:
            MongoDatabaseError: If the query fails.
        """
        try:
            return list(self._collection.find({}).sort("added_at", -1))
        except PyMongoError as exc:
            logger.error("Failed to fetch watchlist: %s", exc)
            raise MongoDatabaseError(f"Failed to fetch watchlist: {exc}") from exc

    def is_in_watchlist(self, tvmaze_id: int) -> bool:
        """
        Check whether a series is in the watchlist.

        Args:
            tvmaze_id: TVmaze show ID to look up.

        Returns:
            ``True`` if the series is in the watchlist, ``False``
            otherwise.

        Raises:
            MongoDatabaseError: If the query fails.
        """
        try:
            return self._collection.find_one({"tvmaze_id": tvmaze_id}) is not None
        except PyMongoError as exc:
            logger.error("Failed to check watchlist for tvmaze_id=%s: %s", tvmaze_id, exc)
            raise MongoDatabaseError(
                f"Failed to check watchlist for tvmaze_id={tvmaze_id}: {exc}"
            ) from exc

    def get_watchlist_count(self) -> int:
        """
        Return the total number of items in the watchlist.

        Returns:
            The document count in the watchlist collection.

        Raises:
            MongoDatabaseError: If the count query fails.
        """
        try:
            return self._collection.count_documents({})
        except PyMongoError as exc:
            logger.error("Failed to count watchlist documents: %s", exc)
            raise MongoDatabaseError(f"Failed to count watchlist documents: {exc}") from exc
