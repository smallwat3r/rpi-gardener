"""Tests for the Pico serial reader module."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rpi.lib.alerts import AlertState, Namespace, get_alert_tracker
from rpi.lib.config import PlantId
from rpi.pico import reader
from rpi.pico.reader import (ValidationError, _audit_moisture,
                             _parse_plant_id, _validate_moisture)


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

    @pytest.mark.asyncio
    async def test_empty_line_ignored(self):
        # Should not raise
        await reader._handle_line("")
        await reader._handle_line("   ")

    @pytest.mark.asyncio
    async def test_invalid_json_logged(self, caplog):
        await reader._handle_line("{invalid json}")
        assert "Invalid JSON" in caplog.text

    @pytest.mark.asyncio
    async def test_non_dict_json_logged(self, caplog):
        await reader._handle_line("[1, 2, 3]")
        assert "Expected JSON object" in caplog.text

    @pytest.mark.asyncio
    @patch.object(reader, "_process_readings", new_callable=AsyncMock)
    async def test_valid_json_processed(self, mock_process):
        mock_process.return_value = 1
        await reader._handle_line('{"plant-1": 50.0}')
        mock_process.assert_called_once_with({"plant-1": 50.0})


class TestProcessReadings:
    """Tests for processing multiple readings."""

    @pytest.mark.asyncio
    @patch.object(reader, "_persist", new_callable=AsyncMock)
    @patch.object(reader, "_audit_moisture")
    @patch.object(reader, "utcnow")
    async def test_valid_readings_persisted(self, mock_time, mock_audit, mock_persist, frozen_time):
        mock_time.return_value = frozen_time

        count = await reader._process_readings({"plant-1": 50.0, "plant-2": 60.0})

        assert count == 2
        assert mock_persist.call_count == 2
        assert mock_audit.call_count == 2

    @pytest.mark.asyncio
    @patch.object(reader, "_persist", new_callable=AsyncMock)
    @patch.object(reader, "_audit_moisture")
    @patch.object(reader, "utcnow")
    async def test_invalid_readings_skipped(self, mock_time, mock_audit, mock_persist, frozen_time):
        mock_time.return_value = frozen_time

        count = await reader._process_readings({
            "plant-1": 50.0,   # valid
            "": 60.0,          # invalid plant_id
            "plant-2": 150.0,  # invalid moisture
        })

        assert count == 1
        mock_persist.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(reader, "_persist", new_callable=AsyncMock)
    @patch.object(reader, "_audit_moisture")
    @patch.object(reader, "utcnow")
    async def test_persist_error_continues(self, mock_time, mock_audit, mock_persist, frozen_time):
        mock_time.return_value = frozen_time
        mock_persist.side_effect = [Exception("DB error"), None]

        count = await reader._process_readings({"plant-1": 50.0, "plant-2": 60.0})

        # First fails, second succeeds
        assert count == 1


class TestAuditMoisture:
    """Tests for moisture alert logic."""

    def setup_method(self):
        """Register Pico alerts callback before each test."""
        from rpi.pico.reader import _register_pico_alerts
        _register_pico_alerts()

    @pytest.mark.asyncio
    @patch.object(reader, "get_notifier")
    @patch.object(reader, "get_moisture_threshold", return_value=30)
    async def test_no_alert_when_above_threshold(self, mock_threshold, mock_get_notifier, frozen_time):
        notifier = MagicMock()
        notifier.send = AsyncMock()
        mock_get_notifier.return_value = notifier

        _audit_moisture(PlantId.PLANT_1, 50.0, frozen_time)

        notifier.send.assert_not_called()
        tracker = get_alert_tracker()
        assert tracker.get_state(Namespace.PICO, PlantId.PLANT_1) == AlertState.OK

    @pytest.mark.asyncio
    @patch.object(reader, "get_notifier")
    @patch.object(reader, "get_moisture_threshold", return_value=30)
    async def test_alert_when_below_threshold(self, mock_threshold, mock_get_notifier, frozen_time):
        notifier = MagicMock()
        notifier.send = AsyncMock()
        mock_get_notifier.return_value = notifier

        _audit_moisture(PlantId.PLANT_1, 20.0, frozen_time)
        await asyncio.sleep(0)  # Let the scheduled task run

        notifier.send.assert_called_once()
        violation = notifier.send.call_args[0][0]
        assert violation.sensor_name == PlantId.PLANT_1
        assert violation.value == 20.0
        assert violation.threshold == 30
        assert violation.namespace == Namespace.PICO
        tracker = get_alert_tracker()
        assert tracker.get_state(Namespace.PICO, PlantId.PLANT_1) == AlertState.IN_ALERT

    @pytest.mark.asyncio
    @patch.object(reader, "get_notifier")
    @patch.object(reader, "get_moisture_threshold", return_value=30)
    async def test_no_duplicate_alerts(self, mock_threshold, mock_get_notifier, frozen_time):
        notifier = MagicMock()
        notifier.send = AsyncMock()
        mock_get_notifier.return_value = notifier

        # First alert
        _audit_moisture(PlantId.PLANT_1, 20.0, frozen_time)
        await asyncio.sleep(0)
        # Still below threshold
        _audit_moisture(PlantId.PLANT_1, 15.0, frozen_time)
        await asyncio.sleep(0)

        # Only one notification sent
        assert notifier.send.call_count == 1

    @pytest.mark.asyncio
    @patch.object(reader, "get_notifier")
    @patch.object(reader, "get_moisture_threshold", return_value=30)
    async def test_new_alert_after_recovery(self, mock_threshold, mock_get_notifier, frozen_time):
        notifier = MagicMock()
        notifier.send = AsyncMock()
        mock_get_notifier.return_value = notifier

        # First alert
        _audit_moisture(PlantId.PLANT_1, 20.0, frozen_time)
        await asyncio.sleep(0)
        # Recovery (also triggers notification now)
        _audit_moisture(PlantId.PLANT_1, 50.0, frozen_time)
        await asyncio.sleep(0)
        # New alert
        _audit_moisture(PlantId.PLANT_1, 25.0, frozen_time)
        await asyncio.sleep(0)

        # 3 notifications: alert, resolution, alert
        assert notifier.send.call_count == 3

    @pytest.mark.asyncio
    @patch.object(reader, "get_notifier")
    @patch.object(reader, "get_moisture_threshold", return_value=30)
    async def test_independent_plant_states(self, mock_threshold, mock_get_notifier, frozen_time):
        notifier = MagicMock()
        notifier.send = AsyncMock()
        mock_get_notifier.return_value = notifier

        _audit_moisture(PlantId.PLANT_1, 20.0, frozen_time)
        await asyncio.sleep(0)
        _audit_moisture(PlantId.PLANT_2, 50.0, frozen_time)
        await asyncio.sleep(0)
        _audit_moisture(PlantId.PLANT_2, 20.0, frozen_time)
        await asyncio.sleep(0)

        assert notifier.send.call_count == 2
        tracker = get_alert_tracker()
        assert tracker.get_state(Namespace.PICO, PlantId.PLANT_1) == AlertState.IN_ALERT
        assert tracker.get_state(Namespace.PICO, PlantId.PLANT_2) == AlertState.IN_ALERT
