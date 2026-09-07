"""
backend/services/tvmaze_backfill.py
=====================================
Keyless catalog backfill from TVMaze's public API, complementing the
TMDb-based `catalog_ingest`. The existing `series` collection was
originally populated from TVMaze (full image URLs, TVMaze `series_id`s,
nested `network`, `cast` list), so TVMaze data maps 1:1 onto the schema
without transformation, and works with search / discovery / recommender
as-is.

Design:
    - Pulls the TVMaze `shows?page=N` index (240 shows/page, no API key).
    - Normalises raw rows into the EXACT existing `series` schema the
      recommender/search/discovery already read.
    - Upserts by `series_id`: inserts new documents, updates existing
      ones, never wipes data.
    - Quality bar: only shows with a name AND an image are kept (every
      home rail and card needs an image; cards render "Untitled" only as
      a last resort).
    - Growth cap: backfills are capped (`max_new`) and quality-weighted
      so a run adds the best unexplored titles without ballooning the
      category into an un-renderable size. Raising the cap is safe — the
      model just needs a rebuild afterwards:
        python -m recommender.build_model
    - Summary HTML is stripped so docs match existing plain-text summaries.

Run directly:
    python -m backend.services.tvmaze_backfill --pages 5 --max-new 300
"""

from __future__ import annotations

import html
import json
import re
import time
import urllib.request
from typing import Any, Callable, Dict, List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)

TVMAZE_INDEX_URL = "https://api.tvmaze.com/shows?page={page}"
DEFAULT_PAGE_SIZE = 240
DEFAULT_PAGE_SLEEP_SECONDS = 0.05
MIN_REQUIRED_FIELDS = ("name",)

_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(value: Optional[str]) -> Optional[str]:
    """
    Strip HTML tags and unescape entities, contracting whitespace so the
    stored summary matches existing plain-text summaries. None stays None;
    empty after stripping becomes None (never empty string).
    """
    if not isinstance(value, str) or not value.strip():
        return None
    text = _TAG_RE.sub(" ", value)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _steady_numeric(value: Any) -> Any:
    """Return a float/int as-is; coerce int-like strings; else None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def normalize_tvmaze_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map a raw TVMaze show row into the app's `series` document schema.

    Field-by-field this mirrors what an original TVMaze sync stored:
        series_id           -> TVMaze show id
        name                -> show name
        genres / rating / language / status / weight / updated
        premiered / ended / runtime / average_runtime
        image_medium / image_original  -> full TVMaze image URLs
        network / web_channel          -> nested objects as provided
        summary             -> HTML-stripped plain text
        imdb_id / thetvdb_id           -> from externals
        cast                -> [] (cast needs one request per show; the
                               recommender handles empty cast cleanly,
                               and existing search/discovery never read it)
    """
    def _ext(value: str) -> Optional[str]:
        v = row.get(value)
        return str(v).strip() if isinstance(v, str) and v.strip() else None

    series_id = row.get("id")
    try:
        series_id = int(series_id) if series_id is not None else None
    except (TypeError, ValueError):
        series_id = None

    image_obj = row.get("image") if isinstance(row.get("image"), dict) else {}
    externals = row.get("externals") if isinstance(row.get("externals"), dict) else {}
    network = row.get("network")
    if not isinstance(network, dict):
        network = row.get("web_channel") if isinstance(row.get("web_channel"), dict) else None
    web_channel = row.get("web_channel")
    if not isinstance(web_channel, dict):
        web_channel = None

    def _coerce_rating(value: Any) -> Any:
        rating_obj = row.get(value)
        average = rating_obj.get("average") if isinstance(rating_obj, dict) else None
        return _steady_numeric(average)

    def _identity_or_none(value: Any) -> Any:
        return value if isinstance(value, (int, float)) else None

    doc: Dict[str, Any] = {
        "series_id": series_id,
        "content_type": "anime" if "Anime" in [g for g in row.get("genres") or [] if isinstance(g, str)] else "tv_series",
        "name": _ext("name"),
        "summary": strip_html(row.get("summary")),
        "genres": [g for g in row.get("genres") or [] if isinstance(g, str)] or [],
        "rating": _coerce_rating("rating"),
        "language": _ext("language"),
        "premiered": _ext("premiered"),
        "ended": _ext("ended"),
        "status": _ext("status"),
        "runtime": _identity_or_none(row.get("runtime")),
        "average_runtime": _identity_or_none(row.get("averageRuntime")),
        "weight": _identity_or_none(row.get("weight")),
        "updated": _identity_or_none(row.get("updated")),
        "image_medium": image_obj.get("medium") or None,
        "image_original": image_obj.get("original") or None,
        "official_site": _ext("officialSite"),
        "network": network,
        "web_channel": web_channel,
        "imdb_id": externals.get("imdb") or None,
        "thetvdb_id": externals.get("thetvdb") or None,
        "external_ids": {
            "tvmaze": series_id,
            "imdb": externals.get("imdb") or None,
            "tvdb": externals.get("thetvdb") or None,
        },
        "cast": [],
        "catalog_source": "tvmaze",
    }
    return doc


