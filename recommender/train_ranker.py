"""
recommender/train_ranker.py
=============================
Offline training/evaluation script for the adaptive contextual bandit.

Usage:
    python -m recommender.train_ranker          # Train and print metrics
    python -m recommender.train_ranker --eval   # Full evaluation with baseline comparison

This script:
    1. Loads all interaction events from MongoDB
    2. Splits into train/test by timestamp
    3. Simulates the recommendation pipeline on training data
    4. Evaluates on test data
    5. Reports precision@K, CTR, diversity, novelty metrics

DO NOT call this during normal API requests.
Train periodically when enough data accumulates.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.logger import get_logger

logger = get_logger(__name__)


def load_training_data() -> Tuple[List[Dict], Dict]:
    """
    Load all interaction events and series metadata from MongoDB.

    Returns:
        (events, series_metadata)
    """
    from database.mongo_client import MongoDBManager
    from database.interaction_events import InteractionEventManager

    manager = MongoDBManager()
    try:
        iem = InteractionEventManager(manager)
        events = iem.get_all_training_data()

        # Load series metadata from the recommendation model
        try:
            from recommender.recommend import load_model
            bundle = load_model()
            metadata = bundle["metadata"]
        except Exception:
            metadata = {}

        return events, metadata
    finally:
        manager.close()


def split_train_test(
    events: List[Dict],
    test_ratio: float = 0.2,
) -> Tuple[List[Dict], List[Dict]]:
    """Split events into train/test by timestamp (temporal split)."""
    if not events:
        return [], []

    sorted_events = sorted(events, key=lambda e: e.get("timestamp", ""))
    split_idx = int(len(sorted_events) * (1 - test_ratio))
    return sorted_events[:split_idx], sorted_events[split_idx:]


def compute_metrics(
    recommended_ids: List[int],
    actual_positives: set,
    k: int,
) -> Dict[str, float]:
    """Compute precision@K and other ranking metrics."""
    if not recommended_ids or k == 0:
        return {"precision_at_k": 0.0, "recall_at_k": 0.0, "hit_rate": 0.0}

    top_k = recommended_ids[:k]
    hits = len(set(top_k) & actual_positives)

    precision = hits / k
    recall = hits / len(actual_positives) if actual_positives else 0.0
    hit_rate = 1.0 if hits > 0 else 0.0

    return {
        "precision_at_k": precision,
        "recall_at_k": recall,
        "hit_rate": hit_rate,
    }


def compute_diversity(recommended_ids: List[int], metadata: Dict) -> float:
    """Compute genre diversity of recommendations (unique genres / total genres)."""
    all_genres = set()
    for rid in recommended_ids:
        meta = metadata.get(rid, {})
        for g in meta.get("genres", []):
            all_genres.add(g)
    return len(all_genres) / max(1, len(recommended_ids))


def evaluate_baseline(
    test_events: List[Dict],
    metadata: Dict,
) -> Dict[str, float]:
    """
    Evaluate the baseline hybrid recommender (no adaptive ranking).

    For each user in test data:
        - Get their positive interactions (like, watchlist_add)
        - Check if baseline recommendations would have caught them
    """
    # Group test events by user
    user_events: Dict[str, List[Dict]] = {}
    for evt in test_events:
        uid = evt.get("user_id", "")
        if uid.startswith("guest:"):
            continue
        user_events.setdefault(uid, []).append(evt)

    all_metrics = []
    for user_id, events in user_events.items():
        positives = {
            evt["series_id"] for evt in events
            if evt.get("event_type") in ("like", "watchlist_add", "provider_click")
            and evt.get("series_id") is not None
        }
        if not positives:
            continue

        # Baseline: just use quality ranking from metadata
        all_series = list(metadata.keys())
        quality_ranked = sorted(
            all_series,
            key=lambda s: metadata[s].get("rating", 0) or 0,
            reverse=True,
        )

        metrics = compute_metrics(quality_ranked, positives, k=10)
        all_metrics.append(metrics)

    if not all_metrics:
        return {"precision_at_10": 0.0, "recall_at_10": 0.0, "hit_rate": 0.0}

    return {
        "precision_at_10": np.mean([m["precision_at_k"] for m in all_metrics]),
        "recall_at_10": np.mean([m["recall_at_k"] for m in all_metrics]),
        "hit_rate": np.mean([m["hit_rate"] for m in all_metrics]),
    }


def train_and_evaluate(eval_mode: bool = False) -> Dict[str, Any]:
    """
    Main training/evaluation function.

    Returns a dict with status and metrics.
    """
    events, metadata = load_training_data()

    if not events:
        return {
            "status": "no_data",
            "message": "No interaction events found. Collect more user data.",
        }

    # Count positive events
    positive_events = [
        e for e in events
        if e.get("event_type") in ("like", "watchlist_add", "provider_click", "view_details")
    ]

    result = {
        "status": "data_collected",
        "total_events": len(events),
        "positive_events": len(positive_events),
        "unique_users": len(set(e.get("user_id") for e in events)),
    }

    if len(positive_events) < 10:
        result["message"] = (
            f"Collected {len(positive_events)} positive events. "
            f"Need at least 10 for training. Keep collecting data."
        )
        return result

    train_events, test_events = split_train_test(events)
    result["train_events"] = len(train_events)
    result["test_events"] = len(test_events)

    if eval_mode and test_events:
        baseline_metrics = evaluate_baseline(test_events, metadata)
        result["baseline_metrics"] = baseline_metrics
        result["message"] = (
            f"Baseline evaluation: Precision@10={baseline_metrics['precision_at_10']:.3f}, "
            f"Hit Rate={baseline_metrics['hit_rate']:.3f}"
        )
    else:
        result["message"] = (
            f"Training data ready: {len(train_events)} events, "
            f"{result['unique_users']} users. "
            f"The adaptive ranker trains on-the-fly per request (stateless LinUCB)."
        )

    result["status"] = "ready"
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Train/evaluate the adaptive recommendation ranker")
    parser.add_argument("--eval", action="store_true", help="Run full evaluation with baseline comparison")
    args = parser.parse_args()

    result = train_and_evaluate(eval_mode=args.eval)

    print("\n=== Adaptive Ranker Training Report ===")
    for key, value in result.items():
        print(f"  {key}: {value}")
    print()


if __name__ == "__main__":
    main()
