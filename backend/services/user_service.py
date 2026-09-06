"""
backend/services/user_service.py
==================================
Wraps watchlist/likes/recently_viewed managers.
"""

from typing import Any, Dict, List, Optional, Tuple

from database.mongo_client import MongoDBManager


def _connect() -> Tuple[MongoDBManager, None] | Tuple[None, str]:
    try:
        return MongoDBManager(), None
    except Exception as exc:
        return None, str(exc)


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------

def get_watchlist(user_id: str) -> Tuple[List[Dict], Optional[str]]:
    manager, err = _connect()
    if err:
        return [], err
    try:
        from database.watchlist import WatchlistManager
        wl = WatchlistManager(manager)
        watchlist_docs = wl.get_watchlist(user_id)

        from backend.services.series_service import get_all_series
        docs, _ = get_all_series()
        series_map = {d["series_id"]: d for d in docs if d.get("series_id") is not None}

        result = []
        for wl_doc in watchlist_docs:
            sid = wl_doc.get("series_id")
            if sid in series_map:
                entry = dict(series_map[sid])
                entry["added_at"] = wl_doc.get("added_at")
                result.append(entry)
        return result, None
    except Exception as exc:
        return [], f"Could not load watchlist: {exc}"
    finally:
        manager.close()


def add_to_watchlist(user_id: str, series_id: int) -> Tuple[bool, Optional[str]]:
    manager, err = _connect()
    if err:
        return False, err
    try:
        from database.watchlist import WatchlistManager
        wl = WatchlistManager(manager)
        result = wl.add_to_watchlist(user_id, series_id)
        return True, None
    except Exception as exc:
        return False, f"Could not add to watchlist: {exc}"
    finally:
        manager.close()


def remove_from_watchlist(user_id: str, series_id: int) -> Tuple[bool, Optional[str]]:
    manager, err = _connect()
    if err:
        return False, err
    try:
        from database.watchlist import WatchlistManager
        wl = WatchlistManager(manager)
        wl.remove_from_watchlist(user_id, series_id)
        return True, None
    except Exception as exc:
        return False, f"Could not remove from watchlist: {exc}"
    finally:
        manager.close()


# ---------------------------------------------------------------------------
# Likes
# ---------------------------------------------------------------------------

def get_likes(user_id: str) -> Tuple[List[Dict], Optional[str]]:
    manager, err = _connect()
    if err:
        return [], err
    try:
        from database.likes import LikesManager
        lm = LikesManager(manager)
        liked_docs = lm.get_liked_series(user_id)

        from backend.services.series_service import get_all_series
        docs, _ = get_all_series()
        series_map = {d["series_id"]: d for d in docs if d.get("series_id") is not None}

        result = []
        for lk_doc in liked_docs:
            sid = lk_doc.get("series_id")
            if sid in series_map:
                entry = dict(series_map[sid])
                entry["liked_at"] = lk_doc.get("liked_at")
                result.append(entry)
        return result, None
    except Exception as exc:
        return [], f"Could not load liked series: {exc}"
    finally:
        manager.close()


def like_series(user_id: str, series_id: int) -> Tuple[bool, Optional[str]]:
    manager, err = _connect()
    if err:
        return False, err
    try:
        from database.likes import LikesManager
        lm = LikesManager(manager)
        lm.like(user_id, series_id)
        return True, None
    except Exception as exc:
        return False, f"Could not like series: {exc}"
    finally:
        manager.close()


def unlike_series(user_id: str, series_id: int) -> Tuple[bool, Optional[str]]:
    manager, err = _connect()
    if err:
        return False, err
    try:
        from database.likes import LikesManager
        lm = LikesManager(manager)
        lm.unlike(user_id, series_id)
        return True, None
    except Exception as exc:
        return False, f"Could not unlike series: {exc}"
    finally:
        manager.close()


# ---------------------------------------------------------------------------
# Recently Viewed
# ---------------------------------------------------------------------------

def get_recently_viewed(user_id: str, limit: int = 20) -> Tuple[List[Dict], Optional[str]]:
    manager, err = _connect()
    if err:
        return [], err
    try:
        from database.recently_viewed import RecentlyViewedManager
        rvm = RecentlyViewedManager(manager)
        recent_docs = rvm.get_recently_viewed(user_id, limit)

        from backend.services.series_service import get_all_series
        docs, _ = get_all_series()
        series_map = {d["series_id"]: d for d in docs if d.get("series_id") is not None}

        result = []
        for rv_doc in recent_docs:
            sid = rv_doc.get("series_id")
            if sid in series_map:
                entry = dict(series_map[sid])
                entry["viewed_at"] = rv_doc.get("viewed_at")
                result.append(entry)
        return result, None
    except Exception as exc:
        return [], f"Could not load recently viewed: {exc}"
    finally:
        manager.close()


def record_view(user_id: str, series_id: int) -> None:
    manager, err = _connect()
    if err:
        return
    try:
        from database.recently_viewed import RecentlyViewedManager
        rvm = RecentlyViewedManager(manager)
        rvm.record_view(user_id, series_id)
    except Exception:
        pass
    finally:
        manager.close()


# ---------------------------------------------------------------------------
# Settings / preferences
# ---------------------------------------------------------------------------

def get_settings(user_id: str) -> Tuple[Dict, Optional[str]]:
    manager, err = _connect()
    if err:
        return {}, err
    try:
        from database.users import UserManager
        um = UserManager(manager)
        return um.get_preferences(user_id), None
    except Exception as exc:
        return {}, f"Could not load settings: {exc}"
    finally:
        manager.close()


def update_settings(user_id: str, settings: Dict) -> Tuple[bool, Optional[str]]:
    manager, err = _connect()
    if err:
        return False, err
    try:
        from database.users import UserManager
        um = UserManager(manager)
        # Merge: an update only touches the provided fields.
        current = um.get_preferences(user_id)
        current.update({k: v for k, v in settings.items() if v is not None})
        ok = um.update_preferences(user_id, current)
        return (True, None) if ok else (False, "User not found.")
    except Exception as exc:
        return False, f"Could not save settings: {exc}"
    finally:
        manager.close()
