"""Threshold rules and DB-backed settings fetching."""

from rpi.lib.config.constants import (
    HYSTERESIS_HUMIDITY,
    HYSTERESIS_TEMPERATURE,
)
from rpi.lib.config.enums import (
    MeasureName,
    NotificationBackend,
    SettingsKey,
    ThresholdType,
)
from rpi.lib.config.settings import (
    NotificationSettings,
    ThresholdSettings,
    get_settings,
)

type _ThresholdRule = tuple[ThresholdType, int, float]
"""Threshold rule: (type, value, hysteresis)."""


async def get_threshold_rules_async() -> dict[MeasureName, tuple[_ThresholdRule, ...]]:
    """Get threshold rules with DB overrides applied.

    This checks the database for runtime setting changes made via
    the admin API, falling back to environment variable defaults.

    Returns a dict mapping measure name to a tuple of (threshold_type, value,
    hysteresis).
    """
    thresholds = await get_effective_thresholds()
    return {
        MeasureName.TEMPERATURE: (
            (
                ThresholdType.MIN,
                thresholds.min_temperature,
                HYSTERESIS_TEMPERATURE,
            ),
            (
                ThresholdType.MAX,
                thresholds.max_temperature,
                HYSTERESIS_TEMPERATURE,
            ),
        ),
        MeasureName.HUMIDITY: (
            (
                ThresholdType.MIN,
                thresholds.min_humidity,
                HYSTERESIS_HUMIDITY,
            ),
            (
                ThresholdType.MAX,
                thresholds.max_humidity,
                HYSTERESIS_HUMIDITY,
            ),
        ),
    }


async def get_effective_thresholds() -> ThresholdSettings:
    """Get threshold settings with DB overrides applied."""
    from rpi.lib.db import get_all_settings

    db_settings = await get_all_settings()
    env_settings = get_settings()

    def get_int(key: SettingsKey, default: int) -> int:
        val = db_settings.get(key)
        return int(val) if val is not None else default

    min_moisture = get_int(
        SettingsKey.MOISTURE_DEFAULT, env_settings.thresholds.min_moisture
    )
    moisture_keys: dict[int, SettingsKey] = {
        1: SettingsKey.MOISTURE_1,
        2: SettingsKey.MOISTURE_2,
        3: SettingsKey.MOISTURE_3,
    }
    plant_thresholds = {
        i: get_int(
            moisture_keys[i],
            env_settings.thresholds.get_moisture_threshold(i),
        )
        for i in (1, 2, 3)
    }

    return ThresholdSettings(
        max_temperature=get_int(
            SettingsKey.TEMP_MAX,
            env_settings.thresholds.max_temperature,
        ),
        min_temperature=get_int(
            SettingsKey.TEMP_MIN,
            env_settings.thresholds.min_temperature,
        ),
        max_humidity=get_int(
            SettingsKey.HUMIDITY_MAX, env_settings.thresholds.max_humidity
        ),
        min_humidity=get_int(
            SettingsKey.HUMIDITY_MIN, env_settings.thresholds.min_humidity
        ),
        min_moisture=min_moisture,
        plant_moisture_thresholds=plant_thresholds,
    )


async def get_effective_notifications() -> NotificationSettings:
    """Get notification settings with DB overrides applied."""
    from rpi.lib.db import get_all_settings

    db_settings = await get_all_settings()
    env_settings = get_settings()

    enabled_val = db_settings.get(SettingsKey.NOTIFICATION_ENABLED)
    enabled = (
        enabled_val == "1"
        if enabled_val is not None
        else env_settings.notifications.enabled
    )

    backends_val = db_settings.get(SettingsKey.NOTIFICATION_BACKENDS)
    backends: list[NotificationBackend] = (
        [
            NotificationBackend(b.strip())
            for b in backends_val.split(",")
            if b.strip()
        ]
        if backends_val is not None
        else list(env_settings.notifications.backends)
    )

    return NotificationSettings(
        enabled=enabled,
        backends=backends,
        gmail=env_settings.notifications.gmail,
        slack=env_settings.notifications.slack,
        max_retries=env_settings.notifications.max_retries,
        initial_backoff_sec=env_settings.notifications.initial_backoff_sec,
        timeout_sec=env_settings.notifications.timeout_sec,
    )
