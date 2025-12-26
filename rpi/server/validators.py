"""Shared query parameter parsing utilities."""

from datetime import UTC, datetime, timedelta
from typing import Any

MIN_HOURS = 1
MAX_HOURS = 24
DEFAULT_HOURS = 3


class InvalidParameter(Exception):
    """Raised when a query parameter is invalid."""


def parse_hours(params: Any, *, strict: bool = True) -> tuple[int, datetime]:
    """Parse and validate hours query parameter.

    Args:
        params: Object with .get() method (Request.query_params or similar)
        strict: If True, raise InvalidParameter on invalid input.
                If False, return defaults for invalid input.

    Returns:
        Tuple of (hours, from_time) where from_time is now minus hours.

    Raises:
        InvalidParameter: If strict=True and parameter is invalid.
    """
    try:
        hours = int(params.get("hours", DEFAULT_HOURS))
    except (ValueError, TypeError):
        if strict:
            raise InvalidParameter(
                "Parameter needs to be an integer"
            ) from None
        hours = DEFAULT_HOURS

    if not (MIN_HOURS <= hours <= MAX_HOURS):
        if strict:
            raise InvalidParameter(
                f"Hours must be between {MIN_HOURS} and {MAX_HOURS}"
            )
        hours = max(MIN_HOURS, min(MAX_HOURS, hours))

    return hours, datetime.now(UTC) - timedelta(hours=hours)
