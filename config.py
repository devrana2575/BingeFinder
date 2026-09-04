"""
config.py
==========
Centralized configuration module for the BingeFinder application.

Responsibilities:
    - Load environment variables from a local .env file (never committed to VCS).
    - Expose strongly-typed configuration constants to the rest of the application.
    - Fail fast (with a clear error) if mandatory secrets are missing.

Never hardcode secrets in this file. All sensitive values must come from
environment variables (see .env.example for the required keys).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Load environment variables from a .env file located at the project root.
# If no .env file exists, this is a no-op and real environment variables
# (e.g. set by the OS, Docker, or a CI/CD pipeline) are used instead.
# ---------------------------------------------------------------------------
PROJECT_ROOT: Path = Path(__file__).resolve().parent
ENV_FILE_PATH: Path = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_FILE_PATH)


class ConfigError(Exception):
    """Raised when a required configuration value is missing or invalid."""


def _get_required_env(key: str) -> str:
    """
    Fetch a required environment variable.

    Args:
        key: Name of the environment variable.

    Returns:
        The value of the environment variable.

    Raises:
        ConfigError: If the environment variable is not set or empty.
    """
    value = os.getenv(key)
    if not value:
        raise ConfigError(
            f"Missing required environment variable '{key}'. "
            f"Please set it in your .env file (see .env.example)."
        )
    return value


def _get_optional_env(key: str, default: str) -> str:
    """
    Fetch an optional environment variable, falling back to a default value.

    Args:
        key: Name of the environment variable.
        default: Default value to use if the variable is not set.

    Returns:
        The value of the environment variable, or the default.
    """
    return os.getenv(key, default)


# ---------------------------------------------------------------------------
# TMDb API configuration
# ---------------------------------------------------------------------------
# NOTE: TMDB_API_KEY is intentionally NOT loaded at import time so that
# unrelated modules (e.g. database utilities) can be imported/tested without
# requiring the key to be present. Call get_tmdb_api_key() when it is needed.
TMDB_BASE_URL: str = _get_optional_env("TMDB_BASE_URL", "https://api.themoviedb.org/3")
TMDB_IMAGE_BASE_URL: str = _get_optional_env(
    "TMDB_IMAGE_BASE_URL", "https://image.tmdb.org/t/p/w500"
)


def get_tmdb_api_key() -> str:
    """
    Retrieve the TMDb API key from the environment.

    Returns:
        The TMDb API key as a string.

    Raises:
        ConfigError: If TMDB_API_KEY is not set.
    """
    return _get_required_env("TMDB_API_KEY")


# ---------------------------------------------------------------------------
# Networking / retry configuration
# ---------------------------------------------------------------------------
REQUEST_TIMEOUT_SECONDS: float = float(_get_optional_env("REQUEST_TIMEOUT_SECONDS", "10"))
MAX_RETRIES: int = int(_get_optional_env("MAX_RETRIES", "3"))
BACKOFF_FACTOR: float = float(_get_optional_env("BACKOFF_FACTOR", "0.5"))

# ---------------------------------------------------------------------------
# MongoDB configuration
# ---------------------------------------------------------------------------
# NOTE: mirrors get_tmdb_api_key() below — not loaded at import time, so
# unrelated modules can still be imported/tested without MongoDB running.
def get_mongodb_uri() -> str:
    """
    Retrieve the MongoDB connection URI from the environment.

    Returns:
        The MongoDB URI as a string (e.g. "mongodb://127.0.0.1:27017/").

    Raises:
        ConfigError: If MONGODB_URI is not set.
    """
    return _get_required_env("MONGODB_URI")


def get_mongodb_database() -> str:
    """
    Retrieve the MongoDB database name from the environment.

    Returns:
        The MongoDB database name as a string.

    Raises:
        ConfigError: If MONGODB_DATABASE is not set.
    """
    return _get_required_env("MONGODB_DATABASE")


# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
LOG_LEVEL: str = _get_optional_env("LOG_LEVEL", "INFO")

# ---------------------------------------------------------------------------
# Authentication configuration
# ---------------------------------------------------------------------------
import secrets as _secrets


def get_jwt_secret() -> str:
    """
    Retrieve the secret key used for session tokens.

    Returns:
        The JWT secret as a string. If JWT_SECRET is not set, a random
        secret is generated (suitable for development only — set a
        stable secret in production to avoid invalidating sessions on
        restart).
    """
    value = os.getenv("JWT_SECRET")
    if value:
        return value
    # Dev fallback: random per process (sessions won't survive restart)
    return _secrets.token_hex(32)


def get_bcrypt_rounds() -> int:
    """
    Retrieve the bcrypt hashing rounds.

    Returns:
        The number of rounds (default 12).
    """
    raw = os.getenv("BCRYPT_ROUNDS", "12")
    try:
        rounds = int(raw)
        return max(4, min(rounds, 31))  # clamp to valid range
    except (ValueError, TypeError):
        return 12


# ---------------------------------------------------------------------------
# Recommendation engine configuration
# ---------------------------------------------------------------------------
EMBEDDING_MODEL_NAME: str = _get_optional_env("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
REBUILD_MODEL_TTL_HOURS: int = int(_get_optional_env("REBUILD_MODEL_TTL_HOURS", "24"))
