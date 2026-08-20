"""
database/likes.py
==================
User-specific like/unlike functionality backed by MongoDB.

Design notes:
    - A compound unique index on ``(user_id, tvmaze_id)`` prevents
      duplicate likes per user.
    - Each user can like a series only once.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List

from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from database.mongo_client import MongoDatabaseError, MongoDBManager
from utils.logger import get_logger

logger = get_logger(__name__)

LIKES_COLLECTION_NAME = "likes"


class LikesManager:
    """
    Manages user likes in the ``likes`` collection.

    Usage:
        mongo_manager = MongoDBManager()
        lm = LikesManager(mongo_manager)
        lm.like("user_id_abc", 1234)
        liked = lm.is_liked("user_id_abc", 1234)
    """

    def __init__(self, mongo_manager: MongoDBManager) -> None:
        self._mongo = mongo_manager
        try:
            self._collection: Collection = mongo_manager._db[LIKES_COLLECTION_NAME]
        except PyMongoError as exc:
            logger.error("Failed to access likes collection: %s", exc)
            raise MongoDatabaseError(f"Failed to access likes collection: {exc}") from exc

        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """Create compound unique index on (user_id, tvmaze_id)."""
        try:
            self._collection.create_index(
                [("user_id", 1), ("tvmaze_id", 1)],
                unique=True,
                name="uniq_likes_user_series",
            )
        except PyMongoError as exc:
            logger.error("Failed to create unique index on likes: %s", exc)
            raise MongoDatabaseError(
                f"Failed to create unique index on likes: {exc}"
            ) from exc

    def like(self, user_id: str, tvmaze_id: int) -> str:
        """
        Like a series for a user.

        Returns:
            ``"liked"`` or ``"already_liked"``.
        """
        document = {
            "user_id": user_id,
            "tvmaze_id": tvmaze_id,
            "liked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        try:
            self._collection.insert_one(document)
            logger.info("User %s liked tvmaze_id=%s.", user_id, tvmaze_id)
            return "liked"
        except PyMongoError as exc:
            if exc.code == 11000:
                return "already_liked"
            logger.error("Failed to like tvmaze_id=%s for user %s: %s", tvmaze_id, user_id, exc)
            raise MongoDatabaseError(
                f"Failed to like series: {exc}"
            ) from exc

    def unlike(self, user_id: str, tvmaze_id: int) -> str:
        """
        Unlike a series for a user.

        Returns:
            ``"unliked"`` or ``"not_found"``.
        """
        try:
            result = self._collection.delete_one(
                {"user_id": user_id, "tvmaze_id": tvmaze_id}
            )
            if result.deleted_count:
                logger.info("User %s unliked tvmaze_id=%s.", user_id, tvmaze_id)
                return "unliked"
            return "not_found"
        except PyMongoError as exc:
            logger.error("Failed to unlike tvmaze_id=%s for user %s: %s", tvmaze_id, user_id, exc)
            raise MongoDatabaseError(
                f"Failed to unlike series: {exc}"
            ) from exc

    def is_liked(self, user_id: str, tvmaze_id: int) -> bool:
        """Check if a user has liked a series."""
        try:
            return self._collection.find_one(
                {"user_id": user_id, "tvmaze_id": tvmaze_id}
            ) is not None
        except PyMongoError as exc:
            logger.error("Failed to check like for user %s, tvmaze_id=%s: %s", user_id, tvmaze_id, exc)
            return False

    def get_liked_series(self, user_id: str) -> List[Dict[str, Any]]:
        """Return all like documents for a user, sorted by liked_at desc."""
        try:
            return list(
                self._collection.find({"user_id": user_id}).sort("liked_at", -1)
            )
        except PyMongoError as exc:
            logger.error("Failed to get likes for user %s: %s", user_id, exc)
            raise MongoDatabaseError(f"Failed to get likes: {exc}") from exc

    def get_liked_series_ids(self, user_id: str) -> List[int]:
        """Return just the tvmaze_ids of liked series for a user."""
        likes = self.get_liked_series(user_id)
        return [l["tvmaze_id"] for l in likes if "tvmaze_id" in l]

    def get_liked_count(self, user_id: str) -> int:
        """Return the number of liked series for a user."""
        try:
            return self._collection.count_documents({"user_id": user_id})
        except PyMongoError as exc:
            logger.error("Failed to count likes for user %s: %s", user_id, exc)
            return 0
