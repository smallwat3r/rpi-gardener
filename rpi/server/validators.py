"""Shared validation utilities."""

from collections.abc import Collection
from datetime import UTC, datetime, timedelta
from typing import Any

MIN_HOURS = 1
MAX_HOURS = 24
DEFAULT_HOURS = 3


class InvalidParameter(Exception):
    """Raised when a query parameter is invalid."""


def validate_int_range(
    val: Any, name: str, min_v: int, max_v: int
) -> str | None:
    """Validate an integer is within range. Returns error message or None."""
    if val is None:
        return None
    if not isinstance(val, int):
        return f"{name} must be an integer"
    if not (min_v <= val <= max_v):
        return f"{name} must be within [{min_v}, {max_v}]"
    return None


def validate_min_max_pair(
    min_val: Any,
    max_val: Any,
    name: str,
    min_bound: int,
    max_bound: int,
) -> list[str]:
    """Validate a min/max pair. Returns list of error messages."""
    if min_val is None or max_val is None:
        return []
    if not isinstance(min_val, int) or not isinstance(max_val, int):
        return [f"{name} thresholds must be integers"]
    errors = []
    if min_val >= max_val:
        errors.append(f"{name} min must be less than max")
    if min_val < min_bound or max_val > max_bound:
        errors.append(f"{name} must be within [{min_bound}, {max_bound}]")
    return errors


def validate_list_items(
    items: Any, name: str, valid_values: Collection[str]
) -> list[str]:
    """Validate list items are from allowed values. Returns error messages."""
    if items is None:
        return []
    if not isinstance(items, list):
        return [f"{name} must be a list"]
    return [f"Invalid {name}: {item}" for item in items if item not in valid_values]


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
