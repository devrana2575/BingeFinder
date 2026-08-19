"""
logger.py
=========
Centralized logging utility for BingeFinder.

Provides a single `get_logger()` factory so every module logs in a
consistent format instead of each module configuring logging on its own
(avoids duplicate handlers and inconsistent formatting).
"""

import logging
import sys

from config import LOG_LEVEL

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str) -> logging.Logger:
    """
    Create (or retrieve) a configured logger instance.

    Args:
        name: Usually `__name__` of the calling module.

    Returns:
        A configured `logging.Logger` instance that writes to stdout.
    """
    logger = logging.getLogger(name)

    # Guard against adding duplicate handlers if get_logger() is called
    # multiple times for the same module (e.g. during test re-imports).
    if not logger.handlers:
        handler = logging.StreamHandler(stream=sys.stdout)
        formatter = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(LOG_LEVEL.upper())
        logger.propagate = False

    return logger
