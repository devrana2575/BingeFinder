"""
backend/services/explain.py
=============================
"WHY THIS?" — turns a recommendation record into a short list of plain
reasons the title was suggested.

Explanations are concise and metadata-driven: only reasons supported by
actual data are shown.  No generic fallbacks, no invented explanations.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_why_reasons(source_doc: Optional[Dict[str, Any]], rec: Dict[str, Any]) -> List[str]:
    """
    Concise, metadata-backed reasons for one recommendation.

    Only reasons that are directly supported by the actual matching features
    (genre overlap, content similarity, network, rating) are generated. No
    generic or invented fallbacks.

    Args:
        source_doc: The MongoDB document of the series the user picked.
        rec: A recommendation dict from get_recommendations().

    Returns:
        A list of 1-3 short reason strings.
    """
    reasons: List[str] = []
    source = source_doc or {}

    source_title = (source.get("name") or "").strip()

    # 1. Genre overlap — share actual measurable overlap.
    source_genres = set(source.get("genres") or [])
    rec_genres = [g for g in (rec.get("genres") or []) if g]
    shared = [g for g in rec_genres if g in source_genres]
    if shared:
        if source_title:
            reasons.append(f"Shares {len(shared)} genre{'s' if len(shared) != 1 else ''} with {source_title}")
        else:
            reasons.append(f"Shares genres: {', '.join(shared[:3])}")

    # 2. Content similarity — driven by the actual semantic/TF-IDF signals.
    components = rec.get("component_scores", {})
    sem = components.get("semantic")
    tfidf = components.get("tfidf")
    if isinstance(sem, (int, float)) and sem > 0.6:
        reasons.append("Similar story themes and tone")
    elif isinstance(tfidf, (int, float)) and isinstance(sem, (int, float)) \
            and tfidf > 0.3 and sem > 0.45:
        reasons.append("Shares content and themes")

    # 3. Network match — same network/web_channel is a definite link.
    source_channels = set()
    for field in ("network", "web_channel"):
        obj = source.get(field)
        if isinstance(obj, dict) and obj.get("name"):
            source_channels.add(obj["name"])
    if isinstance(tfidf, (int, float)) and tfidf > 0.3 and source_channels:
        reasons.append(f"From {', '.join(sorted(source_channels)[:1])} — a network you know")

    # 4. Quality signal — from the actual rating on the record.
    rating = rec.get("rating")
    if isinstance(rating, (int, float)) and rating >= 8.0:
        reasons.append(f"Highly rated: {rating:.1f}/10")

    return reasons


def build_why_map(
    source_doc: Optional[Dict[str, Any]], recs: List[Dict[str, Any]]
) -> Dict[int, List[str]]:
    """{series_id: [reason, ...]} for every recommendation."""
    return {
        r["series_id"]: build_why_reasons(source_doc, r)
        for r in recs
        if r.get("series_id") is not None
    }
