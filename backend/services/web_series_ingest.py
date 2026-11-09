"""
backend/services/web_series_ingest.py
=====================================
Rebuild BingeFinder's "Web Series" catalog from streaming platforms only.

Why this exists
---------------
TMDb's `tv` catalog mixes broadcast/cable TV with streaming originals and
has no "web series" flag. Streaming originals *do* carry their platform in
the show's `networks` list, so this module uses that signal:

  1. Discover every TV title whose networks overlap a whitelist of
     streaming platforms (Netflix, Prime Video, Hotstar, SonyLIV, ...).
  2. Fetch details for every candidate in parallel and keep only titles
     whose **every** network is a streaming platform. Co-productions that
     also aired on a broadcast/cable network (e.g. a BBC One + Netflix
     show) are dropped, because they are still TV shows.
  3. Upsert the survivors with the existing `tv_series` bucket (the UI
     labels that bucket "Web Series") and record their streaming network.
  4. Hide every other legacy `tv_series` document by moving it to the
     unsupported `broadcast_tv` bucket. Nothing is deleted, so the sweep is
     reversible, but product-facing reads (search, rails, recommendations)
     stop returning broadcast TV immediately.

Anime is not affected: Japanese + Animation titles are re-classified as
`anime` by the shared normalizer, and existing anime docs stay untouched.

Run:
    python -m backend.services.web_series_ingest
    python -m backend.services.web_series_ingest --pages 20 --workers 8
    python -m backend.services.web_series_ingest --dry-run
"""

from __future__ import annotations

import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Set, Tuple

from api.tmdb import TMDbClient
from backend.services.catalog_ingest import normalize_tmdb_row
from database.mongo_client import MongoDBManager
from utils.logger import get_logger

logger = get_logger(__name__)

# TMDb network ids for streaming-only platforms. These are matched against
# the `networks` field returned by /tv/{id}; only titles whose entire network
# list is a subset of these ids are kept.
STREAMING_NETWORKS: Dict[int, str] = {
    213: "Netflix",
    1024: "Prime Video",
    453: "Hulu",
    2739: "Disney+",
    2552: "Apple TV+",
    3186: "Max",
    3353: "Peacock",
    4330: "Paramount+",
    3919: "Disney+ Hotstar",
    2646: "SonyLIV",
    2590: "ZEE5",
    4008: "JioCinema",
    2964: "MX Player",
    2112: "ALTBalaji",
    3758: "aha",
    2532: "Voot",
    1436: "YouTube Premium",
    247: "YouTube",
    1145: "TVFPlay",
    5920: "Amazon miniTV",
    7774: "Amazon MX Player",
    2139: "hoichoi",
    1025: "WWE Network",
}

_STREAMING_NAMES = {name.strip().lower() for name in STREAMING_NETWORKS.values()}

# Legacy/broadcast TV is parked here instead of being deleted. It is not in
# `series_service.SUPPORTED_CONTENT_TYPES`, so every product read ignores it.
HIDDEN_CONTENT_TYPE = "broadcast_tv"

DISCOVER_SORT = "popularity.desc"
DEFAULT_WORKERS = 10
DEFAULT_PAGE_SLEEP = 0.0
_PROGRESS_EVERY = 100


def _network_ids(details: Dict[str, Any]) -> Set[int]:
    ids: Set[int] = set()
    for network in details.get("networks") or []:
        nid = network.get("id")
        if isinstance(nid, int):
            ids.add(nid)
    return ids


def fetch_candidates(
    client: TMDbClient,
    max_pages: Optional[int] = None,
    sleep_seconds: float = DEFAULT_PAGE_SLEEP,
) -> List[Dict[str, Any]]:
    """Fetch every discover row that overlaps the streaming-network whitelist."""
    include = "|".join(str(nid) for nid in STREAMING_NETWORKS)
    page = 1
    total_pages = 1
    seen: Set[int] = set()
    rows: List[Dict[str, Any]] = []

    while page <= total_pages and (max_pages is None or page <= max_pages):
        payload = client._get(
            "/discover/tv",
            params={
                "with_networks": include,
                "sort_by": DISCOVER_SORT,
                "page": page,
                "include_adult": "false",
            },
        )
        try:
            total_pages = min(int(payload.get("total_pages") or 1), 500)
        except (TypeError, ValueError):
            total_pages = 1
        for row in payload.get("results") or []:
            rid = row.get("id")
            if isinstance(rid, int) and rid not in seen:
                seen.add(rid)
                rows.append(row)
        logger.info("Fetched discover page %d/%d (%d unique candidates)", page, total_pages, len(rows))
        page += 1
        if sleep_seconds:
            time.sleep(sleep_seconds)

    return rows


