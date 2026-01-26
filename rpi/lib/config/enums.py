"""Enumerations for the RPi Gardener application."""

from enum import IntEnum, StrEnum


class NotificationBackend(StrEnum):
    GMAIL = "gmail"
    SLACK = "slack"


class Unit(StrEnum):
    """Measurement units for sensor readings."""

    CELSIUS = "°C"
    PERCENT = "%"


class ThresholdType(StrEnum):
    """Type of threshold being checked."""

    MIN = "min"  # Alert when value < threshold
    MAX = "max"  # Alert when value > threshold


class MeasureName(StrEnum):
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"


class PlantId(IntEnum):
    PLANT_1 = 1
    PLANT_2 = 2
    PLANT_3 = 3

    @property
    def key(self) -> str:
        """Return the Pico data key format (e.g., 'plant-1')."""
        return f"plant-{self.value}"


class SettingsKey(StrEnum):
    """Valid DB settings keys."""

    TEMP_MIN = "threshold.temperature.min"
    TEMP_MAX = "threshold.temperature.max"
    HUMIDITY_MIN = "threshold.humidity.min"
    HUMIDITY_MAX = "threshold.humidity.max"
    MOISTURE_DEFAULT = "threshold.moisture.default"
    MOISTURE_1 = "threshold.moisture.1"
    MOISTURE_2 = "threshold.moisture.2"
    MOISTURE_3 = "threshold.moisture.3"
    NOTIFICATION_ENABLED = "notification.enabled"
    NOTIFICATION_BACKENDS = "notification.backends"
    RETENTION_DAYS = "cleanup.retention_days"


# Mapping from PlantId to moisture SettingsKey
PLANT_MOISTURE_KEYS: dict[PlantId, SettingsKey] = {
    PlantId.PLANT_1: SettingsKey.MOISTURE_1,
    PlantId.PLANT_2: SettingsKey.MOISTURE_2,
    PlantId.PLANT_3: SettingsKey.MOISTURE_3,
}
