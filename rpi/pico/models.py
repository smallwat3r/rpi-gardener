"""Domain models for Pico moisture sensor readings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from rpi.lib.config import PlantIdValue, get_settings, parse_pico_plant_id


class ValidationError(Exception):
    """Raised when input validation fails."""


@dataclass(slots=True)
class MoistureReading:
    """A validated moisture reading from a single plant sensor."""

    plant_id: PlantIdValue
    moisture: float
    recording_time: datetime

    @classmethod
    def from_raw(
        cls,
        raw_id: str,
        raw_moisture: float,
        recording_time: datetime,
    ) -> MoistureReading:
        """Create a validated reading from raw Pico data.

        Args:
            raw_id: Plant ID in 'plant-N' format.
            raw_moisture: Moisture percentage value.
            recording_time: When the reading was taken.

        Raises:
            ValidationError: If the input data is invalid.
        """
        plant_id = cls._validate_plant_id(raw_id)
        moisture = cls._validate_moisture(raw_moisture)
        return cls(plant_id, moisture, recording_time)

    @staticmethod
    def _validate_plant_id(raw_id: str) -> PlantIdValue:
        """Parse and validate plant_id from Pico's 'plant-N' format."""
        if not isinstance(raw_id, str):
            raise ValidationError(
                f"plant_id must be a string, got {type(raw_id).__name__}"
            )
        plant_id = parse_pico_plant_id(raw_id)
        if plant_id is None:
            raise ValidationError(
                f"plant_id must be in 'plant-N' format, got '{raw_id}'"
            )
        return plant_id

    @staticmethod
    def _validate_moisture(value: float) -> float:
        """Validate moisture value is a number within valid bounds."""
        if not isinstance(value, int | float):
            raise ValidationError(
                f"moisture must be a number, got {type(value).__name__}"
            )
        pico_cfg = get_settings().pico
        if not (pico_cfg.moisture_min <= value <= pico_cfg.moisture_max):
            raise ValidationError(
                f"moisture must be between {pico_cfg.moisture_min} "
                f"and {pico_cfg.moisture_max}, got {value}"
            )
        return float(value)
