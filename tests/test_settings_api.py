"""Tests for admin settings API."""

import pytest
from pydantic import ValidationError

from rpi.lib.config import SettingsKey
from rpi.server.api.admin import (
    _AdminSettingsRequest,
    _db_settings_to_response,
    _request_to_db_settings,
)


class TestSettingsValidation:
    """Tests for settings validation via Pydantic."""

    def test_validate_valid_settings(self):
        """Valid settings should parse without errors."""
        settings = {
            "thresholds": {
                "temperature": {"min": 18, "max": 25},
                "humidity": {"min": 40, "max": 65},
                "moisture": {"default": 30, "1": 55, "2": 30, "3": 35},
            },
            "notifications": {
                "enabled": True,
                "backends": ["gmail", "slack"],
            },
            "cleanup": {
                "retentionDays": 7,
            },
        }

        # Should not raise
        data = _AdminSettingsRequest.model_validate(settings)
        assert data.thresholds.temperature.min == 18
        assert data.thresholds.temperature.max == 25

    def test_validate_temperature_min_gt_max(self):
        """Should error when temperature min >= max."""
        settings = {
            "thresholds": {
                "temperature": {"min": 30, "max": 25},
            },
        }

        with pytest.raises(ValidationError) as exc_info:
            _AdminSettingsRequest.model_validate(settings)
        assert "max must be greater than min" in str(exc_info.value)

    def test_validate_temperature_out_of_bounds(self):
        """Should error when temperature outside [-40, 80]."""
        settings = {
            "thresholds": {
                "temperature": {"min": -50, "max": 90},
            },
        }

        with pytest.raises(ValidationError) as exc_info:
            _AdminSettingsRequest.model_validate(settings)
        errors = str(exc_info.value).lower()
        assert "greater than or equal to -40" in errors or "ge" in errors

    def test_validate_humidity_min_gt_max(self):
        """Should error when humidity min >= max."""
        settings = {
            "thresholds": {
                "humidity": {"min": 70, "max": 50},
            },
        }

        with pytest.raises(ValidationError) as exc_info:
            _AdminSettingsRequest.model_validate(settings)
        assert "max must be greater than min" in str(exc_info.value)

    def test_validate_humidity_out_of_bounds(self):
        """Should error when humidity outside [0, 100]."""
        settings = {
            "thresholds": {
                "humidity": {"min": -10, "max": 110},
            },
        }

        with pytest.raises(ValidationError) as exc_info:
            _AdminSettingsRequest.model_validate(settings)
        errors = str(exc_info.value).lower()
        assert "greater than or equal to 0" in errors or "ge" in errors

    def test_validate_moisture_out_of_bounds(self):
        """Should error when moisture outside [0, 100]."""
        settings = {
            "thresholds": {
                "moisture": {"1": 150},
            },
        }

        with pytest.raises(ValidationError) as exc_info:
            _AdminSettingsRequest.model_validate(settings)
        errors = str(exc_info.value).lower()
        assert "less than or equal to 100" in errors or "le" in errors

    def test_validate_invalid_backend(self):
        """Should error for invalid notification backend."""
        settings = {
            "notifications": {
                "backends": ["invalid_backend"],
            },
        }

        with pytest.raises(ValidationError) as exc_info:
            _AdminSettingsRequest.model_validate(settings)
        assert "Invalid backends" in str(exc_info.value)

    def test_validate_retention_days_out_of_bounds(self):
        """Should error when retention days outside [1, 365]."""
        settings = {
            "cleanup": {
                "retentionDays": 500,
            },
        }

        with pytest.raises(ValidationError) as exc_info:
            _AdminSettingsRequest.model_validate(settings)
        errors = str(exc_info.value).lower()
        assert "less than or equal to 365" in errors or "le" in errors


class TestSettingsConversion:
    """Tests for settings format conversion."""

    def test_request_to_db_settings(self):
        """Should convert structured request to flat DB keys."""
        request = _AdminSettingsRequest.model_validate(
            {
                "thresholds": {
                    "temperature": {"min": 18, "max": 25},
                    "humidity": {"min": 40, "max": 65},
                    "moisture": {"default": 30, "1": 55},
                },
                "notifications": {
                    "enabled": True,
                    "backends": ["gmail", "slack"],
                },
                "cleanup": {
                    "retentionDays": 7,
                },
            }
        )

        result = _request_to_db_settings(request)

        assert result[SettingsKey.TEMP_MIN] == "18"
        assert result[SettingsKey.TEMP_MAX] == "25"
        assert result[SettingsKey.HUMIDITY_MIN] == "40"
        assert result[SettingsKey.HUMIDITY_MAX] == "65"
        assert result[SettingsKey.MOISTURE_DEFAULT] == "30"
        assert result[SettingsKey.MOISTURE_1] == "55"
        assert result[SettingsKey.NOTIFICATION_ENABLED] == "1"
        assert result[SettingsKey.NOTIFICATION_BACKENDS] == "gmail,slack"
        assert result[SettingsKey.RETENTION_DAYS] == "7"

    def test_request_to_db_settings_partial(self):
        """Should handle partial settings update."""
        request = _AdminSettingsRequest.model_validate(
            {
                "thresholds": {
                    "temperature": {"min": 20},
                },
            }
        )

        result = _request_to_db_settings(request)

        assert result[SettingsKey.TEMP_MIN] == "20"
        assert SettingsKey.TEMP_MAX not in result

    def test_db_settings_to_response_with_defaults(self):
        """Should use env defaults when DB settings are empty."""
        db_settings: dict[SettingsKey, str] = {}

        result = _db_settings_to_response(db_settings)

        # Should return structured format with defaults from env
        assert "thresholds" in result
        assert "notifications" in result
        assert "cleanup" in result
        assert "temperature" in result["thresholds"]
        assert "humidity" in result["thresholds"]
        assert "moisture" in result["thresholds"]

    def test_db_settings_to_response_with_overrides(self):
        """Should use DB values when present."""
        db_settings: dict[SettingsKey, str] = {
            SettingsKey.TEMP_MIN: "20",
            SettingsKey.TEMP_MAX: "30",
            SettingsKey.NOTIFICATION_ENABLED: "1",
            SettingsKey.NOTIFICATION_BACKENDS: "slack",
            SettingsKey.RETENTION_DAYS: "14",
        }

        result = _db_settings_to_response(db_settings)

        assert result["thresholds"]["temperature"]["min"] == 20
        assert result["thresholds"]["temperature"]["max"] == 30
        assert result["notifications"]["enabled"] is True
        assert result["notifications"]["backends"] == ["slack"]
        assert result["cleanup"]["retentionDays"] == 14