def _fetch_details(client: TMDbClient, tmdb_id: int) -> Tuple[int, Optional[Dict[str, Any]], Optional[str]]:
    try:
        return tmdb_id, client.fetch_tv_details(tmdb_id), None
    except Exception as exc:  # best-effort: a single failure must not stop the sweep
        return tmdb_id, None, str(exc)


def enrich_streaming_only(
    client: TMDbClient,
    rows: List[Dict[str, Any]],
    workers: int = DEFAULT_WORKERS,
) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """Keep only rows whose entire network list is streaming-only."""
    keep: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    errors = 0
    pending = [row for row in rows if isinstance(row.get("id"), int)]

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_fetch_details, client, int(row["id"])): row for row in pending}
        for done, future in enumerate(as_completed(futures), 1):
            row = futures[future]
            _tmdb_id, details, err = future.result()
            if err or not details:
                errors += 1
                continue
            ids = _network_ids(details)
            if not ids or not ids.issubset(STREAMING_NETWORKS.keys()):
                continue
            keep.append((row, details))
            if done % _PROGRESS_EVERY == 0:
                logger.info(
                    "Enriched %d/%d candidates (%d kept, %d errors)",
                    done, len(pending), len(keep), errors,
                )

    logger.info(
        "Enrichment finished: %d/%d kept, %d detail errors",
        len(keep), len(pending), errors,
    )
    return keep


def normalize_web_series(
    row: Dict[str, Any],
    details: Dict[str, Any],
    genre_map: Optional[Dict[int, str]] = None,
) -> Dict[str, Any]:
    """Build a catalog document for a verified streaming-only title."""
    doc = normalize_tmdb_row(row, genre_map=genre_map)

    # `normalize_tmdb_row` returns "anime" for Japanese animation and
    # "tv_series" otherwise. Keep anime; the rest is our web-series bucket.
    if doc.get("content_type") != "anime":
        doc["content_type"] = "tv_series"

    networks: List[Dict[str, Any]] = []
    for network in details.get("networks") or []:
        nid = network.get("id")
        name = network.get("name")
        if not isinstance(nid, int) or not name:
            continue
        country_code = network.get("origin_country")
        networks.append(
            {
                "id": nid,
                "name": name,
                "country": {"name": country_code, "code": country_code},
            }
        )
    doc["network"] = networks[0] if networks else None
    doc["networks"] = networks

    if details.get("status"):
        doc["status"] = details.get("status")
    if details.get("last_air_date"):
        doc["ended"] = details.get("last_air_date")
    if details.get("number_of_episodes") is not None:
        doc["episodes_count"] = details.get("number_of_episodes")
    if details.get("number_of_seasons") is not None:
        doc["seasons_count"] = details.get("number_of_seasons")
    if details.get("homepage"):
        doc["official_site"] = details.get("homepage")
    if details.get("origin_country"):
        doc["origin_country"] = details.get("origin_country")

    runtimes = [int(m) for m in details.get("episode_run_time") or [] if isinstance(m, int)]
    if runtimes:
        doc["average_runtime"] = sum(runtimes) / len(runtimes)

    doc["catalog_scope"] = "web_series"
    return doc


