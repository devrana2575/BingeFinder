"""
database/mongo_client.py
==========================
MongoDB persistence layer for BingeFinder's TVmaze-sourced series data.

Design notes:
    - A single `pymongo.MongoClient` is reused per `MongoDBManager`
      instance (PyMongo pools connections internally).
    - The `series` collection is uniquely indexed on `tvmaze_id` so
      re-syncing a show updates its existing document (upsert) instead
      of creating a duplicate.
    - Mirrors the shape of database/database.py's public API (upsert +
      count + context-manager close) so the two backends are easy to
      compare; neither module depends on the other.
    - This replaces database/database.py (SQLite) as the active storage
      backend (TMDb is currently unreachable from this network, and
      TVmaze + MongoDB is used instead). database/database.py is left in
      place, unused, until this migration is fully verified.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from config import get_mongodb_database, get_mongodb_uri
from utils.logger import get_logger

logger = get_logger(__name__)

SERIES_COLLECTION_NAME = "series"


class MongoDatabaseError(Exception):
    """Raised when a MongoDB operation fails."""


class MongoDBManager:
    """
    Manages the MongoDB connection and `series` collection operations.

    Usage:
        mongo_manager = MongoDBManager()
        result = mongo_manager.upsert_series(series_document)  # "inserted" | "updated"
        total = mongo_manager.get_series_count()
        mongo_manager.close()
    """

    def __init__(self, uri: Optional[str] = None, database_name: Optional[str] = None) -> None:
        """
        Initialize the MongoDB connection and ensure required indexes
        exist. Never drops or recreates the database/collection — safe to
        call on every run against an already-populated database.

        Args:
            uri: Optional explicit MongoDB connection URI. If not
                provided, read from MONGODB_URI via config.
            database_name: Optional explicit database name. If not
                provided, read from MONGODB_DATABASE via config.

        Raises:
            ConfigError: If MONGODB_URI or MONGODB_DATABASE is not set
                anywhere.
            MongoDatabaseError: If the connection or index creation fails.
        """
        self._uri: str = uri or get_mongodb_uri()
        self._database_name: str = database_name or get_mongodb_database()
        try:
            self._client: MongoClient = MongoClient(self._uri, serverSelectionTimeoutMS=5000)
            # Force a round-trip now so connection problems surface here,
            # with a clear error, rather than on the first real operation.
            self._client.admin.command("ping")
            self._db = self._client[self._database_name]
            self.series: Collection = self._db[SERIES_COLLECTION_NAME]
        except PyMongoError as exc:
            logger.error("Failed to connect to MongoDB at %s: %s", self._uri, exc)
            raise MongoDatabaseError(f"Failed to connect to MongoDB: {exc}") from exc

        self.ensure_indexes()

    def ensure_indexes(self) -> None:
        """
        Ensure a unique index on `tvmaze_id` exists — idempotent, so
        calling this on every startup never raises `IndexOptionsConflict`
        regardless of what index (if any) is already there.

        `Collection.create_index()` is only a no-op when an *existing*
        index has the exact same key spec AND the exact same name. A
        differently-named index on the same key (e.g. an old
        `tvmaze_id_1` from a previous default `create_index("tvmaze_id")`
        call, vs. this method's `name="uniq_tvmaze_id"`) makes MongoDB
        raise `IndexOptionsConflict` instead of silently reusing it — this
        is exactly what happened before this fix. So the existing index
        is inspected first:

          1. No index on `tvmaze_id` at all -> create the unique index.
          2. An existing index on `tvmaze_id` is already unique -> reuse
             it as-is (whatever it's named); nothing to do.
          3. An existing index on `tvmaze_id` is NOT unique -> check the
             collection for duplicate `tvmaze_id` values first:
               - Duplicates found -> refuse to touch the index (a unique
                 index could never be built anyway) and raise a clear
                 error describing which values collide, so they can be
                 cleaned up manually. The collection/index are left
                 untouched.
               - No duplicates -> it's safe to drop that one non-unique
                 index (by its actual name) and create the required
                 unique index in its place. Only ever drops the single
                 conflicting index, never the collection or its data.

        Raises:
            MongoDatabaseError: If duplicate `tvmaze_id` values are found
                (so a unique index can't be built), or if an index
                operation fails for any other reason.
        """
        try:
            existing_indexes = self.series.index_information()
        except PyMongoError as exc:
            logger.error("Failed to read existing indexes on 'series': %s", exc)
            raise MongoDatabaseError(f"Failed to read existing indexes on 'series': {exc}") from exc

        # Find any existing index whose key spec is exactly {tvmaze_id: 1}
        # (a single-field ascending index), regardless of its name.
        existing_tvmaze_id_index = None
        for index_name, index_spec in existing_indexes.items():
            if index_spec.get("key") == [("tvmaze_id", 1)]:
                existing_tvmaze_id_index = (index_name, index_spec)
                break

        if existing_tvmaze_id_index is None:
            logger.info("No index on 'tvmaze_id' found; creating 'uniq_tvmaze_id'.")
            self._create_unique_tvmaze_id_index()
            return

        index_name, index_spec = existing_tvmaze_id_index
        if index_spec.get("unique"):
            logger.info(
                "Existing index '%s' on 'tvmaze_id' is already unique; reusing it as-is.",
                index_name,
            )
            return

        logger.warning(
            "Existing index '%s' on 'tvmaze_id' is not unique; checking for duplicate "
            "tvmaze_id values before attempting to replace it.",
            index_name,
        )
        duplicates = self._find_duplicate_tvmaze_ids()
        if duplicates:
            raise MongoDatabaseError(
                "Cannot create a unique index on 'tvmaze_id': duplicate values found "
                f"({duplicates}). Resolve these duplicate series documents manually, "
                "then rerun. The existing (non-unique) index and all series data have "
                "been left untouched."
            )

        logger.info(
            "No duplicate tvmaze_id values found; dropping non-unique index '%s' and "
            "creating the required unique index. No documents are affected.",
            index_name,
        )
        try:
            self.series.drop_index(index_name)
        except PyMongoError as exc:
            logger.error("Failed to drop conflicting index '%s': %s", index_name, exc)
            raise MongoDatabaseError(f"Failed to drop conflicting index '{index_name}': {exc}") from exc

        self._create_unique_tvmaze_id_index()

    def _create_unique_tvmaze_id_index(self) -> None:
        """Create the unique 'uniq_tvmaze_id' index. Assumes no conflicting index exists."""
        try:
            self.series.create_index("tvmaze_id", unique=True, name="uniq_tvmaze_id")
        except PyMongoError as exc:
            logger.error("Failed to create unique index on tvmaze_id: %s", exc)
            raise MongoDatabaseError(f"Failed to create unique index on tvmaze_id: {exc}") from exc

    def _find_duplicate_tvmaze_ids(self) -> List[Any]:
        """
        Return the list of `tvmaze_id` values that appear on more than
        one document (empty list if there are none). Read-only — never
        modifies data.

        Raises:
            MongoDatabaseError: If the aggregation query fails.
        """
        pipeline = [
            {"$group": {"_id": "$tvmaze_id", "count": {"$sum": 1}}},
            {"$match": {"count": {"$gt": 1}}},
        ]
        try:
            return [doc["_id"] for doc in self.series.aggregate(pipeline)]
        except PyMongoError as exc:
            logger.error("Failed to check for duplicate tvmaze_id values: %s", exc)
            raise MongoDatabaseError(f"Failed to check for duplicate tvmaze_id values: {exc}") from exc

    def upsert_series(self, series_document: Dict[str, Any]) -> str:
        """
        Insert a new series document, or update the existing one matched
        by `tvmaze_id`, avoiding duplicates.

        Args:
            series_document: Dict with at least a "tvmaze_id" key, plus
                any of the other `series` document fields. A
                "last_synced_at" timestamp is added/overwritten
                automatically.

        Returns:
            "inserted" if a new document was created, "updated" if an
            existing document (matched by tvmaze_id) was written to.

        Raises:
            ValueError: If `series_document` has no "tvmaze_id".
            MongoDatabaseError: If the write fails.
        """
        tvmaze_id = series_document.get("tvmaze_id")
        if tvmaze_id is None:
            raise ValueError("series_document must include a 'tvmaze_id' to upsert.")

        document_to_set = dict(series_document)
        document_to_set["last_synced_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

        try:
            result = self.series.update_one(
                {"tvmaze_id": tvmaze_id},
                {"$set": document_to_set},
                upsert=True,
            )
        except PyMongoError as exc:
            logger.error("Failed to upsert series tvmaze_id=%s: %s", tvmaze_id, exc)
            raise MongoDatabaseError(f"Failed to upsert series tvmaze_id={tvmaze_id}: {exc}") from exc

        return "inserted" if result.upserted_id is not None else "updated"

    def get_all_series(self) -> List[Dict[str, Any]]:
        """
        Fetch every series document currently stored.

        Used by the recommendation engine (recommender/build_model.py) to
        read the full catalog when (re)building the TF-IDF model. Not
        paginated: the current catalog sizes this project deals with are
        small enough to load into memory in one shot, and re-fetching
        everything is exactly what a "rebuild the model" step should do.

        Returns:
            A list of all series documents (each a plain dict, including
            Mongo's `_id`).

        Raises:
            MongoDatabaseError: If the query fails.
        """
        try:
            return list(self.series.find({}))
        except PyMongoError as exc:
            logger.error("Failed to fetch all series documents: %s", exc)
            raise MongoDatabaseError(f"Failed to fetch all series documents: {exc}") from exc

    def get_series_by_id(self, tvmaze_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch a single series document by its `tvmaze_id`.

        Args:
            tvmaze_id: TVmaze show ID to look up.

        Returns:
            The matching series document, or None if no series with that
            `tvmaze_id` exists.

        Raises:
            MongoDatabaseError: If the query fails.
        """
        try:
            return self.series.find_one({"tvmaze_id": tvmaze_id})
        except PyMongoError as exc:
            logger.error("Failed to fetch series tvmaze_id=%s: %s", tvmaze_id, exc)
            raise MongoDatabaseError(f"Failed to fetch series tvmaze_id={tvmaze_id}: {exc}") from exc

    def get_series_count(self) -> int:
        """
        Count the total number of series documents stored.

        Returns:
            The total document count in the `series` collection.

        Raises:
            MongoDatabaseError: If the count query fails.
        """
        try:
            return self.series.count_documents({})
        except PyMongoError as exc:
            logger.error("Failed to count series documents: %s", exc)
            raise MongoDatabaseError(f"Failed to count series documents: {exc}") from exc

    def close(self) -> None:
        """Close the underlying MongoDB connection."""
        self._client.close()

    def __enter__(self) -> "MongoDBManager":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
