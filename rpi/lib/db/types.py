"""Type definitions for database operations."""

from typing import Any, TypedDict

type SQLParams = tuple[Any, ...] | dict[str, Any]
"""SQL parameter types: positional tuple or named dict for query binding."""


class DHTReading(TypedDict):
    """DHT22 sensor reading from the database."""

    temperature: float
    humidity: float
    recording_time: str
    epoch: int


class PicoReading(TypedDict):
    """Pico moisture reading from the database."""

    plant_id: int
    moisture: float
    recording_time: str
    epoch: int
