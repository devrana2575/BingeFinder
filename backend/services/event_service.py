"""
backend/services/event_service.py
===================================
Handles event recording with duplicate protection and session management.
Backend determines rewards — never trusts client-sent reward values.
"""

import hashlib
import time
from typing import Any, Dict, Optional, Tuple

from database.mongo_client import MongoDBManager


def _connect() -> Tuple[MongoDBManager, None] | Tuple[None, str]:
    try:
        return MongoDBManager(), None
    except Exception as exc:
        return None, str(exc)


def record_event(
    user_id: str,
    event_type: str,
    series_id: Optional[int] = None,
    source_series_id: Optional[int] = None,
    session_id: Optional[str] = None,
    position: Optional[int] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[float], Optional[str]]:
    """
    Record a user interaction event with duplicate protection.

    Returns (reward, error). Reward is always computed server-side.
    """
    from database.interaction_events import InteractionEventManager, REWARD_WEIGHTS

    if event_type not in REWARD_WEIGHTS:
        return None, f"Unknown event type: {event_type}"

    manager, err = _connect()
    if err:
        return None, err

    try:
        iem = InteractionEventManager(manager)

        # Duplicate protection: hash of user+event+series+session within 2-second window
        dedup_key = hashlib.md5(
            f"{user_id}:{event_type}:{series_id}:{session_id}:{int(time.time())}".encode()
        ).hexdigest()

        # Check for very recent duplicate (within 2 seconds)
        recent = manager._db["interaction_events"].find_one({
            "user_id": user_id,
            "event_type": event_type,
            "series_id": series_id,
            "dedup_key": dedup_key[:8],
        })
        if recent:
            return REWARD_WEIGHTS[event_type], None  # Already recorded

        # Add dedup key to context for protection
        ctx = dict(context or {})
        ctx["dedup_key"] = dedup_key[:8]

        reward = iem.log_event(
            user_id=user_id,
            event_type=event_type,
            series_id=series_id,
            source_series_id=source_series_id,
            session_id=session_id,
            position=position,
            context=ctx,
        )
        return reward, None
    except Exception as exc:
        return None, f"Failed to record event: {exc}"
    finally:
        manager.close()


def get_adaptive_status(user_id: str) -> Dict[str, Any]:
    """
    Check the adaptive ranker status for a user.

    Returns:
        {
            "status": "cold_start" | "collecting_data" | "trained",
            "event_count": int,
            "reward_matrix_size": int,
        }
    """
    from database.interaction_events import InteractionEventManager, MIN_EVENTS_FOR_TRAINING

    manager, err = _connect()
    if err:
        return {"status": "cold_start", "event_count": 0, "reward_matrix_size": 0}

    try:
        iem = InteractionEventManager(manager)
        event_count = iem.get_total_event_count(user_id)
        reward_matrix = iem.get_reward_matrix(user_id)
        non_zero = sum(1 for r in reward_matrix if r["total_reward"] != 0)

        if event_count < MIN_EVENTS_FOR_TRAINING:
            status = "cold_start"
        elif non_zero < 5:
            status = "collecting_data"
        else:
            status = "trained"

        return {
            "status": status,
            "event_count": event_count,
            "reward_matrix_size": len(reward_matrix),
        }
    finally:
        manager.close()
