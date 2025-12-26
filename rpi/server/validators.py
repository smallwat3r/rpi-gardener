"""Shared validation utilities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field

MIN_HOURS = 1
MAX_HOURS = 168  # 7 days max (matches retention)
DEFAULT_HOURS = 24


class HoursQuery(BaseModel):
    """Validated hours query parameter."""

    hours: int = Field(default=DEFAULT_HOURS, ge=MIN_HOURS, le=MAX_HOURS)

    @property
    def from_time(self) -> datetime:
        """Get the datetime for hours ago from now."""
        return datetime.now(UTC) - timedelta(hours=self.hours)

    @classmethod
    def from_params(cls, params: dict[str, str] | None) -> HoursQuery:
        """Parse from query params dict, using default for missing/invalid."""
        if not params:
            return cls()
        raw = params.get("hours", DEFAULT_HOURS)
        try:
            hours = int(raw)
        except (ValueError, TypeError):
            raise ValueError("hours must be an integer") from None
        return cls(hours=hours)
