"""Centralized configuration for the RPi Gardener application.

This package provides:
- Enums for sensor types, thresholds, and notification backends
- Pydantic settings models for configuration
- Functions for accessing DB-backed runtime settings
"""

from .enums import (
    MeasureName,
    NotificationBackend,
    PlantId,
    SettingsKey,
    ThresholdType,
    Unit,
)
from .settings import (
    AlertSettings,
    CleanupSettings,
    DHT22_BOUNDS,
    DisplaySettings,
    EventBusSettings,
    GmailSettings,
    HumidifierSettings,
    LCDSettings,
    NotificationSettings,
    OLEDSettings,
    PicoSettings,
    PlantIdValue,
    PollingSettings,
    Settings,
    SlackSettings,
    ThresholdSettings,
    get_settings,
    parse_pico_plant_id,
)
from .thresholds import (
    get_effective_notifications,
    get_effective_thresholds,
    get_threshold_rules_async,
)

__all__ = [
    # Enums
    "MeasureName",
    "NotificationBackend",
    "PlantId",
    "SettingsKey",
    "ThresholdType",
    "Unit",
    # Settings models
    "AlertSettings",
    "CleanupSettings",
    "DisplaySettings",
    "EventBusSettings",
    "GmailSettings",
    "HumidifierSettings",
    "LCDSettings",
    "NotificationSettings",
    "OLEDSettings",
    "PicoSettings",
    "PollingSettings",
    "Settings",
    "SlackSettings",
    "ThresholdSettings",
    # Constants
    "DHT22_BOUNDS",
    # Type aliases
    "PlantIdValue",
    # Functions
    "get_effective_notifications",
    "get_effective_thresholds",
    "get_settings",
    "get_threshold_rules_async",
    "parse_pico_plant_id",
]
