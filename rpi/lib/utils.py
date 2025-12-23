"""Shared utility functions."""
from datetime import UTC, datetime


def utcnow() -> datetime:
    """Return current UTC time as a naive datetime."""
    return datetime.now(UTC).replace(tzinfo=None)
