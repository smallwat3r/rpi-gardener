"""Tests for the Pico serial reader module."""
from unittest.mock import MagicMock, patch

import pytest

from rpi.lib.config import PlantId
from rpi.pico import reader
from rpi.pico.reader import (ValidationError, _audit_moisture, _handle_line,
                             _parse_plant_id, _process_readings,
                             _validate_moisture)


class TestParsePlantId:
    """Tests for plant ID parsing."""

    def test_valid_plant_id(self):
        assert _parse_plant_id("plant-1") == 1
        assert _parse_plant_id("plant-2") == 2
        assert _parse_plant_id("plant-99") == 99

    def test_invalid_format_raises(self):
        with pytest.raises(ValidationError, match="must be in 'plant-N' format"):
            _parse_plant_id("invalid")
        with pytest.raises(ValidationError, match="must be in 'plant-N' format"):
            _parse_plant_id("plant_1")
        with pytest.raises(ValidationError, match="must be in 'plant-N' format"):
            _parse_plant_id("")

    def test_non_string_raises(self):
        with pytest.raises(ValidationError, match="must be a string"):
            _parse_plant_id(123)
        with pytest.raises(ValidationError, match="must be a string"):
            _parse_plant_id(None)


class TestValidateMoisture:
    """Tests for moisture value validation."""

    def test_valid_moisture(self):
        assert _validate_moisture(50.0) == 50.0
        assert _validate_moisture(0.0) == 0.0
        assert _validate_moisture(100.0) == 100.0
        assert _validate_moisture(50) == 50.0  # int converted to float

    def test_below_min_raises(self):
        with pytest.raises(ValidationError, match="must be between 0"):
            _validate_moisture(-1.0)

    def test_above_max_raises(self):
        with pytest.raises(ValidationError, match="must be between 0"):
            _validate_moisture(101.0)

    def test_non_number_raises(self):
        with pytest.raises(ValidationError, match="must be a number"):
            _validate_moisture("50")
        with pytest.raises(ValidationError, match="must be a number"):
            _validate_moisture(None)


class TestHandleLine:
    """Tests for JSON line processing."""

    def test_empty_line_ignored(self):
        # Should not raise
        _handle_line("")
        _handle_line("   ")

    def test_invalid_json_logged(self, caplog):
        _handle_line("{invalid json}")
        assert "Invalid JSON" in caplog.text

    def test_non_dict_json_logged(self, caplog):
        _handle_line("[1, 2, 3]")
        assert "Expected JSON object" in caplog.text

    @patch.object(reader, "_process_readings")
    def test_valid_json_processed(self, mock_process):
        mock_process.return_value = 1
        _handle_line('{"plant-1": 50.0}')
        mock_process.assert_called_once_with({"plant-1": 50.0})


class TestProcessReadings:
    """Tests for processing multiple readings."""

    @patch.object(reader, "_persist")
    @patch.object(reader, "_audit_moisture")
    @patch.object(reader, "utcnow")
    def test_valid_readings_persisted(self, mock_time, mock_audit, mock_persist, frozen_time):
        mock_time.return_value = frozen_time

        count = _process_readings({"plant-1": 50.0, "plant-2": 60.0})

        assert count == 2
        assert mock_persist.call_count == 2
        assert mock_audit.call_count == 2

    @patch.object(reader, "_persist")
    @patch.object(reader, "_audit_moisture")
    @patch.object(reader, "utcnow")
    def test_invalid_readings_skipped(self, mock_time, mock_audit, mock_persist, frozen_time):
        mock_time.return_value = frozen_time

        count = _process_readings({
            "plant-1": 50.0,   # valid
            "": 60.0,          # invalid plant_id
            "plant-2": 150.0,  # invalid moisture
        })

        assert count == 1
        mock_persist.assert_called_once()

    @patch.object(reader, "_persist")
    @patch.object(reader, "_audit_moisture")
    @patch.object(reader, "utcnow")
    def test_persist_error_continues(self, mock_time, mock_audit, mock_persist, frozen_time):
        mock_time.return_value = frozen_time
        mock_persist.side_effect = [Exception("DB error"), None]

        count = _process_readings({"plant-1": 50.0, "plant-2": 60.0})

        # First fails, second succeeds
        assert count == 1


