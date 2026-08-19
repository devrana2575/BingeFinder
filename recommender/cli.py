"""
recommender/cli.py
=====================
Tiny command-line demo for the recommendation engine. Not a test suite
(see tests/test_recommender.py for that) — just a manual, human-readable
way to build the model and try it out.

Usage:
    python -m recommender.cli build
    python -m recommender.cli recommend <tvmaze_id> [--top_n 10]
"""

import argparse
import sys
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from recommender.build_model import build_recommendation_model
from recommender.exceptions import InsufficientDataError, ModelNotBuiltError, SeriesNotFoundError
from recommender.recommend import get_recommendations
from database.mongo_client import MongoDatabaseError


def _cmd_build(_args: argparse.Namespace) -> None:
    try:
        stats = build_recommendation_model()
    except (MongoDatabaseError, InsufficientDataError) as exc:
        print(f"Build failed: {exc}")
        sys.exit(1)

    print("Model built successfully.")
    print(f"  Total series in MongoDB : {stats['total_in_db']}")
    print(f"  Series used in model    : {stats['used']}")
    print(f"  Series skipped          : {stats['skipped']}")
    print(f"  TF-IDF vocabulary size  : {stats['vocabulary_size']}")
    print(f"  Saved to                : {stats['model_path']}")


def _cmd_recommend(args: argparse.Namespace) -> None:
    try:
        results = get_recommendations(args.series_id, top_n=args.top_n)
    except ModelNotBuiltError as exc:
        print(f"{exc}")
        sys.exit(1)
    except SeriesNotFoundError as exc:
        print(f"{exc}")
        sys.exit(1)

    if not results:
        print(f"No recommendations found for series_id={args.series_id}.")
        return

    print(f"Top {len(results)} recommendations for series_id={args.series_id}:\n")
    for rank, rec in enumerate(results, start=1):
        genres = ", ".join(rec["genres"]) if rec["genres"] else "N/A"
        rating = rec["rating"] if rec["rating"] is not None else "N/A"
        print(
            f"{rank:>2}. {rec['title'] or '(untitled)'}  "
            f"[id={rec['series_id']}]  "
            f"Similarity Score={rec['similarity_score']}  "
            f"Rating={rating}  Genres={genres}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="BingeFinder recommendation engine CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("build", help="Build (or rebuild) the recommendation model from MongoDB.")

    recommend_parser = subparsers.add_parser("recommend", help="Get recommendations for a series.")
    recommend_parser.add_argument("series_id", type=int, help="tvmaze_id of the series to base recommendations on.")
    recommend_parser.add_argument("--top_n", type=int, default=10, help="Number of recommendations to return.")

    args = parser.parse_args()
    if args.command == "build":
        _cmd_build(args)
    elif args.command == "recommend":
        _cmd_recommend(args)


if __name__ == "__main__":
    main()
