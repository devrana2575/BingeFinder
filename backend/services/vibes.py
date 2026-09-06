"""
backend/services/vibes.py
===========================
"WHAT'S YOUR VIBE?" mood picker + "SURPRISE ME" taste-aware pick.

Pure, in-memory helpers over a catalog of series documents. A mood is a
curated set of genre strings. "Surprise Me" is a taste-aware, weighted
pick over the (optionally vibe-filtered) catalog: it favours titles that
match the user's saved preferences and recent engagement signals, mixes
in a small amount of randomness so "Try Another" stays varied, and always
returns a real document — never a hardcoded/fake title.
"""

from __future__ import annotations

import random
from typing import Any, Callable, Dict, List, Optional, Tuple

# Keep at least this many candidates after filtering out titles the user
# has already engaged with, so a fresh pick is still possible.
MIN_SURPRISE_POOL = 6

VIBES: Dict[str, Dict[str, Any]] = {
    "hype": {
        "label": "Can't stop watching",
        "genres": {"Action", "Adventure", "Crime", "Thriller", "Sports"},
    },
    "think": {
        "label": "Make me think",
        "genres": {"Science-Fiction", "Mystery", "History", "Legal", "Espionage", "Anthology"},
    },
    "dark": {
        "label": "Dark & disturbing",
        "genres": {"Horror", "Thriller", "Crime", "Supernatural", "War"},
    },
    "chill": {
        "label": "Just chill",
        "genres": {"Comedy", "Family", "Food", "Music", "Travel", "Children"},
    },
    "feels": {
        "label": "Need feelings",
        "genres": {"Romance", "Drama", "Family"},
    },
    "mindblown": {
        "label": "Mind = blown",
        "genres": {"Science-Fiction", "Fantasy", "Mystery", "Supernatural"},
    },
}

SURPRISE_KEY = "surprise"
SURPRISE_VIBE: Dict[str, str] = {"label": "Surprise me"}


def vibe_options() -> List[Tuple[str, Dict[str, Any]]]:
    """Ordered (key, vibe) pairs for the selector — moods first, Surprise Me last."""
    return list(VIBES.items()) + [(SURPRISE_KEY, SURPRISE_VIBE)]


def filter_by_vibe(docs: List[Dict[str, Any]], vibe_key: str, limit: int = 12) -> List[Dict[str, Any]]:
    """
    Series from the already-loaded catalog whose existing `genres` list
    overlaps this vibe's genre set, best-rated first.

    Falls back to the catalog's own top-rated titles if nothing in the
    current catalog happens to match this vibe's genres yet.
    """
    vibe = VIBES.get(vibe_key)
    if vibe is None:
        return []

    wanted = vibe["genres"]
    matches = [d for d in docs if wanted.intersection(d.get("genres") or [])]
    pool = matches if matches else docs

    def sort_key(d: Dict[str, Any]):
        rating = d.get("rating") if isinstance(d.get("rating"), (int, float)) else -1
        weight = d.get("weight") if isinstance(d.get("weight"), (int, float)) else -1
        return (rating, weight)

    return sorted(pool, key=sort_key, reverse=True)[:limit]


def _surprise_score(doc: Dict[str, Any], signals: Dict[str, Any]) -> float:
    """
    Transparent, data-grounded surprise score in [0, 1).

    Every component is derived from real fields on the doc and the user's
    saved signals — nothing is invented. This is a preference-matching
    weight used to ORDER a surprise pick, not a probability and not a
    "you'll like this X%" guarantee.
    """
    score = 0.0

    rating = doc.get("rating")
    if isinstance(rating, (int, float)):
        # Quality signal: 0.25 at most, so it never overwhelms taste.
        score += 0.25 * min(max(rating, 0.0), 10.0) / 10.0

    weight = doc.get("weight")
    if isinstance(weight, (int, float)):
        # Popularity signal (capped): 0.15 at most.
        score += 0.15 * min(max(weight, 0.0), 500.0) / 500.0

    preferences = signals.get("preferences") or {}
    pref_genres = {str(g).lower() for g in (preferences.get("genres") or [])}
    if pref_genres:
        doc_genres = [str(g) for g in (doc.get("genres") or [])]
        if any(g.lower() in pref_genres for g in doc_genres):
            score += 0.30  # Strongest taste signal available.

    pref_languages = {str(l).lower() for l in (preferences.get("languages") or [])}
    doc_language = str(doc.get("language") or "").lower()
    if pref_languages and doc_language in pref_languages:
        score += 0.10

    return min(score, 0.99)


