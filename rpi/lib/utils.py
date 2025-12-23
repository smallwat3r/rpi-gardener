"""Shared utility functions."""
import sqlite3
from datetime import UTC, datetime, timedelta

# SQLite datetime format (space separator, not T)
_SQLITE_DATETIME_FMT = "%Y-%m-%d %H:%M:%S"


def _adapt_datetime(dt: datetime) -> str:
    """Adapt datetime to SQLite string format."""
    return dt.strftime(_SQLITE_DATETIME_FMT)


# Register adapter at module import time - this ensures it's registered
# before any database operations occur. Python 3.12+ removed the default
# datetime adapters, so we must register explicitly.
sqlite3.register_adapter(datetime, _adapt_datetime)


def utcnow() -> datetime:
    """Return current UTC time as a naive datetime."""
    return datetime.now(UTC).replace(tzinfo=None)
