"""Shared utility functions."""
from datetime import UTC, datetime


def utcnow() -> datetime:
    """Return current UTC time as a naive datetime.

    Uses datetime.now(UTC) internally for correctness, but returns a naive
    datetime for SQLite compatibility (which stores timestamps without timezone).
    """
    return datetime.now(UTC).replace(tzinfo=None)
