"""Shared validation utilities."""

from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field, ValidationError

MIN_HOURS = 1
MAX_HOURS = 24
DEFAULT_HOURS = 3


class HoursQuery(BaseModel):
    """Validated hours query parameter."""

    hours: int = Field(default=DEFAULT_HOURS, ge=MIN_HOURS, le=MAX_HOURS)

    @property
    def from_time(self) -> datetime:
        """Get the datetime for hours ago from now."""
        return datetime.now(UTC) - timedelta(hours=self.hours)


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
    raw_hours = params.get("hours", DEFAULT_HOURS)

    # Handle None explicitly as invalid
    if raw_hours is None:
        if strict:
            raise InvalidParameter("Parameter needs to be an integer")
        return DEFAULT_HOURS, datetime.now(UTC) - timedelta(hours=DEFAULT_HOURS)

    # Try to parse as integer
    try:
        hours_int = int(raw_hours)
    except (ValueError, TypeError):
        if strict:
            raise InvalidParameter("Parameter needs to be an integer") from None
        return DEFAULT_HOURS, datetime.now(UTC) - timedelta(hours=DEFAULT_HOURS)

    # Validate with Pydantic
    try:
        query = HoursQuery(hours=hours_int)
        return query.hours, query.from_time
    except ValidationError:
        if strict:
            raise InvalidParameter(
                f"Hours must be between {MIN_HOURS} and {MAX_HOURS}"
            ) from None
        clamped = max(MIN_HOURS, min(MAX_HOURS, hours_int))
        return clamped, datetime.now(UTC) - timedelta(hours=clamped)