class TestAuditMoisture:
    """Tests for moisture alert logic."""

    def setup_method(self):
        """Reset alert state before each test."""
        reader._alert_tracker.reset()

    @patch.object(reader, "get_notifier")
    @patch.object(reader, "get_moisture_threshold", return_value=30)
    def test_no_alert_when_above_threshold(self, mock_threshold, mock_get_notifier, frozen_time):
        from rpi.lib.alerts import AlertState

        notifier = MagicMock()
        mock_get_notifier.return_value = notifier

        _audit_moisture(PlantId.PLANT_1, 50.0, frozen_time)

        notifier.send.assert_not_called()
        assert reader._alert_tracker.get_state(PlantId.PLANT_1) == AlertState.OK

    @patch.object(reader, "get_notifier")
    @patch.object(reader, "get_moisture_threshold", return_value=30)
    def test_alert_when_below_threshold(self, mock_threshold, mock_get_notifier, frozen_time):
        from rpi.lib.alerts import AlertState

        notifier = MagicMock()
        mock_get_notifier.return_value = notifier

        _audit_moisture(PlantId.PLANT_1, 20.0, frozen_time)

        notifier.send.assert_called_once()
        event = notifier.send.call_args[0][0]
        assert event.sensor_name == PlantId.PLANT_1
        assert event.value == 20.0
        assert event.threshold == 30
        assert reader._alert_tracker.get_state(PlantId.PLANT_1) == AlertState.IN_ALERT

    @patch.object(reader, "get_notifier")
    @patch.object(reader, "get_moisture_threshold", return_value=30)
    def test_no_duplicate_alerts(self, mock_threshold, mock_get_notifier, frozen_time):
        notifier = MagicMock()
        mock_get_notifier.return_value = notifier

        # First alert
        _audit_moisture(PlantId.PLANT_1, 20.0, frozen_time)
        # Still below threshold
        _audit_moisture(PlantId.PLANT_1, 15.0, frozen_time)

        # Only one notification sent
        assert notifier.send.call_count == 1

    @patch.object(reader, "get_notifier")
    @patch.object(reader, "get_moisture_threshold", return_value=30)
    def test_new_alert_after_recovery(self, mock_threshold, mock_get_notifier, frozen_time):
        notifier = MagicMock()
        mock_get_notifier.return_value = notifier

        # First alert
        _audit_moisture(PlantId.PLANT_1, 20.0, frozen_time)
        # Recovery
        _audit_moisture(PlantId.PLANT_1, 50.0, frozen_time)
        # New alert
        _audit_moisture(PlantId.PLANT_1, 25.0, frozen_time)

        assert notifier.send.call_count == 2

    @patch.object(reader, "get_notifier")
    @patch.object(reader, "get_moisture_threshold", return_value=30)
    def test_independent_plant_states(self, mock_threshold, mock_get_notifier, frozen_time):
        from rpi.lib.alerts import AlertState

        notifier = MagicMock()
        mock_get_notifier.return_value = notifier

        _audit_moisture(PlantId.PLANT_1, 20.0, frozen_time)
        _audit_moisture(PlantId.PLANT_2, 50.0, frozen_time)
        _audit_moisture(PlantId.PLANT_2, 20.0, frozen_time)

        assert notifier.send.call_count == 2
        assert reader._alert_tracker.get_state(PlantId.PLANT_1) == AlertState.IN_ALERT
        assert reader._alert_tracker.get_state(PlantId.PLANT_2) == AlertState.IN_ALERT
