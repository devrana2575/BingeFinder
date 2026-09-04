"""
database/interaction_events.py
==============================
Logs user interaction events for the contextual bandit reward signal.

Event types and their rewards:
    POSITIVE:
        view_details    +1.0
        like            +3.0
        watchlist_add   +4.0
        provider_click  +4.0
        return_visit    +3.0

    NEGATIVE:
        unlike          -3.0
        watchlist_remove -4.0
        skip            -1.0
        dismiss         -2.0
        immediate_back  -1.0

Design:
    - Append-only event log (no updates/deletes).
    - Indexed on (user_id, timestamp) for fast per-user queries.
    - Indexed on (event_type) for aggregation queries.
    - Indexed on (session_id, user_id) for session queries.
    - TTL index on timestamp (90 days) to auto-prune old events.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from database.mongo_client import MongoDatabaseError, MongoDBManager
from utils.logger import get_logger

logger = get_logger(__name__)

EVENTS_COLLECTION_NAME = "interaction_events"
EVENT_TTL_DAYS = 90

# ---------------------------------------------------------------------------
# Reward weights — centralized, configurable.
# These are the STARTING values. Adjust based on evaluation.
# ---------------------------------------------------------------------------
REWARD_WEIGHTS: Dict[str, float] = {
    # Positive signals
    "view_details": 1.0,
    "like": 3.0,
    "watchlist_add": 4.0,
    "provider_click": 4.0,
    "return_visit": 3.0,
    # Negative signals
    "unlike": -3.0,
    "watchlist_remove": -4.0,
    "skip": -1.0,
    "dismiss": -2.0,
    "immediate_back": -1.0,
}

# Minimum events before the adaptive ranker trusts the signal
MIN_EVENTS_FOR_TRAINING = 10


class InteractionEventManager:
    """
    Append-only event log for user interactions.

    Usage:
        mongo_manager = MongoDBManager()
        iem = InteractionEventManager(mongo_manager)
        iem.log_event("user_id_abc", "like", series_id=1234)
    """

    def __init__(self, mongo_manager: MongoDBManager) -> None:
        self._mongo = mongo_manager
        try:
            self._collection: Collection = mongo_manager._db[EVENTS_COLLECTION_NAME]
        except PyMongoError as exc:
            logger.error("Failed to access interaction_events collection: %s", exc)
            raise MongoDatabaseError(
                f"Failed to access interaction_events collection: {exc}"
            ) from exc

        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """Create indexes for fast queries and auto-expiry."""
        try:
            self._collection.create_index(
                [("user_id", 1), ("timestamp", -1)],
                name="idx_events_user_time",
            )
            self._collection.create_index(
                [("event_type", 1)],
                name="idx_events_type",
            )
            self._collection.create_index(
                [("session_id", 1), ("user_id", 1)],
                name="idx_events_session",
            )
            self._collection.create_index(
                "timestamp",
                expireAfterSeconds=EVENT_TTL_DAYS * 86400,
                name="idx_events_ttl",
            )
        except PyMongoError as exc:
            logger.error("Failed to create indexes on interaction_events: %s", exc)

    def log_event(
        self,
        user_id: str,
        event_type: str,
        series_id: Optional[int] = None,
        source_series_id: Optional[int] = None,
        session_id: Optional[str] = None,
        position: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        Log a user interaction event.

        Returns the reward value (computed server-side, never from the client).
        """
        reward = REWARD_WEIGHTS.get(event_type, 0.0)

        document: Dict[str, Any] = {
            "user_id": user_id,
            "event_type": event_type,
            "series_id": series_id,
            "source_series_id": source_series_id,
            "session_id": session_id,
            "position": position,
            "reward": reward,
            "context": context or {},
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

        # Remove None fields to keep documents clean
        document = {k: v for k, v in document.items() if v is not None}

        try:
            self._collection.insert_one(document)
        except PyMongoError as exc:
            logger.error("Failed to log event for user %s: %s", user_id, exc)

        return reward

    def get_events_for_user(
        self,
        user_id: str,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve events for a user, optionally filtered by type.
        Returns most recent events first.
        """
        query: Dict[str, Any] = {"user_id": user_id}
        if event_type:
            query["event_type"] = event_type
        try:
            return list(
                self._collection.find(query)
                .sort("timestamp", -1)
                .limit(limit)
            )
        except PyMongoError as exc:
            logger.error("Failed to get events for user %s: %s", user_id, exc)
            return []

    def get_total_reward(self, user_id: str, series_id: int) -> float:
        """Sum of all rewards a user has generated for a specific series."""
        try:
            pipeline = [
                {"$match": {"user_id": user_id, "series_id": series_id}},
                {"$group": {"_id": None, "total_reward": {"$sum": "$reward"}}},
            ]
            result = list(self._collection.aggregate(pipeline))
            return result[0]["total_reward"] if result else 0.0
        except PyMongoError as exc:
            logger.error("Failed to compute reward for user %s, series_id=%s: %s", user_id, series_id, exc)
            return 0.0

    def get_user_event_counts(self, user_id: str) -> Dict[str, int]:
        """Return {event_type: count} for a user."""
        try:
            pipeline = [
                {"$match": {"user_id": user_id}},
                {"$group": {"_id": "$event_type", "count": {"$sum": 1}}},
            ]
            return {r["_id"]: r["count"] for r in self._collection.aggregate(pipeline)}
        except PyMongoError as exc:
            logger.error("Failed to get event counts for user %s: %s", user_id, exc)
            return {}

    def get_reward_matrix(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Return [{series_id, total_reward, event_count}] per series for a user.
        Used to build the contextual bandit's reward signal.
        """
        try:
            pipeline = [
                {"$match": {"user_id": user_id}},
                {
                    "$group": {
                        "_id": "$series_id",
                        "total_reward": {"$sum": "$reward"},
                        "event_count": {"$sum": 1},
                    }
                },
                {"$sort": {"total_reward": -1}},
            ]
            return [
                {"series_id": r["_id"], "total_reward": r["total_reward"], "event_count": r["event_count"]}
                for r in self._collection.aggregate(pipeline)
                if r["_id"] is not None
            ]
        except PyMongoError as exc:
            logger.error("Failed to build reward matrix for user %s: %s", user_id, exc)
            return []

    def get_total_event_count(self, user_id: str) -> int:
        """Total number of events for a user."""
        try:
            return self._collection.count_documents({"user_id": user_id})
        except PyMongoError:
            return 0

    def get_all_training_data(self) -> List[Dict[str, Any]]:
        """
        Return all events for offline training/evaluation.
        Used by train_ranker.py — not called during normal requests.
        """
        try:
            return list(self._collection.find(
                {"user_id": {"$exists": True}},
                {"_id": 0}
            ).sort("timestamp", 1))
        except PyMongoError as exc:
            logger.error("Failed to get training data: %s", exc)
            return []
