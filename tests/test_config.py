"""Tests for the configuration module."""

from unittest.mock import patch

import pytest
from pydantic import SecretStr, ValidationError

import rpi.lib.config as config
from rpi.lib.config import (
    GmailSettings,
    NotificationSettings,
    PicoSettings,
    Settings,
    SlackSettings,
    ThresholdSettings,
    get_settings,
    parse_pico_plant_id,
)


class TestParsePicoPlantId:
    """Tests for plant ID pattern parsing."""

    def test_valid_plant_ids(self):
        assert parse_pico_plant_id("plant-1") == 1
        assert parse_pico_plant_id("plant-2") == 2
        assert parse_pico_plant_id("plant-3") == 3
        assert parse_pico_plant_id("plant-99") == 99

    def test_invalid_format_returns_none(self):
        assert parse_pico_plant_id("plant_1") is None
        assert parse_pico_plant_id("Plant-1") is None
        assert parse_pico_plant_id("1") is None
        assert parse_pico_plant_id("") is None
        assert parse_pico_plant_id("plant-") is None
        assert parse_pico_plant_id("plant-abc") is None


class TestThresholdSettings:
    """Tests for threshold settings."""

    def test_default_values(self):
        settings = ThresholdSettings()

        assert settings.max_temperature == 25
        assert settings.min_temperature == 18
        assert settings.max_humidity == 65
        assert settings.min_humidity == 40
        assert settings.min_moisture == 30
        assert settings.plant_moisture_thresholds == {}

    def test_get_moisture_threshold_with_override(self):
        settings = ThresholdSettings(
            min_moisture=30, plant_moisture_thresholds={1: 25, 2: 35}
        )

        assert settings.get_moisture_threshold(1) == 25
        assert settings.get_moisture_threshold(2) == 35
        assert (
            settings.get_moisture_threshold(3) == 30
        )  # Falls back to default


class TestGmailSettings:
    """Tests for Gmail settings."""

    def test_default_values(self):
        settings = GmailSettings()

        assert settings.sender == ""
        assert settings.recipients == ""
        assert settings.username == ""
        assert settings.password.get_secret_value() == ""


class TestSlackSettings:
    """Tests for Slack settings."""

    def test_default_values(self):
        settings = SlackSettings()

        assert settings.webhook_url == ""


class TestNotificationSettings:
    """Tests for notification settings."""

    def test_default_values(self):
        settings = NotificationSettings()

        assert settings.enabled is False
        assert settings.backends == []
        assert settings.max_retries == 3


class TestPicoSettings:
    """Tests for Pico settings."""

    def test_default_values(self):
        settings = PicoSettings()

        assert settings.serial_port == "/dev/ttyACM0"
        assert settings.serial_baud == 115200
        assert settings.serial_timeout_sec == 30.0
        assert settings.moisture_min == 0.0
        assert settings.moisture_max == 100.0


class TestSettings:
    """Tests for main settings container."""

    def test_default_values(self):
        settings = Settings()

        assert settings.db_path == "dht.sqlite3"
        assert settings.db_timeout_sec == 30.0
        assert settings.mock_sensors is False

    @patch.dict(
        "os.environ",
        {
            "DB_PATH": "/custom/path.db",
            "DB_TIMEOUT_SEC": "60.0",
            "MOCK_SENSORS": "1",
        },
        clear=True,
    )
    def test_from_env(self):
        settings = Settings()

        assert settings.db_path == "/custom/path.db"
        assert settings.db_timeout_sec == 60.0
        assert settings.mock_sensors is True

    @patch.dict(
        "os.environ",
        {
            "MAX_TEMPERATURE": "30",
            "MIN_TEMPERATURE": "15",
            "MAX_HUMIDITY": "70",
            "MIN_HUMIDITY": "35",
            "MIN_MOISTURE": "25",
            "MIN_MOISTURE_PLANT_1": "20",
            "MIN_MOISTURE_PLANT_2": "30",
        },
        clear=True,
    )
    def test_thresholds_from_env(self):
        settings = Settings()

        assert settings.thresholds.max_temperature == 30
        assert settings.thresholds.min_temperature == 15
        assert settings.thresholds.max_humidity == 70
        assert settings.thresholds.min_humidity == 35
        assert settings.thresholds.min_moisture == 25
        assert settings.thresholds.plant_moisture_thresholds[1] == 20
        assert settings.thresholds.plant_moisture_thresholds[2] == 30

    @patch.dict(
        "os.environ",
        {
            "ENABLE_NOTIFICATION_SERVICE": "1",
            "NOTIFICATION_BACKENDS": "gmail,slack",
            "EMAIL_MAX_RETRIES": "5",
            "GMAIL_SENDER": "My Garden Alerts",
            "GMAIL_RECIPIENTS": "recv@example.com",
            "GMAIL_USERNAME": "testuser@gmail.com",
            "GMAIL_PASSWORD": "testpass",
            "SLACK_WEBHOOK_URL": "https://hooks.slack.com/test",
        },
        clear=True,
    )
    def test_notifications_from_env(self):
        settings = Settings()

        assert settings.notifications.enabled is True
        assert settings.notifications.backends == ["gmail", "slack"]
        assert settings.notifications.max_retries == 5

    @patch.dict(
        "os.environ",
        {"NOTIFICATION_BACKENDS": " gmail , slack , "},
        clear=True,
    )
    def test_backends_trimmed(self):
        settings = Settings()

        assert settings.notifications.backends == ["gmail", "slack"]

    @patch.dict(
        "os.environ",
        {
            "PICO_SERIAL_PORT": "/dev/ttyUSB0",
            "PICO_SERIAL_BAUD": "9600",
            "PICO_SERIAL_TIMEOUT_SEC": "10.0",
        },
        clear=True,
    )
    def test_pico_from_env(self):
        settings = Settings()

        assert settings.pico.serial_port == "/dev/ttyUSB0"
        assert settings.pico.serial_baud == 9600
        assert settings.pico.serial_timeout_sec == 10.0