def _existing_streaming_ids(manager: MongoDBManager) -> Set[int]:
    """Legacy docs already carrying a streaming network name are kept too."""
    keep: Set[int] = set()
    cursor = manager.series.find(
        {"content_type": "tv_series"},
        {"series_id": 1, "network.name": 1, "web_channel": 1},
    )
    for doc in cursor:
        sid = doc.get("series_id")
        if not isinstance(sid, int):
            continue
        network = doc.get("network") or {}
        name = network.get("name") if isinstance(network, dict) else None
        channel = doc.get("web_channel")
        if isinstance(channel, dict):
            channel = channel.get("name")
        if (name and name.strip().lower() in _STREAMING_NAMES) or (
            isinstance(channel, str) and channel.strip().lower() in _STREAMING_NAMES
        ):
            keep.add(sid)
    return keep


def hide_non_streaming_tv(
    manager: MongoDBManager, keep_ids: Set[int], dry_run: bool = False
) -> Dict[str, int]:
    """
    Move every remaining `tv_series` document to the unsupported
    `broadcast_tv` bucket. Reversible (no documents are deleted).
    """
    keep_ids |= _existing_streaming_ids(manager)
    keep_list = sorted(keep_ids)

    if dry_run:
        remaining = manager.series.count_documents(
            {"content_type": "tv_series", "series_id": {"$nin": keep_list}}
        )
        return {"kept": len(keep_list), "hidden": remaining}

    hidden = manager.series.update_many(
        {"content_type": "tv_series", "series_id": {"$nin": keep_list}},
        {"$set": {"content_type": HIDDEN_CONTENT_TYPE, "catalog_scope": "broadcast_tv"}},
    )
    kept = manager.series.update_many(
        {"content_type": "tv_series", "series_id": {"$in": keep_list}},
        {"$set": {"catalog_scope": "web_series"}},
    )
    return {
        "kept": kept.matched_count,
        "hidden": hidden.modified_count,
    }


def run(
    max_pages: Optional[int] = None,
    workers: int = DEFAULT_WORKERS,
    page_sleep: float = DEFAULT_PAGE_SLEEP,
    dry_run: bool = False,
    hide: bool = True,
) -> Dict[str, Any]:
    client = TMDbClient()
    manager: Optional[MongoDBManager] = None
    try:
        genre_map: Dict[int, str] = {}
        try:
            for genre in client.fetch_tv_genres():
                genre_map[int(genre["id"])] = genre["name"]
        except Exception as exc:
            logger.warning("Could not load TMDb TV genres: %s", exc)

        rows = fetch_candidates(client, max_pages=max_pages, sleep_seconds=page_sleep)
        logger.info("Discover candidates: %d", len(rows))
        if not rows:
            return {"candidates": 0, "kept": 0, "upserted": 0, "hidden": 0}

        enriched = enrich_streaming_only(client, rows, workers=workers)
        docs = [
            normalize_web_series(row, details, genre_map=genre_map)
            for row, details in enriched
        ]
        docs = [doc for doc in docs if doc.get("series_id") is not None and doc.get("name")]
        keep_ids = {int(doc["series_id"]) for doc in docs}

        upserted = {"inserted": 0, "updated": 0}
        if not dry_run:
            manager = MongoDBManager()
            for doc in docs:
                outcome = manager.upsert_series(doc)
                upserted["inserted" if outcome == "inserted" else "updated"] += 1
        else:
            manager = MongoDBManager()

        hidden = 0
        if hide:
            hide_counts = hide_non_streaming_tv(manager, keep_ids, dry_run=dry_run)
            hidden = hide_counts["hidden"]

        result = {
            "candidates": len(rows),
            "kept": len(docs),
            "upserted": upserted,
            "hidden": hidden,
            "dry_run": dry_run,
        }
        logger.info("Web-series sweep complete: %s", result)
        return result
    finally:
        if manager is not None:
            manager.close()
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pages", type=int, default=0, help="Max discover pages (0 = all).")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="Parallel detail requests.")
    parser.add_argument("--sleep", type=float, default=DEFAULT_PAGE_SLEEP, help="Seconds between discover pages.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and count, but write nothing.")
    parser.add_argument("--no-hide", action="store_true", help="Do not move legacy TV to the hidden bucket.")
    args = parser.parse_args()

    result = run(
        max_pages=args.pages or None,
        workers=args.workers,
        page_sleep=args.sleep,
        dry_run=args.dry_run,
        hide=not args.no_hide,
    )
    print(result)


if __name__ == "__main__":
    main()