def _surprise_reasons(doc: Dict[str, Any], signals: Dict[str, Any]) -> List[str]:
    """
    Grounded, human-readable reasons for a surprise pick. Each reason is
    only emitted when the underlying data actually supports it. An empty
    list means "no strong preferences to justify" — the UI then simply
    omits the explanation rather than inventing one.
    """
    reasons: List[str] = []

    preferences = signals.get("preferences") or {}
    pref_genres = {str(g).lower() for g in (preferences.get("genres") or [])}
    if pref_genres:
        doc_genres = [str(g) for g in (doc.get("genres") or [])]
        overlap = [g for g in doc_genres if g.lower() in pref_genres]
        if overlap:
            reasons.append(f"Matches your interest in {overlap[0]}")

    pref_languages = {str(l).lower() for l in (preferences.get("languages") or [])}
    doc_language = str(doc.get("language") or "").lower()
    if pref_languages and doc_language in pref_languages:
        reasons.append("In your preferred language")

    rating = doc.get("rating")
    if isinstance(rating, (int, float)) and rating >= 8.0:
        reasons.append("Great reviews")

    weight = doc.get("weight")
    if isinstance(weight, (int, float)) and weight >= 400:
        reasons.append("Popular right now")

    return reasons


def pick_surprise(
    docs: List[Dict[str, Any]],
    vibe_key: Optional[str] = None,
    user_signals: Optional[Dict[str, Any]] = None,
    rng: Optional[random.Random] = None,
) -> Optional[Dict[str, Any]]:
    """
    Surprise Me: pick one real series document using a weighted sample.

    Strategy:
        1. If a mood vibe is active, shuffle within that vibe's matches
           when any exist (so the surprise still fits the mood).
        2. Prefer titles the user has NOT already liked / watchlisted /
           viewed, unless that would leave the pool smaller than
           MIN_SURPRISE_POOL (taste first: never force a title the user
           already engaged with when better options remain).
        3. Weighted sample by `_surprise_score`, which rewards preference
           matches and, for guests without preferences, quality/popularity
           so the pick is still a good one rather than a uniform random.
           A little jitter keeps "Try Another" varied without discarding
           the taste signal.

    The chosen document has a `_surprise_reasons` key attached with
    grounded reasons (may be empty). Returns None only if there is
    nothing pickable (e.g. empty catalog).
    """
    rng = rng or random

    pool = docs
    if vibe_key and vibe_key in VIBES:
        vibe_matches = filter_by_vibe(docs, vibe_key, limit=max(len(docs), 1))
        if vibe_matches:
            pool = vibe_matches

    candidates = [d for d in pool if d.get("series_id") is not None]
    if not candidates:
        return None

    signals = user_signals or {}
    seen = set(signals.get("seen_ids") or [])
    if seen:
        keeps_min = len(candidates) - len(seen.intersection(d.get("series_id") for d in candidates))
        if keeps_min >= min(MIN_SURPRISE_POOL, len(candidates)):
            candidates = [d for d in candidates if d.get("series_id") not in seen]

    scored = [(d, _surprise_score(d, signals)) for d in candidates]
    # Weight floor keeps every candidate reachable (so "Try Another" can
    # still surprise), while the score keeps preference-aware picking.
    weights = [max(0.1, s) for _, s in scored]
    pick = rng.choices([d for d, _ in scored], weights=weights, k=1)[0]

    pick = dict(pick)
    pick["_surprise_reasons"] = _surprise_reasons(pick, signals)
    return pick
