"""Shared utility functions."""
import sqlite3
from datetime import UTC, datetime

# SQLite datetime format (space separator, not T)
_SQLITE_DATETIME_FMT = "%Y-%m-%d %H:%M:%S"


def utcnow() -> datetime:
    """Return current UTC time as a naive datetime.

    Uses datetime.now(UTC) internally for correctness, but returns a naive
    datetime for SQLite compatibility (which stores timestamps without timezone).
    """
    return datetime.now(UTC).replace(tzinfo=None)


def _adapt_datetime(dt: datetime) -> str:
    """Adapt datetime to SQLite string format."""
    return dt.strftime(_SQLITE_DATETIME_FMT)


def register_sqlite_adapters() -> None:
    """Register sqlite3 adapters for datetime handling.

    Python 3.12+ removed the default datetime adapters, so we need to
    register them explicitly. Call this once at application startup.
    """
    sqlite3.register_adapter(datetime, _adapt_datetime)
