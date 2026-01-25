"""Tests for the DHT22 audit and event service."""

import pytest

from rpi.dht.audit import audit_reading
from rpi.dht.models import Measure, Reading
from rpi.lib.alerts import AlertState, Namespace
from rpi.lib.config import ThresholdType, Unit


class TestAuditReading:
    """Tests for audit_reading function."""

    @pytest.mark.asyncio
    async def test_normal_reading_no_event(
        self, dht_audit_events, sample_reading, alert_tracker
    ):
        """Normal reading within thresholds should not trigger events."""
        await audit_reading(sample_reading, alert_tracker)

        assert len(dht_audit_events) == 0

    @pytest.mark.asyncio
    async def test_high_temperature_triggers_event(
        self, dht_audit_events, frozen_time, alert_tracker
    ):
        """Temperature above max should trigger an event."""
        reading = Reading(
            temperature=Measure(
                80.0, Unit.CELSIUS
            ),  # Very high, definitely over threshold
            humidity=Measure(
                55.0, Unit.PERCENT
            ),  # Safe value within thresholds
            recording_time=frozen_time,
        )

        await audit_reading(reading, alert_tracker)

        assert len(dht_audit_events) == 1
        event = dht_audit_events[0]
        assert event.sensor_name == "temperature"
        assert event.value == 80.0
        assert event.namespace == Namespace.DHT

    @pytest.mark.asyncio
    async def test_low_temperature_triggers_event(
        self, dht_audit_events, frozen_time, alert_tracker
    ):
        """Temperature below min should trigger an event."""
        reading = Reading(
            temperature=Measure(
                -10.0, Unit.CELSIUS
            ),  # Very low, definitely under threshold
            humidity=Measure(
                55.0, Unit.PERCENT
            ),  # Safe value within thresholds
            recording_time=frozen_time,
        )

        await audit_reading(reading, alert_tracker)

        assert len(dht_audit_events) == 1
        assert dht_audit_events[0].sensor_name == "temperature"

    @pytest.mark.asyncio
    async def test_high_humidity_triggers_event(
        self, dht_audit_events, frozen_time, alert_tracker
    ):
        """Humidity above max should trigger an event."""
        reading = Reading(
            temperature=Measure(22.0, Unit.CELSIUS),
            humidity=Measure(
                99.0, Unit.PERCENT
            ),  # Very high, definitely over threshold
            recording_time=frozen_time,
        )

        await audit_reading(reading, alert_tracker)

        assert len(dht_audit_events) == 1
        assert dht_audit_events[0].sensor_name == "humidity"

    @pytest.mark.asyncio
    async def test_low_humidity_triggers_event(
        self, dht_audit_events, frozen_time, alert_tracker
    ):
        """Humidity below min should trigger an event."""
        reading = Reading(
            temperature=Measure(22.0, Unit.CELSIUS),
            humidity=Measure(
                5.0, Unit.PERCENT
            ),  # Very low, definitely under threshold
            recording_time=frozen_time,
        )

        await audit_reading(reading, alert_tracker)

        assert len(dht_audit_events) == 1
        assert dht_audit_events[0].sensor_name == "humidity"

    @pytest.mark.asyncio
    async def test_no_duplicate_events(
        self, dht_audit_events, frozen_time, alert_tracker
    ):
        """Consecutive alerts should not trigger duplicate events."""
        reading1 = Reading(
            temperature=Measure(80.0, Unit.CELSIUS),  # Definitely triggers
            humidity=Measure(
                55.0, Unit.PERCENT
            ),  # Safe value within thresholds
            recording_time=frozen_time,
        )
        reading2 = Reading(
            temperature=Measure(81.0, Unit.CELSIUS),  # Still in alert
            humidity=Measure(
                55.0, Unit.PERCENT
            ),  # Safe value within thresholds
            recording_time=frozen_time,
        )

        await audit_reading(reading1, alert_tracker)
        initial_count = len(dht_audit_events)
        assert initial_count == 1  # First alert triggers

        await audit_reading(reading2, alert_tracker)

        # No new temperature event should be triggered (still in alert state)
        assert len(dht_audit_events) == initial_count

    @pytest.mark.asyncio
    async def test_new_event_after_recovery(
        self, dht_audit_events, frozen_time, alert_tracker
    ):
        """New alert after recovery should trigger a new event."""
        # Initial alert
        reading1 = Reading(
            temperature=Measure(80.0, Unit.CELSIUS),  # Definitely triggers
            humidity=Measure(
                55.0, Unit.PERCENT
            ),  # Safe value within thresholds
            recording_time=frozen_time,
        )
        await audit_reading(reading1, alert_tracker)
        assert len(dht_audit_events) == 1

        # Recovery - use very safe middle value
        reading2 = Reading(
            temperature=Measure(20.0, Unit.CELSIUS),
            humidity=Measure(
                55.0, Unit.PERCENT
            ),  # Safe value within thresholds
            recording_time=frozen_time,
        )
        await audit_reading(reading2, alert_tracker)
        # Recovery event (is_resolved=True)
        assert len(dht_audit_events) == 2
        assert dht_audit_events[1].is_resolved is True

        # New alert
        reading3 = Reading(
            temperature=Measure(
                80.0, Unit.CELSIUS
            ),  # Definitely triggers again
            humidity=Measure(
                55.0, Unit.PERCENT
            ),  # Safe value within thresholds
            recording_time=frozen_time,
        )
        await audit_reading(reading3, alert_tracker)

        # New temperature event should be triggered
        assert len(dht_audit_events) == 3
        assert dht_audit_events[2].sensor_name == "temperature"
        assert dht_audit_events[2].is_resolved is False

    @pytest.mark.asyncio
    async def test_multiple_alerts_same_reading(
        self, dht_audit_events, frozen_time, alert_tracker
    ):
        """Both temperature and humidity alerts should trigger separate events."""
        reading = Reading(
            temperature=Measure(80.0, Unit.CELSIUS),  # Definitely triggers
            humidity=Measure(99.0, Unit.PERCENT),  # Definitely triggers
            recording_time=frozen_time,
        )

        await audit_reading(reading, alert_tracker)

        sensor_names = {e.sensor_name for e in dht_audit_events}
        assert "temperature" in sensor_names
        assert "humidity" in sensor_names

    @pytest.mark.asyncio
    async def test_alert_tracker_uses_dht_namespace(
        self, dht_audit_events, frozen_time, alert_tracker
    ):
        """Alert tracker should use DHT namespace for temperature/humidity."""
        # Temperature is high (alert), humidity is within normal range
        reading = Reading(
            temperature=Measure(
                80.0, Unit.CELSIUS
            ),  # Above max, triggers alert
            humidity=Measure(
                55.0, Unit.PERCENT
            ),  # Between min (40) and max (65), no alert
            recording_time=frozen_time,
        )

        await audit_reading(reading, alert_tracker)

        # Temperature is above max threshold
        assert (
            await alert_tracker.get_state(
                Namespace.DHT, "temperature", ThresholdType.MAX
            )
            == AlertState.IN_ALERT
        )
        # Humidity is within normal range (neither MIN nor MAX violated)
        assert (
            await alert_tracker.get_state(
                Namespace.DHT, "humidity", ThresholdType.MIN
            )
            == AlertState.OK
        )
        assert (
            await alert_tracker.get_state(
                Namespace.DHT, "humidity", ThresholdType.MAX
            )
            == AlertState.OK
        )

    @pytest.mark.asyncio
    async def test_hysteresis_prevents_flapping(
        self, dht_audit_events, frozen_time, alert_tracker
    ):
        """Alert should not clear until value recovers past hysteresis band.

        With max_temperature=25 and hysteresis=1:
        - Alert triggers at temp > 25
        - Alert clears at temp <= 24 (25 - 1)
        - Value between 24-25 should stay IN_ALERT
        """
        # Use humidity 60% which should be within any reasonable threshold range
        safe_humidity = 60.0

        # Trigger alert with high temperature
        reading1 = Reading(
            temperature=Measure(26.0, Unit.CELSIUS),  # Above 25, triggers
            humidity=Measure(safe_humidity, Unit.PERCENT),
            recording_time=frozen_time,
        )
        await audit_reading(reading1, alert_tracker)
        assert len(dht_audit_events) == 1

        # Drop to 24.5 - within hysteresis band (24-25), should stay IN_ALERT
        reading2 = Reading(
            temperature=Measure(24.5, Unit.CELSIUS),  # Below 25 but above 24
            humidity=Measure(safe_humidity, Unit.PERCENT),
            recording_time=frozen_time,
        )
        await audit_reading(reading2, alert_tracker)
        # No new events (still in alert, no recovery)
        assert len(dht_audit_events) == 1

        # Drop to 23 - below hysteresis band, should recover
        reading3 = Reading(
            temperature=Measure(23.0, Unit.CELSIUS),  # Below 24, recovers
            humidity=Measure(safe_humidity, Unit.PERCENT),
            recording_time=frozen_time,
        )
        await audit_reading(reading3, alert_tracker)
        # Recovery event triggered
        assert len(dht_audit_events) == 2
        assert dht_audit_events[1].is_resolved is True

    @pytest.mark.asyncio
    async def test_hysteresis_min_threshold(
        self, dht_audit_events, frozen_time, alert_tracker
    ):
        """Hysteresis also works for MIN thresholds.

        With min_temperature=18 and hysteresis=1:
        - Alert triggers at temp < 18
        - Alert clears at temp >= 19 (18 + 1)
        """
        # Use humidity 60% which should be within any reasonable threshold range
        safe_humidity = 60.0

        # Trigger alert with low temperature
        reading1 = Reading(
            temperature=Measure(17.0, Unit.CELSIUS),  # Below 18, triggers
            humidity=Measure(safe_humidity, Unit.PERCENT),
            recording_time=frozen_time,
        )
        await audit_reading(reading1, alert_tracker)
        assert len(dht_audit_events) == 1

        # Rise to 18.5 - within hysteresis band (18-19), should stay IN_ALERT
        reading2 = Reading(
            temperature=Measure(18.5, Unit.CELSIUS),  # Above 18 but below 19
            humidity=Measure(safe_humidity, Unit.PERCENT),
            recording_time=frozen_time,
        )
        await audit_reading(reading2, alert_tracker)
        assert len(dht_audit_events) == 1

        # Rise to 20 - above hysteresis band, should recover
        reading3 = Reading(
            temperature=Measure(20.0, Unit.CELSIUS),  # Above 19, recovers
            humidity=Measure(safe_humidity, Unit.PERCENT),
            recording_time=frozen_time,
        )
        await audit_reading(reading3, alert_tracker)
        assert len(dht_audit_events) == 2
        assert dht_audit_events[1].is_resolved is True