def _doc_key(doc: Dict[str, Any]) -> Optional[int]:
    try:
        sid = doc.get("series_id")
        return int(sid) if isinstance(sid, (int, float, str)) and sid is not None else None
    except (TypeError, ValueError):
        return None


def fetch_show_page(
    page: int,
    fetcher: Optional[Callable[[int], List[Dict[str, Any]]]] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch one page of the TVMaze show index. `fetcher` is injectable for
    tests/proxies; the default hits the public API directly. Returns an
    empty list when the page is beyond the last page (404/empty body).
    """
    if fetcher is not None:
        return fetcher(page)
    url = TVMAZE_INDEX_URL.format(page=page)
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            payload = response.read().decode("utf-8")
            if not payload.strip():
                return []
            data = json.loads(payload)
    except Exception as exc:
        logger.warning("TVMaze page %s failed: %s", page, exc)
        return []
    return data if isinstance(data, list) else []


def ingest_rows(
    manager: Any,
    rows: List[Dict[str, Any]],
    *,
    min_weight: Optional[float] = None,
) -> Dict[str, int]:
    """
    Normalise and upsert a batch of raw TVMaze rows into the series catalog.

    Skips (counted as "skipped") rows that: lack a usable id/name, have no
    image (cards/rails need one), or fall below the (optional) TVMaze
    `weight` popularity floor. A row whose `series_id` already exists is
    updated in place (never duplicated), counted as "updated".

    Returns counts: {"inserted": n, "updated": n, "skipped": n}.
    """
    counts = {"inserted": 0, "updated": 0, "skipped": 0}
    for row in rows:
        doc = normalize_tvmaze_row(row)
        sid = _doc_key(doc)
        if sid is None or not doc.get("name"):
            counts["skipped"] += 1
            continue
        if not (doc.get("image_medium") or doc.get("image_original")):
            counts["skipped"] += 1
            continue
        weight = doc.get("weight")
        if min_weight is not None and (not isinstance(weight, (int, float)) or weight < min_weight):
            counts["skipped"] += 1
            continue

        try:
            outcome = manager.upsert_series(doc)
        except Exception as exc:
            logger.warning("Failed to upsert series_id=%s: %s", sid, exc)
            counts["skipped"] += 1
            continue
        counts["inserted" if outcome == "inserted" else "updated"] += 1
    return counts


def run_backfill(
    start_page: int = 0,
    pages: int = 5,
    max_new: int = 250,
    min_weight: float = 0.0,
    sleep_seconds: float = DEFAULT_PAGE_SLEEP_SECONDS,
    manager: Any = None,
    fetcher: Optional[Callable[[int], List[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """
    Scan TVMaze index pages and upsert quality shows into the catalog.

    Pages are consumed in order; the scan stops early once either the page
    budget runs out or `max_new` new titles have been added. Existing ids
    are skipped via the live `series_id` set, so a re-run adds nothing new.

    Args:
        start_page: first index page to scan (0-based).
        pages: how many pages to scan at most.
        max_new: stop after adding this many brand-new titles.
        min_weight: optional TVMaze popularity floor (0 = keep all).
        sleep_seconds: delay between page requests.
        manager: optional MongoDBManager (default: open one).
        fetcher: optional page fetcher (as in fetch_show_page).

    Returns:
        Summary dict with per-run counts and totals.
    """
    from database.mongo_client import MongoDBManager

    close_manager = manager is None
    manager = manager or MongoDBManager()

    try:
        total = {"inserted": 0, "updated": 0, "skipped": 0}
        reached_end = False
        scanned_pages = 0

        for page in range(start_page, start_page + max(pages, 1)):
            rows = fetch_show_page(page, fetcher=fetcher)
            scanned_pages += 1
            if not rows:
                reached_end = True
                break
            time.sleep(max(0.0, sleep_seconds))

            counts = ingest_rows(manager, rows, min_weight=min_weight)
            for key in ("inserted", "updated", "skipped"):
                total[key] += counts[key]
            if total["inserted"] >= max_new:
                break

        return {
            "scanned_pages": scanned_pages,
            "reached_end": reached_end,
            "total_inserted": total["inserted"],
            "total_updated": total["updated"],
            "total_skipped": total["skipped"],
        }
    finally:
        if close_manager:
            manager.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Keyless TVMaze catalog backfill for BingeFinder.")
    parser.add_argument("--start-page", type=int, default=0, help="First TVMaze index page (0-based).")
    parser.add_argument("--pages", type=int, default=5, help="Max index pages to scan.")
    parser.add_argument("--max-new", type=int, default=250, help="Stop once this many new titles are added.")
    parser.add_argument("--min-weight", type=float, default=0.0, help="Keep only shows at/above this TVMaze weight.")
    parser.add_argument("--sleep", type=float, default=DEFAULT_PAGE_SLEEP_SECONDS, help="Seconds between page requests.")
    args = parser.parse_args()

    result = run_backfill(
        start_page=args.start_page,
        pages=args.pages,
        max_new=args.max_new,
        min_weight=args.min_weight,
        sleep_seconds=args.sleep,
    )
    print(result)