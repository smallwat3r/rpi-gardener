"""Tests for DB-backed runtime settings."""

from rpi.lib.config import SettingsKey
from rpi.lib.db import get_all_settings, set_settings_batch


async def test_set_then_get_roundtrip():
    assert await get_all_settings() == {}

    result = await set_settings_batch(
        {SettingsKey.TEMP_MAX: "30", SettingsKey.NOTIFICATION_ENABLED: "1"}
    )
    assert result == {
        SettingsKey.TEMP_MAX: "30",
        SettingsKey.NOTIFICATION_ENABLED: "1",
    }
    assert await get_all_settings() == result


async def test_set_overwrites_existing_key():
    await set_settings_batch({SettingsKey.TEMP_MAX: "30"})
    await set_settings_batch({SettingsKey.TEMP_MAX: "28"})
    assert (await get_all_settings())[SettingsKey.TEMP_MAX] == "28"
