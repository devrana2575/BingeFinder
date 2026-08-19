"""
database/update_mongo.py
==========================
Ingestion pipeline that fetches TVmaze's show catalog, enriches each show
with its cast, and upserts everything into MongoDB's `series` collection.

This module only orchestrates calls into the existing `TVmazeClient` and
`MongoDBManager` layers — no new fetching or storage logic is introduced
here.

This replaces database/update_database.py (TMDb + SQLite) as the active
ingestion pipeline. That module is left in place, unused, until this
migration is fully verified.

Run directly:
    python -m database.update_mongo

Or scheduled via cron / Task Scheduler / GitHub Actions for periodic syncs.
"""

import sys
from typing import Any, Dict, List, Optional

# Allow running this file directly (`python database/update_mongo.py`) as
# well as as a module (`python -m database.update_mongo`) by ensuring the
# project root is importable in both cases.
if __name__ == "__main__" and __package__ is None:
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from api.tvmaze import TVmazeAPIError, TVmazeClient, clean_summary
from config import TVMAZE_CAST_LIMIT, TVMAZE_SYNC_PAGES
from database.mongo_client import MongoDatabaseError, MongoDBManager
from utils.logger import get_logger

logger = get_logger(__name__)


def _map_tvmaze_show_to_document(show: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map a raw TVmaze show dictionary (from the catalog index or the
    single-show details endpoint — both use the same shape) to our
    MongoDB `series` document schema.

    Fields TVmaze doesn't provide for a given show are stored as None
    rather than invented (e.g. TVmaze has no "original name" concept at
    all, so that field is always None).

    Args:
        show: Raw TVmaze show dictionary.

    Returns:
        Dict matching the `series` document schema, minus "cast" (added
        separately, since it requires its own API call) and
        "last_synced_at" (added by `MongoDBManager.upsert_series`).
    """
    image = show.get("image") or {}
    externals = show.get("externals") or {}
    rating = show.get("rating") or {}

    return {
        "tvmaze_id": show.get("id"),
        "name": show.get("name"),
        # TVmaze has no separate "original name" / "original language
        # title" field — always None rather than guessed.
        "original_name": None,
        "language": show.get("language"),
        "genres": show.get("genres") or [],
        "status": show.get("status"),
        "premiered": show.get("premiered"),
        "ended": show.get("ended"),
        "runtime": show.get("runtime"),
        "average_runtime": show.get("averageRuntime"),
        "rating": rating.get("average"),
        "weight": show.get("weight"),
        "summary": clean_summary(show.get("summary")),
        "network": show.get("network"),
        "web_channel": show.get("webChannel"),
        "official_site": show.get("officialSite"),
        "image_medium": image.get("medium"),
        "image_original": image.get("original"),
        "imdb_id": externals.get("imdb"),
        "thetvdb_id": externals.get("thetvdb"),
        "updated": show.get("updated"),
    }


def _map_tvmaze_cast_to_document_field(cast_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Map a raw TVmaze cast list (from `/shows/{id}/cast`) to the compact
    shape stored in a series document's "cast" field.

    Args:
        cast_entries: Raw TVmaze cast dictionaries, each with "person"
            and "character" sub-objects.

    Returns:
        List of simplified cast dictionaries (person id/name, character
        name, and a headshot image URL where available).
    """
    cast_field: List[Dict[str, Any]] = []
    for entry in cast_entries:
        person = entry.get("person") or {}
        character = entry.get("character") or {}
        person_image = person.get("image") or {}
        cast_field.append(
            {
                "person_id": person.get("id"),
                "person_name": person.get("name"),
                "character_name": character.get("name"),
                "image_medium": person_image.get("medium"),
            }
        )
    return cast_field


def fetch_all_shows(client: TVmazeClient, pages: int) -> List[Dict[str, Any]]:
    """
    Fetch and merge `pages` pages of TVmaze's show index/catalog,
    deduplicated by TVmaze show ID (the catalog itself should not contain
    duplicates across pages, but this guards against any overlap).

    A single page's failure is logged and skipped rather than aborting
    the whole fetch, so one flaky page doesn't block the rest. Fetching
    stops early if a page comes back empty (TVmaze signals "no more
    pages" this way), so `pages` is a ceiling, not a guarantee.

    Args:
        client: An initialized `TVmazeClient`.
        pages: Number of catalog pages to fetch, starting at page 0.

    Returns:
        A deduplicated list of raw TVmaze show dictionaries.
    """
    seen_ids = set()
    all_shows: List[Dict[str, Any]] = []

    for page in range(pages):
        try:
            shows = client.fetch_shows_page(page=page)
        except TVmazeAPIError as exc:
            logger.warning("Skipping catalog page %d due to API error: %s", page, exc)
            continue

        if not shows:
            logger.info("Catalog page %d returned no shows; stopping pagination.", page)
            break

        logger.info("Fetched %d shows from catalog page %d.", len(shows), page)
        for show in shows:
            show_id = show.get("id")
            if show_id is None or show_id in seen_ids:
                continue
            seen_ids.add(show_id)
            all_shows.append(show)

    return all_shows


def fetch_and_upsert_show(
    show: Dict[str, Any],
    client: TVmazeClient,
    mongo_manager: MongoDBManager,
    fetch_cast: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Map + upsert a single raw TVmaze show dict (e.g. the top result of a
    title search) into MongoDB, reusing the exact same mapping and
    upsert logic as the bulk catalog sync in `run_update` — so an
    on-demand lookup can never create a differently-shaped document or a
    duplicate (upserts are still keyed by tvmaze_id).

    Args:
        show: Raw TVmaze show dictionary (from `/search/shows` or
            `/shows/{id}`).
        client: An initialized `TVmazeClient`, used for the one extra
            cast lookup.
        mongo_manager: An initialized `MongoDBManager`.
        fetch_cast: If False, skips the cast API call; "cast" is stored
            as None.

    Returns:
        The series document as stored in MongoDB (including `_id` and
        `last_synced_at`), or None if the show has no TVmaze id.

    Raises:
        TVmazeAPIError: If the cast lookup fails.
        MongoDatabaseError: If the upsert fails.
    """
    show_id = show.get("id")
    if show_id is None:
        return None

    document = _map_tvmaze_show_to_document(show)
    if fetch_cast:
        cast_entries = client.fetch_show_cast(show_id, top_n=TVMAZE_CAST_LIMIT)
        document["cast"] = _map_tvmaze_cast_to_document_field(cast_entries)
    else:
        document["cast"] = None

    mongo_manager.upsert_series(document)
    return mongo_manager.get_series_by_id(show_id)


def find_or_fetch_show(query: str, mongo_manager: MongoDBManager) -> Optional[Dict[str, Any]]:
    """
    On-demand single-title lookup for the UI's search flow, used only
    when a title isn't already in MongoDB:
      1. TVmaze title search for `query` (`/search/shows`).
      2. Take TVmaze's top-scoring match (results already come back
         ranked by relevance).
      3. Fetch its cast and upsert it via `fetch_and_upsert_show` (the
         same mapping/upsert path the bulk sync uses).

    Args:
        query: Free-text title to search TVmaze for.
        mongo_manager: An initialized `MongoDBManager`.

    Returns:
        The newly stored series document, or None if TVmaze has no
        matching show or the search/cast request failed.
    """
    try:
        with TVmazeClient() as client:
            results = client.search_shows(query)
            if not results:
                return None
            top_show = (results[0] or {}).get("show")
            if not top_show:
                return None
            return fetch_and_upsert_show(top_show, client, mongo_manager)
    except TVmazeAPIError as exc:
        logger.warning("TVmaze search failed for %r: %s", query, exc)
        return None


def run_update(
    pages: Optional[int] = None,
    max_shows: Optional[int] = None,
    fetch_cast: bool = True,
) -> Dict[str, int]:
    """
    Orchestrate a full TVmaze -> MongoDB sync:
      1. Fetch `pages` pages of TVmaze's show catalog (each entry already
         contains nearly every field our schema needs).
      2. Optionally cap the run to the first `max_shows` discovered shows
         (for small, safe test runs — this pipeline never runs a massive
         import unless explicitly asked to via `pages`/`max_shows`).
      3. For each show, optionally enrich it with its cast: exactly one
         extra, targeted API call per show. Show details are NOT
         re-fetched, since the catalog page already has them — avoiding
         redundant TMDb-style detail calls.
      4. Upsert every show into MongoDB's `series` collection, keyed by
         tvmaze_id (never inserted as a duplicate), printing progress as
         it goes.
      5. Print final statistics.

    A failure processing any single show (TVmaze request or database
    write) is caught, logged, and counted — it never stops the rest of
    the sync. MongoDB data is never deleted or rebuilt; documents are
    upserted in place.

    Args:
        pages: Number of catalog pages to fetch, starting at page 0.
            Defaults to `TVMAZE_SYNC_PAGES` from config if not provided
            (kept small by default — see config.py).
        max_shows: If given, only the first `max_shows` discovered shows
            are enriched/upserted. Useful for small, safe test runs.
        fetch_cast: If False, skips the per-show cast API call entirely;
            "cast" is stored as None rather than fetched.

    Returns:
        Dict with "fetched", "inserted", "updated", "failed", and
        "total_in_db" counts.
    """
    stats = {"fetched": 0, "inserted": 0, "updated": 0, "failed": 0, "total_in_db": 0}

    if pages is None:
        pages = TVMAZE_SYNC_PAGES

    try:
        mongo_manager = MongoDBManager()
    except MongoDatabaseError as exc:
        logger.error("Aborting update: could not initialize MongoDB: %s", exc)
        return stats

    try:
        try:
            with TVmazeClient() as client:
                shows = fetch_all_shows(client, pages=pages)
                if max_shows is not None:
                    shows = shows[:max_shows]
                stats["fetched"] = len(shows)

                if not shows:
                    logger.warning("No shows fetched from TVmaze; nothing to upsert.")
                else:
                    total = len(shows)
                    for index, show in enumerate(shows, start=1):
                        show_id = show.get("id")
                        show_name = show.get("name", "<unknown>")
                        if show_id is None:
                            stats["failed"] += 1
                            logger.warning("Skipping a catalog entry with no TVmaze id.")
                            continue

                        try:
                            document = _map_tvmaze_show_to_document(show)

                            # Cast requires its own call — the only extra
                            # request made per show, and only once.
                            if fetch_cast:
                                cast_entries = client.fetch_show_cast(show_id, top_n=TVMAZE_CAST_LIMIT)
                                document["cast"] = _map_tvmaze_cast_to_document_field(cast_entries)
                            else:
                                document["cast"] = None

                            outcome = mongo_manager.upsert_series(document)
                            stats[outcome] += 1
                            print(f"[{index}/{total}] {outcome}: {show_name} (tvmaze_id={show_id})")
                        except (TVmazeAPIError, MongoDatabaseError) as exc:
                            stats["failed"] += 1
                            logger.warning("Failed to process show %s (%s): %s", show_id, show_name, exc)
                        except Exception as exc:  # defensive: one bad show must never kill the run
                            stats["failed"] += 1
                            logger.error(
                                "Unexpected error processing show %s (%s): %s", show_id, show_name, exc
                            )
        except TVmazeAPIError as exc:
            logger.error("Aborting update: could not fetch the TVmaze catalog: %s", exc)
        except Exception as exc:
            logger.error("Aborting update: unexpected error during sync: %s", exc)

        try:
            stats["total_in_db"] = mongo_manager.get_series_count()
        except MongoDatabaseError as exc:
            logger.error("Could not fetch final series count: %s", exc)
    finally:
        mongo_manager.close()

    _print_summary(stats)
    return stats


def _print_summary(stats: Dict[str, int]) -> None:
    """Print the final sync summary in the required format."""
    print("Fetched:", stats["fetched"])
    print("Inserted:", stats["inserted"])
    print("Updated:", stats["updated"])
    print("Failed:", stats["failed"])
    print("Total series in MongoDB:", stats["total_in_db"])


if __name__ == "__main__":
    run_update()
