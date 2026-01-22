"""Tests for the Pico serial reader module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rpi.lib.alerts import AlertState, AlertTracker, Namespace
from rpi.lib.config import PlantId, ThresholdSettings, ThresholdType
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
            MoistureReading.from_raw(123, 50.0, frozen_time)  # type: ignore[arg-type]

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
            MoistureReading.from_raw("plant-1", "50", frozen_time)  # type: ignore[arg-type]


class TestPicoPollingServicePoll:
    """Tests for PicoPollingService poll method."""

    @pytest.fixture
    def mock_source(self):
        source = MagicMock()
        source.readline = AsyncMock()
        source.close = MagicMock()
        return source

    @pytest.fixture
    def mock_publisher(self):
        publisher = MagicMock()
        publisher.connect = MagicMock()
        publisher.publish = MagicMock()
        publisher.close = MagicMock()
        return publisher

    @pytest.fixture
    def service(self, mock_source, mock_publisher, alert_tracker):
        from rpi.pico.reader import PicoPollingService

        return PicoPollingService(mock_source, mock_publisher, alert_tracker)

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
    def mock_publisher(self):
        publisher = MagicMock()
        publisher.connect = MagicMock()
        publisher.publish = MagicMock()
        publisher.close = MagicMock()
        return publisher

    @pytest.fixture
    def service(self, mock_source, mock_publisher, alert_tracker):
        from rpi.pico.reader import PicoPollingService

        return PicoPollingService(mock_source, mock_publisher, alert_tracker)

    @pytest.mark.asyncio
    @patch("rpi.pico.reader.get_effective_thresholds")
    async def test_no_alert_when_above_threshold(
        self,
        mock_thresholds,
        service,
        pico_audit_events,
        frozen_time,
        alert_tracker,
    ):
        mock_thresholds.return_value = ThresholdSettings(min_moisture=30)
        readings = [MoistureReading(PlantId.PLANT_1, 50.0, frozen_time)]
        await service.audit(readings)

        assert len(pico_audit_events) == 0
        assert (
            await alert_tracker.get_state(
                Namespace.PICO, PlantId.PLANT_1, ThresholdType.MIN
            )
            == AlertState.OK
        )

    @pytest.mark.asyncio
    @patch("rpi.pico.reader.get_effective_thresholds")
    async def test_alert_when_below_threshold(
        self,
        mock_thresholds,
        service,
        pico_audit_events,
        frozen_time,
        alert_tracker,
    ):
        mock_thresholds.return_value = ThresholdSettings(min_moisture=30)
        readings = [MoistureReading(PlantId.PLANT_1, 20.0, frozen_time)]
        await service.audit(readings)

        assert len(pico_audit_events) == 1
        event = pico_audit_events[0]
        assert event.sensor_name == PlantId.PLANT_1
        assert event.value == 20.0
        assert event.threshold == 30
        assert event.namespace == Namespace.PICO
        assert (
            await alert_tracker.get_state(
                Namespace.PICO, PlantId.PLANT_1, ThresholdType.MIN
            )
            == AlertState.IN_ALERT
        )

    @pytest.mark.asyncio
    @patch("rpi.pico.reader.get_effective_thresholds")
    async def test_no_duplicate_alerts(
        self, mock_thresholds, service, pico_audit_events, frozen_time
    ):
        mock_thresholds.return_value = ThresholdSettings(min_moisture=30)
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
    @patch("rpi.pico.reader.get_effective_thresholds")
    async def test_independent_plant_states(
        self,
        mock_thresholds,
        service,
        pico_audit_events,
        frozen_time,
        alert_tracker,
    ):
        mock_thresholds.return_value = ThresholdSettings(min_moisture=30)
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
        assert (
            await alert_tracker.get_state(
                Namespace.PICO, PlantId.PLANT_1, ThresholdType.MIN
            )
            == AlertState.IN_ALERT
        )
        assert (
            await alert_tracker.get_state(
                Namespace.PICO, PlantId.PLANT_2, ThresholdType.MIN
            )
            == AlertState.IN_ALERT
        )

    @pytest.mark.asyncio
    @patch("rpi.pico.reader.get_effective_thresholds")
    async def test_hysteresis_prevents_moisture_flapping(
        self, mock_thresholds, service, pico_audit_events, frozen_time
    ):
        """Alert should not clear until moisture recovers past hysteresis band.

        With min_moisture=30 and hysteresis=3:
        - Alert triggers at moisture < 30
        - Alert clears at moisture >= 33 (30 + 3)
        - Value between 30-33 should stay IN_ALERT
        """
        mock_thresholds.return_value = ThresholdSettings(min_moisture=30)
        # Trigger alert with low moisture
        await service.audit(
            [MoistureReading(PlantId.PLANT_1, 25.0, frozen_time)]
        )
        assert len(pico_audit_events) == 1

        # Rise to 31 - within hysteresis band (30-33), should stay IN_ALERT
        await service.audit(
            [MoistureReading(PlantId.PLANT_1, 31.0, frozen_time)]
        )
        assert len(pico_audit_events) == 1  # No recovery event

        # Rise to 35 - above hysteresis band, should recover
        await service.audit(
            [MoistureReading(PlantId.PLANT_1, 35.0, frozen_time)]
        )
        assert len(pico_audit_events) == 2
        assert pico_audit_events[1].is_resolved is True


class TestSpikeDetection:
    """Tests for spike detection in PicoPollingService.

    Spikes to 100% are detected and marked (is_anomaly=True) but still recorded.
    This allows data visibility while suppressing alerts for suspected sensor
    errors. Large increases below 100% are normal (watering recovery).
    """

    @pytest.fixture
    def mock_source(self):
        source = MagicMock()
        source.readline = AsyncMock()
        source.close = MagicMock()
        return source

    @pytest.fixture
    def mock_publisher(self):
        publisher = MagicMock()
        publisher.connect = MagicMock()
        publisher.publish = MagicMock()
        publisher.close = MagicMock()
        return publisher

    @pytest.fixture
    def service(self, mock_source, mock_publisher, alert_tracker):
        from rpi.pico.reader import PicoPollingService

        return PicoPollingService(mock_source, mock_publisher, alert_tracker)

    @pytest.mark.asyncio
    async def test_spike_to_100_marked(self, service, mock_source, caplog):
        """Sudden jump to 100% should be marked as spike but still recorded."""
        with patch("rpi.pico.reader.datetime") as mock_dt:
            from datetime import UTC, datetime

            mock_dt.now.return_value = datetime(
                2024, 6, 15, 12, 0, 0, tzinfo=UTC
            )

            # First reading establishes baseline
            mock_source.readline.return_value = '{"plant-1": 50.0}'
            result = await service.poll()
            assert len(result) == 1
            assert result[0].moisture == 50.0
            assert result[0].is_anomaly is False

            # Spike to 100% should be marked but still returned
            mock_source.readline.return_value = '{"plant-1": 100.0}'
            result = await service.poll()
            assert len(result) == 1
            assert result[0].moisture == 100.0
            assert result[0].is_anomaly is True
            assert "Spike detected" in caplog.text

    @pytest.mark.asyncio
    async def test_large_increase_below_100_not_spike(
        self, service, mock_source
    ):
        """Large increases below 100% should not be marked as spike."""
        with patch("rpi.pico.reader.datetime") as mock_dt:
            from datetime import UTC, datetime

            mock_dt.now.return_value = datetime(
                2024, 6, 15, 12, 0, 0, tzinfo=UTC
            )

            # Dry soil
            mock_source.readline.return_value = '{"plant-1": 25.0}'
            result = await service.poll()
            assert result[0].moisture == 25.0
            assert result[0].is_anomaly is False

            # After watering - large jump to 80% should not be a spike
            mock_source.readline.return_value = '{"plant-1": 80.0}'
            result = await service.poll()
            assert len(result) == 1
            assert result[0].moisture == 80.0
            assert result[0].is_anomaly is False

    @pytest.mark.asyncio
    async def test_gradual_rise_to_100_accepted(self, service, mock_source):
        """Gradual rise to 100% within threshold should be accepted."""
        with patch("rpi.pico.reader.datetime") as mock_dt:
            from datetime import UTC, datetime

            mock_dt.now.return_value = datetime(
                2024, 6, 15, 12, 0, 0, tzinfo=UTC
            )

            # Already high moisture
            mock_source.readline.return_value = '{"plant-1": 85.0}'
            result = await service.poll()
            assert result[0].moisture == 85.0

            # Rise to 100% (within 20% threshold)
            mock_source.readline.return_value = '{"plant-1": 100.0}'
            result = await service.poll()
            assert len(result) == 1
            assert result[0].moisture == 100.0

    @pytest.mark.asyncio
    async def test_first_reading_never_spike(self, service, mock_source):
        """First reading for a plant should never be considered a spike."""
        with patch("rpi.pico.reader.datetime") as mock_dt:
            from datetime import UTC, datetime

            mock_dt.now.return_value = datetime(
                2024, 6, 15, 12, 0, 0, tzinfo=UTC
            )

            # Even 100% as first reading should be accepted
            mock_source.readline.return_value = '{"plant-1": 100.0}'
            result = await service.poll()
            assert len(result) == 1
            assert result[0].moisture == 100.0


class TestConfirmationWindow:
    """Tests for alert confirmation window in AlertTracker."""

    @pytest.fixture
    def tracker_with_confirmation(self):
        """AlertTracker requiring 3 consecutive readings to confirm."""
        return AlertTracker(confirmation_count=3)

    @pytest.fixture
    async def pico_events_with_confirmation(self, tracker_with_confirmation):
        from rpi.lib.alerts import AlertEvent

        events: list[AlertEvent] = []

        def capture_event(event: AlertEvent) -> None:
            events.append(event)

        await tracker_with_confirmation.register_callback(
            Namespace.PICO, capture_event
        )
        return events

    @pytest.mark.asyncio
    async def test_single_reading_no_alert(
        self,
        tracker_with_confirmation,
        pico_events_with_confirmation,
        frozen_time,
    ):
        """Single reading below threshold should not trigger alert."""
        await tracker_with_confirmation.check(
            namespace=Namespace.PICO,
            sensor_name=1,
            value=20.0,  # Below threshold
            unit="%",
            threshold=30,
            threshold_type=ThresholdType.MIN,
            hysteresis=3,
            recording_time=frozen_time,
        )
        assert len(pico_events_with_confirmation) == 0

    @pytest.mark.asyncio
    async def test_confirmation_after_three_readings(
        self,
        tracker_with_confirmation,
        pico_events_with_confirmation,
        frozen_time,
    ):
        """Alert should trigger after 3 consecutive readings below threshold."""
        for _ in range(3):
            await tracker_with_confirmation.check(
                namespace=Namespace.PICO,
                sensor_name=1,
                value=20.0,  # Below threshold
                unit="%",
                threshold=30,
                threshold_type=ThresholdType.MIN,
                hysteresis=3,
                recording_time=frozen_time,
            )
        assert len(pico_events_with_confirmation) == 1
        assert pico_events_with_confirmation[0].value == 20.0

    @pytest.mark.asyncio
    async def test_counter_resets_on_normal_reading(
        self,
        tracker_with_confirmation,
        pico_events_with_confirmation,
        frozen_time,
    ):
        """Pending counter should reset when value returns to normal."""
        # Two readings below threshold
        for _ in range(2):
            await tracker_with_confirmation.check(
                namespace=Namespace.PICO,
                sensor_name=1,
                value=20.0,
                unit="%",
                threshold=30,
                threshold_type=ThresholdType.MIN,
                hysteresis=3,
                recording_time=frozen_time,
            )
        assert len(pico_events_with_confirmation) == 0

        # Normal reading resets counter
        await tracker_with_confirmation.check(
            namespace=Namespace.PICO,
            sensor_name=1,
            value=50.0,  # Above threshold
            unit="%",
            threshold=30,
            threshold_type=ThresholdType.MIN,
            hysteresis=3,
            recording_time=frozen_time,
        )

        # Two more readings below threshold (not 3 total)
        for _ in range(2):
            await tracker_with_confirmation.check(
                namespace=Namespace.PICO,
                sensor_name=1,
                value=20.0,
                unit="%",
                threshold=30,
                threshold_type=ThresholdType.MIN,
                hysteresis=3,
                recording_time=frozen_time,
            )
        # Still no alert because counter was reset
        assert len(pico_events_with_confirmation) == 0
