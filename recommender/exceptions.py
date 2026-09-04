"""
recommender/exceptions.py
===========================
Custom exceptions for the recommendation engine, so callers can catch
recommender-specific failures separately from generic errors (mirrors
the ConfigError / MongoDatabaseError pattern already used elsewhere in
this project).
"""


class RecommenderError(Exception):
    """Base class for all recommender-related errors."""


class ModelNotBuiltError(RecommenderError):
    """
    Raised when get_recommendations() (or anything else that needs the
    saved model) is called before a model has ever been built, or the
    saved artifact file is missing/corrupted.
    """


class InsufficientDataError(RecommenderError):
    """
    Raised when build_recommendation_model() is asked to build a model
    from too few usable series (fewer than 2 series with any text
    content) to compute meaningful similarities.
    """


class SeriesNotFoundError(RecommenderError):
    """
    Raised by get_recommendations() when the given series_id does not
    exist in the currently loaded model (e.g. an invalid/unknown
    series_id).
    """
