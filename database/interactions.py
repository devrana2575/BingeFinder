"""
database/interactions.py
=========================
Unified user → series reaction model: LIKE, LOVE, and NOT FOR ME (dislike).

One reaction per (user, series) — a unique compound index enforces this, so
a user can never have contradictory reactions on the same title. Setting a
new reaction overwrites the previous one (upsert), keeping one clean record.

Reaction semantics (used by the personalization layer):
    love     strong positive
    like     positive
    dislike  negative (actively suppresses similar content)
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from database.mongo_client import MongoDatabaseError, MongoDBManager
from utils.logger import get_logger

logger = get_logger(__name__)

INTERACTIONS_COLLECTION_NAME = "interactions"

# Valid reaction values
REACTION_LOVE = "love"
REACTION_LIKE = "like"
REACTION_DISLIKE = "dislike"
VALID_REACTIONS = {REACTION_LOVE, REACTION_LIKE, REACTION_DISLIKE}

# Personalization impact per reaction.
# A LOVE is stronger than a LIKE; a DISLIKE is actively negative.
REACTION_WEIGHTS: Dict[str, float] = {
    REACTION_LOVE: 5.0,
    REACTION_LIKE: 3.0,
    REACTION_DISLIKE: -6.0,
}


class InteractionManager:
    """
    Manages per-user LIKE/LOVE/DISLIKE reactions on series.

    Usage:
        mongo_manager = MongoDBManager()
        im = InteractionManager(mongo_manager)
        im.set_reaction(user_id, 1234, "love")
        im.get_reaction(user_id, 1234)  # "love" | "like" | "dislike" | None
        im.clear_reaction(user_id, 1234)
    """

    def __init__(self, mongo_manager: MongoDBManager) -> None:
        self._mongo = mongo_manager
        try:
            self._collection: Collection = mongo_manager._db[INTERACTIONS_COLLECTION_NAME]
        except PyMongoError as exc:
            logger.error("Failed to access interactions collection: %s", exc)
            raise MongoDatabaseError(
                f"Failed to access interactions collection: {exc}"
            ) from exc
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """Create a compound unique index on (user_id, series_id)."""
        try:
            self._collection.create_index(
                [("user_id", 1), ("series_id", 1)],
                unique=True,
                name="uniq_interaction_user_series",
            )
        except PyMongoError as exc:
            logger.error("Failed to create unique index on interactions: %s", exc)
            raise MongoDatabaseError(
                f"Failed to create unique index on interactions: {exc}"
            ) from exc

    def set_reaction(
        self, user_id: str, series_id: int, reaction: str
    ) -> str:
        """
        Set (create or overwrite) a user's reaction to a series.

        Returns:
            "set" if written.

        Raises:
            ValueError: If `reaction` is not a valid reaction value.
            MongoDatabaseError: If the write fails.
        """
        if reaction not in VALID_REACTIONS:
            raise ValueError(
                f"Invalid reaction '{reaction}'. Must be one of {sorted(VALID_REACTIONS)}."
            )

        document = {
            "user_id": user_id,
            "series_id": series_id,
            "reaction": reaction,
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        try:
            self._collection.update_one(
                {"user_id": user_id, "series_id": series_id},
                {"$set": document},
                upsert=True,
            )
            logger.info(
                "User %s set reaction '%s' on series_id=%s.", user_id, reaction, series_id
            )
            return "set"
        except PyMongoError as exc:
            logger.error(
                "Failed to set reaction '%s' on series_id=%s for user %s: %s",
                reaction, series_id, user_id, exc,
            )
            raise MongoDatabaseError(f"Failed to set reaction: {exc}") from exc

    def clear_reaction(self, user_id: str, series_id: int) -> str:
        """
        Remove any reaction a user has on a series.

        Returns:
            "cleared" if a reaction was removed, "not_found" otherwise.
        """
        try:
            result = self._collection.delete_one(
                {"user_id": user_id, "series_id": series_id}
            )
            if result.deleted_count:
                return "cleared"
            return "not_found"
        except PyMongoError as exc:
            logger.error(
                "Failed to clear reaction on series_id=%s for user %s: %s",
                series_id, user_id, exc,
            )
            raise MongoDatabaseError(f"Failed to clear reaction: {exc}") from exc

    def get_reaction(self, user_id: str, series_id: int) -> Optional[str]:
        """Return the user's reaction ('love'/'like'/'dislike') or None."""
        try:
            doc = self._collection.find_one(
                {"user_id": user_id, "series_id": series_id}
            )
            return doc.get("reaction") if doc else None
        except PyMongoError as exc:
            logger.error(
                "Failed to check reaction for user %s, series_id=%s: %s",
                user_id, series_id, exc,
            )
            return None

    def get_reactions(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Return all reaction documents for a user, most recently updated first.
        """
        try:
            return list(
                self._collection.find({"user_id": user_id}).sort("updated_at", -1)
            )
        except PyMongoError as exc:
            logger.error("Failed to get reactions for user %s: %s", user_id, exc)
            raise MongoDatabaseError(f"Failed to get reactions: {exc}") from exc

    def get_reaction_map(self, user_id: str) -> Dict[int, str]:
        """Return {series_id: reaction} for all the user's reactions."""
        return {
            doc["series_id"]: doc["reaction"]
            for doc in self.get_reactions(user_id)
            if doc.get("series_id") is not None and doc.get("reaction") in VALID_REACTIONS
        }

    def get_series_with_reaction(self, user_id: str, reaction: str) -> List[int]:
        """Return the series_ids the user reacted to with a specific reaction."""
        if reaction not in VALID_REACTIONS:
            return []
        return [
            doc["series_id"]
            for doc in self.get_reactions(user_id)
            if doc.get("reaction") == reaction and doc.get("series_id") is not None
        ]
