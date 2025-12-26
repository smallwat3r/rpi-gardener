"""Tests for the DHT22 audit and event service."""

from rpi.dht.audit import audit_reading
from rpi.dht.models import Measure, Reading, State, Unit
from rpi.lib.alerts import AlertState, Namespace, get_alert_tracker


class TestAuditReading:
    """Tests for audit_reading function."""

    def test_normal_reading_no_event(self, dht_audit_events, sample_reading):
        """Normal reading within thresholds should not trigger events."""
        audit_reading(sample_reading)

        assert len(dht_audit_events) == 0
        assert sample_reading.temperature.state == State.OK
        assert sample_reading.humidity.state == State.OK

    def test_high_temperature_triggers_event(
        self, dht_audit_events, frozen_time
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

        audit_reading(reading)

        assert reading.temperature.state == State.IN_ALERT
        assert len(dht_audit_events) == 1
        event = dht_audit_events[0]
        assert event.sensor_name == "temperature"
        assert event.value == 80.0
        assert event.namespace == Namespace.DHT

    def test_low_temperature_triggers_event(
        self, dht_audit_events, frozen_time
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

        audit_reading(reading)

        assert reading.temperature.state == State.IN_ALERT
        assert len(dht_audit_events) == 1
        assert dht_audit_events[0].sensor_name == "temperature"

    def test_high_humidity_triggers_event(self, dht_audit_events, frozen_time):
        """Humidity above max should trigger an event."""
        reading = Reading(
            temperature=Measure(22.0, Unit.CELSIUS),
            humidity=Measure(
                99.0, Unit.PERCENT
            ),  # Very high, definitely over threshold
            recording_time=frozen_time,
        )

        audit_reading(reading)

        assert reading.humidity.state == State.IN_ALERT
        assert len(dht_audit_events) == 1
        assert dht_audit_events[0].sensor_name == "humidity"

    def test_low_humidity_triggers_event(self, dht_audit_events, frozen_time):
        """Humidity below min should trigger an event."""
        reading = Reading(
            temperature=Measure(22.0, Unit.CELSIUS),
            humidity=Measure(
                5.0, Unit.PERCENT
            ),  # Very low, definitely under threshold
            recording_time=frozen_time,
        )

        audit_reading(reading)

        assert reading.humidity.state == State.IN_ALERT
        assert len(dht_audit_events) == 1
        assert dht_audit_events[0].sensor_name == "humidity"

    def test_no_duplicate_events(self, dht_audit_events, frozen_time):
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

        audit_reading(reading1)
        initial_count = len(dht_audit_events)
        assert initial_count == 1  # First alert triggers

        audit_reading(reading2)

        # No new temperature event should be triggered (still in alert state)
        assert len(dht_audit_events) == initial_count

    def test_new_event_after_recovery(self, dht_audit_events, frozen_time):
        """New alert after recovery should trigger a new event."""
        # Initial alert
        reading1 = Reading(
            temperature=Measure(80.0, Unit.CELSIUS),  # Definitely triggers
            humidity=Measure(
                55.0, Unit.PERCENT
            ),  # Safe value within thresholds
            recording_time=frozen_time,
        )
        audit_reading(reading1)
        assert len(dht_audit_events) == 1

        # Recovery - use very safe middle value
        reading2 = Reading(
            temperature=Measure(20.0, Unit.CELSIUS),
            humidity=Measure(
                55.0, Unit.PERCENT
            ),  # Safe value within thresholds
            recording_time=frozen_time,
        )
        audit_reading(reading2)
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
        audit_reading(reading3)

        # New temperature event should be triggered
        assert len(dht_audit_events) == 3
        assert dht_audit_events[2].sensor_name == "temperature"
        assert dht_audit_events[2].is_resolved is False

    def test_multiple_alerts_same_reading(self, dht_audit_events, frozen_time):
        """Both temperature and humidity alerts should trigger separate events."""
        reading = Reading(
            temperature=Measure(80.0, Unit.CELSIUS),  # Definitely triggers
            humidity=Measure(99.0, Unit.PERCENT),  # Definitely triggers
            recording_time=frozen_time,
        )

        audit_reading(reading)

        sensor_names = {e.sensor_name for e in dht_audit_events}
        assert "temperature" in sensor_names
        assert "humidity" in sensor_names

    def test_state_updated_on_reading(self, dht_audit_events, frozen_time):
        """Reading's measure states should be updated after audit."""
        reading = Reading(
            temperature=Measure(80.0, Unit.CELSIUS),  # Definitely triggers
            humidity=Measure(50.0, Unit.PERCENT),
            recording_time=frozen_time,
        )

        assert reading.temperature.state == State.OK
        audit_reading(reading)
        assert reading.temperature.state == State.IN_ALERT  # type: ignore[comparison-overlap]

    def test_alert_tracker_uses_dht_namespace(
        self, dht_audit_events, frozen_time
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

        audit_reading(reading)

        tracker = get_alert_tracker()
        assert (
            tracker.get_state(Namespace.DHT, "temperature")
            == AlertState.IN_ALERT
        )
        assert tracker.get_state(Namespace.DHT, "humidity") == AlertState.OK
