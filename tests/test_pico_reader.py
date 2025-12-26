"""Tests for the Pico serial reader module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rpi.lib.alerts import AlertState, Namespace, get_alert_tracker
from rpi.lib.config import PlantId
from rpi.pico.models import MoistureReading, ValidationError


class TestMoistureReadingValidation:
    """Tests for MoistureReading validation."""

    def test_valid_plant_id(self, frozen_time):
        reading = MoistureReading.from_raw("plant-1", 50.0, frozen_time)
        assert reading.plant_id == 1
        assert reading.moisture == 50.0

    def test_valid_plant_id_multi_digit(self, frozen_time):
        reading = MoistureReading.from_raw("plant-99", 50.0, frozen_time)
        assert reading.plant_id == 99

    def test_invalid_plant_id_format_raises(self, frozen_time):
        with pytest.raises(
            ValidationError, match="must be in 'plant-N' format"
        ):
            MoistureReading.from_raw("invalid", 50.0, frozen_time)
        with pytest.raises(
            ValidationError, match="must be in 'plant-N' format"
        ):
            MoistureReading.from_raw("plant_1", 50.0, frozen_time)
        with pytest.raises(
            ValidationError, match="must be in 'plant-N' format"
        ):
            MoistureReading.from_raw("", 50.0, frozen_time)

    def test_non_string_plant_id_raises(self, frozen_time):
        with pytest.raises(ValidationError, match="must be a string"):
            MoistureReading.from_raw(123, 50.0, frozen_time)

    def test_valid_moisture_values(self, frozen_time):
        assert (
            MoistureReading.from_raw("plant-1", 50.0, frozen_time).moisture
            == 50.0
        )
        assert (
            MoistureReading.from_raw("plant-1", 0.0, frozen_time).moisture
            == 0.0
        )
        assert (
            MoistureReading.from_raw("plant-1", 100.0, frozen_time).moisture
            == 100.0
        )
        # int converted to float
        assert (
            MoistureReading.from_raw("plant-1", 50, frozen_time).moisture
            == 50.0
        )

    def test_moisture_below_min_raises(self, frozen_time):
        with pytest.raises(ValidationError, match="must be between 0"):
            MoistureReading.from_raw("plant-1", -1.0, frozen_time)

    def test_moisture_above_max_raises(self, frozen_time):
        with pytest.raises(ValidationError, match="must be between 0"):
            MoistureReading.from_raw("plant-1", 101.0, frozen_time)

    def test_non_number_moisture_raises(self, frozen_time):
        with pytest.raises(ValidationError, match="must be a number"):
            MoistureReading.from_raw("plant-1", "50", frozen_time)


class TestPicoPollingServicePoll:
    """Tests for PicoPollingService poll method."""

    @pytest.fixture
    def mock_source(self):
        source = MagicMock()
        source.readline = AsyncMock()
        source.close = MagicMock()
        return source

    @pytest.fixture
    def service(self, mock_source):
        from rpi.pico.reader import PicoPollingService

        return PicoPollingService(mock_source)

    @pytest.mark.asyncio
    async def test_empty_line_returns_none(self, service, mock_source):
        mock_source.readline.return_value = ""
        result = await service.poll()
        assert result is None

    @pytest.mark.asyncio
    async def test_whitespace_line_returns_none(self, service, mock_source):
        mock_source.readline.return_value = "   \n"
        result = await service.poll()
        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_json_returns_none(
        self, service, mock_source, caplog
    ):
        mock_source.readline.return_value = "{invalid json}"
        result = await service.poll()
        assert result is None
        assert "Invalid JSON" in caplog.text

    @pytest.mark.asyncio
    async def test_non_dict_json_returns_none(
        self, service, mock_source, caplog
    ):
        mock_source.readline.return_value = "[1, 2, 3]"
        result = await service.poll()
        assert result is None
        assert "Expected JSON object" in caplog.text

    @pytest.mark.asyncio
    async def test_valid_json_returns_readings(
        self, service, mock_source, frozen_time
    ):
        with patch("rpi.pico.reader.datetime") as mock_dt:
            mock_dt.now.return_value = frozen_time
            mock_source.readline.return_value = (
                '{"plant-1": 50.0, "plant-2": 60.0}'
            )

            result = await service.poll()

            assert len(result) == 2
            assert result[0].plant_id == 1
            assert result[0].moisture == 50.0
            assert result[1].plant_id == 2
            assert result[1].moisture == 60.0

    @pytest.mark.asyncio
    async def test_invalid_readings_skipped(
        self, service, mock_source, frozen_time, caplog
    ):
        with patch("rpi.pico.reader.datetime") as mock_dt:
            mock_dt.now.return_value = frozen_time
            mock_source.readline.return_value = (
                '{"plant-1": 50.0, "invalid": 60.0, "plant-2": 150.0}'
            )

            result = await service.poll()

            # Only plant-1 is valid
            assert len(result) == 1
            assert result[0].plant_id == 1
            assert "Validation failed" in caplog.text


class TestPicoPollingServiceAudit:
    """Tests for moisture alert logic."""

    @pytest.fixture
    def mock_source(self):
        source = MagicMock()
        source.readline = AsyncMock()
        source.close = MagicMock()
        return source

    @pytest.fixture
    def service(self, mock_source):
        from rpi.pico.reader import PicoPollingService

        return PicoPollingService(mock_source)

    @pytest.mark.asyncio
    @patch("rpi.pico.reader.get_moisture_threshold", return_value=30)
    async def test_no_alert_when_above_threshold(
        self, mock_threshold, service, pico_audit_events, frozen_time
    ):
        readings = [MoistureReading(PlantId.PLANT_1, 50.0, frozen_time)]
        await service.audit(readings)

        assert len(pico_audit_events) == 0
        tracker = get_alert_tracker()
        assert (
            tracker.get_state(Namespace.PICO, PlantId.PLANT_1) == AlertState.OK
        )

    @pytest.mark.asyncio
    @patch("rpi.pico.reader.get_moisture_threshold", return_value=30)
    async def test_alert_when_below_threshold(
        self, mock_threshold, service, pico_audit_events, frozen_time
    ):
        readings = [MoistureReading(PlantId.PLANT_1, 20.0, frozen_time)]
        await service.audit(readings)

        assert len(pico_audit_events) == 1
        event = pico_audit_events[0]
        assert event.sensor_name == PlantId.PLANT_1
        assert event.value == 20.0
        assert event.threshold == 30
        assert event.namespace == Namespace.PICO
        tracker = get_alert_tracker()
        assert (
            tracker.get_state(Namespace.PICO, PlantId.PLANT_1)
            == AlertState.IN_ALERT
        )

    @pytest.mark.asyncio
    @patch("rpi.pico.reader.get_moisture_threshold", return_value=30)
    async def test_no_duplicate_alerts(
        self, mock_threshold, service, pico_audit_events, frozen_time
    ):
        # First alert
        await service.audit(
            [MoistureReading(PlantId.PLANT_1, 20.0, frozen_time)]
        )
        # Still below threshold
        await service.audit(
            [MoistureReading(PlantId.PLANT_1, 15.0, frozen_time)]
        )

        # Only one event triggered
        assert len(pico_audit_events) == 1

    @pytest.mark.asyncio
    @patch("rpi.pico.reader.get_moisture_threshold", return_value=30)
    async def test_independent_plant_states(
        self, mock_threshold, service, pico_audit_events, frozen_time
    ):
        await service.audit(
            [MoistureReading(PlantId.PLANT_1, 20.0, frozen_time)]
        )
        await service.audit(
            [MoistureReading(PlantId.PLANT_2, 50.0, frozen_time)]
        )
        await service.audit(
            [MoistureReading(PlantId.PLANT_2, 20.0, frozen_time)]
        )

        assert len(pico_audit_events) == 2
        tracker = get_alert_tracker()
        assert (
            tracker.get_state(Namespace.PICO, PlantId.PLANT_1)
            == AlertState.IN_ALERT
        )
        assert (
            tracker.get_state(Namespace.PICO, PlantId.PLANT_2)
            == AlertState.IN_ALERT
        )