class TestGetSettings:
    """Tests for global settings management."""

    def test_get_settings_lazy_initialization(self):
        config._settings_override = None
        config._load_settings.cache_clear()

        settings = get_settings()

        assert settings is not None
        assert isinstance(settings, Settings)

    def test_get_settings_uses_override(self):
        custom = Settings(db_path="custom.db")
        config._settings_override = custom

        assert get_settings().db_path == "custom.db"


class TestValidateConfig:
    """Tests for configuration validation (via model_validator)."""

    def test_valid_config_passes(self):
        # Should not raise - validation happens at construction
        Settings(
            min_temperature=10,
            max_temperature=30,
            min_humidity=30,
            max_humidity=70,
        )

    def test_min_temp_greater_than_max_fails(self):
        with pytest.raises(
            ValidationError, match="MIN_TEMPERATURE.*must be less than"
        ):
            Settings(
                min_temperature=30,
                max_temperature=20,
            )

    def test_min_humidity_greater_than_max_fails(self):
        with pytest.raises(
            ValidationError, match="MIN_HUMIDITY.*must be less than"
        ):
            Settings(
                min_humidity=70,
                max_humidity=50,
            )

    def test_temperature_outside_sensor_bounds_fails(self):
        with pytest.raises(
            ValidationError, match="greater than or equal to -40"
        ):
            Settings(
                min_temperature=-50,  # Below DHT22 min of -40
                max_temperature=30,
            )

    def test_humidity_outside_sensor_bounds_fails(self):
        with pytest.raises(
            ValidationError, match="greater than or equal to 0"
        ):
            Settings(
                min_humidity=-10,  # Below 0
                max_humidity=70,
            )

    def test_moisture_threshold_outside_bounds_fails(self):
        with pytest.raises(ValidationError, match="less than or equal to 100"):
            Settings(
                min_moisture_plant_1=150,  # Above 100
            )

    def test_gmail_enabled_without_credentials_fails(self):
        with pytest.raises(ValidationError, match="Gmail enabled but missing"):
            Settings(
                enable_notification_service=True,
                notification_backends="gmail",
                gmail_sender="",
                gmail_recipients="",
                gmail_username="",
                gmail_password=SecretStr(""),
            )

    def test_slack_enabled_without_webhook_fails(self):
        with pytest.raises(
            ValidationError, match="SLACK_WEBHOOK_URL is not set"
        ):
            Settings(
                enable_notification_service=True,
                notification_backends="slack",
                slack_webhook_url="",
            )

    def test_notifications_disabled_skips_credential_check(self):
        # Should not raise since notifications disabled
        Settings(
            enable_notification_service=False,
            notification_backends="gmail",
        )

    def test_multiple_errors_collected(self):
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                min_temperature=30,
                max_temperature=20,  # Error 1
                min_humidity=70,
                max_humidity=50,  # Error 2
            )

        error_message = str(exc_info.value)
        assert "MIN_TEMPERATURE" in error_message
        assert "MIN_HUMIDITY" in error_message
