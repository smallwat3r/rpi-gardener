"""Tests for the DHT22 audit and event service."""
import pytest

from rpi.dht import audit
from rpi.dht.models import Measure, Reading, State, Unit
from rpi.dht.audit import _enqueue_event, audit_reading
from rpi.lib.alerts import (AlertState, Namespace, get_alert_tracker,
                            reset_alert_tracker)


class TestAuditReading:
    """Tests for audit_reading function."""

    def setup_method(self):
        """Reset alert state and queue before each test."""
        # Reset the global alert tracker
        reset_alert_tracker()
        # Register the DHT callback
        tracker = get_alert_tracker()
        tracker.register_callback(Namespace.DHT, _enqueue_event)
        # Clear the queue
        while not audit._queue.empty():
            try:
                audit._queue.get_nowait()
            except Exception:
                break

    def test_normal_reading_no_event(self, sample_reading):
        """Normal reading within thresholds should not queue events."""
        initial_queue_size = audit._queue.qsize()

        audit_reading(sample_reading)

        assert audit._queue.qsize() == initial_queue_size
        assert sample_reading.temperature.state == State.OK
        assert sample_reading.humidity.state == State.OK

    def test_high_temperature_triggers_event(self, frozen_time):
        """Temperature above max should trigger an event."""
        reading = Reading(
            temperature=Measure(80.0, Unit.CELSIUS),  # Very high, definitely over threshold
            humidity=Measure(50.0, Unit.PERCENT),
            recording_time=frozen_time,
        )

        audit_reading(reading)

        assert reading.temperature.state == State.IN_ALERT
        # Check temperature event was queued
        assert not audit._queue.empty()
        violation = audit._queue.get_nowait()
        assert violation.sensor_name == "temperature"
        assert violation.value == 80.0
        assert violation.namespace == Namespace.DHT

    def test_low_temperature_triggers_event(self, frozen_time):
        """Temperature below min should trigger an event."""
        reading = Reading(
            temperature=Measure(-10.0, Unit.CELSIUS),  # Very low, definitely under threshold
            humidity=Measure(50.0, Unit.PERCENT),
            recording_time=frozen_time,
        )

        audit_reading(reading)

        assert reading.temperature.state == State.IN_ALERT
        violation = audit._queue.get_nowait()
        assert violation.sensor_name == "temperature"

    def test_high_humidity_triggers_event(self, frozen_time):
        """Humidity above max should trigger an event."""
        reading = Reading(
            temperature=Measure(22.0, Unit.CELSIUS),
            humidity=Measure(99.0, Unit.PERCENT),  # Very high, definitely over threshold
            recording_time=frozen_time,
        )

        audit_reading(reading)

        assert reading.humidity.state == State.IN_ALERT
        violation = audit._queue.get_nowait()
        assert violation.sensor_name == "humidity"

    def test_low_humidity_triggers_event(self, frozen_time):
        """Humidity below min should trigger an event."""
        reading = Reading(
            temperature=Measure(22.0, Unit.CELSIUS),
            humidity=Measure(5.0, Unit.PERCENT),  # Very low, definitely under threshold
            recording_time=frozen_time,
        )

        audit_reading(reading)

        assert reading.humidity.state == State.IN_ALERT
        violation = audit._queue.get_nowait()
        assert violation.sensor_name == "humidity"

    def test_no_duplicate_events(self, frozen_time):
        """Consecutive alerts should not queue duplicate events."""
        reading1 = Reading(
            temperature=Measure(80.0, Unit.CELSIUS),  # Definitely triggers
            humidity=Measure(50.0, Unit.PERCENT),
            recording_time=frozen_time,
        )
        reading2 = Reading(
            temperature=Measure(81.0, Unit.CELSIUS),  # Still in alert
            humidity=Measure(50.0, Unit.PERCENT),
            recording_time=frozen_time,
        )

        audit_reading(reading1)
        initial_temp_events = 0
        while not audit._queue.empty():
            violation = audit._queue.get_nowait()
            if violation.sensor_name == "temperature":
                initial_temp_events += 1

        audit_reading(reading2)

        # No new temperature event should be queued (still in alert state)
        temp_events = 0
        while not audit._queue.empty():
            violation = audit._queue.get_nowait()
            if violation.sensor_name == "temperature":
                temp_events += 1
        assert temp_events == 0

    def test_new_event_after_recovery(self, frozen_time):
        """New alert after recovery should queue a new event."""
        # Initial alert
        reading1 = Reading(
            temperature=Measure(80.0, Unit.CELSIUS),  # Definitely triggers
            humidity=Measure(50.0, Unit.PERCENT),
            recording_time=frozen_time,
        )
        audit_reading(reading1)
        # Clear queue
        while not audit._queue.empty():
            audit._queue.get_nowait()

        # Recovery - use very safe middle value
        reading2 = Reading(
            temperature=Measure(20.0, Unit.CELSIUS),
            humidity=Measure(50.0, Unit.PERCENT),
            recording_time=frozen_time,
        )
        audit_reading(reading2)
        # Clear any humidity alerts
        while not audit._queue.empty():
            audit._queue.get_nowait()

        # New alert
        reading3 = Reading(
            temperature=Measure(80.0, Unit.CELSIUS),  # Definitely triggers again
            humidity=Measure(50.0, Unit.PERCENT),
            recording_time=frozen_time,
        )
        audit_reading(reading3)

        # New temperature event should be queued
        temp_events = []
        while not audit._queue.empty():
            violation = audit._queue.get_nowait()
            if violation.sensor_name == "temperature":
                temp_events.append(violation)
        assert len(temp_events) == 1

    def test_multiple_alerts_same_reading(self, frozen_time):
        """Both temperature and humidity alerts should queue separate events."""
        reading = Reading(
            temperature=Measure(80.0, Unit.CELSIUS),  # Definitely triggers
            humidity=Measure(99.0, Unit.PERCENT),  # Definitely triggers
            recording_time=frozen_time,
        )

        audit_reading(reading)

        events = []
        while not audit._queue.empty():
            events.append(audit._queue.get_nowait())
        sensor_names = {e.sensor_name for e in events}
        assert "temperature" in sensor_names
        assert "humidity" in sensor_names

    def test_state_updated_on_reading(self, frozen_time):
        """Reading's measure states should be updated after audit."""
        reading = Reading(
            temperature=Measure(80.0, Unit.CELSIUS),  # Definitely triggers
            humidity=Measure(50.0, Unit.PERCENT),
            recording_time=frozen_time,
        )

        assert reading.temperature.state == State.OK
        audit_reading(reading)
        assert reading.temperature.state == State.IN_ALERT

    def test_alert_tracker_uses_dht_namespace(self, frozen_time):
        """Alert tracker should use DHT namespace for temperature/humidity."""
        # Temperature is high (alert), humidity is within normal range
        reading = Reading(
            temperature=Measure(80.0, Unit.CELSIUS),  # Above max, triggers alert
            humidity=Measure(55.0, Unit.PERCENT),  # Between min (40) and max (65), no alert
            recording_time=frozen_time,
        )

        audit_reading(reading)

        tracker = get_alert_tracker()
        assert tracker.get_state(Namespace.DHT, "temperature") == AlertState.IN_ALERT
        assert tracker.get_state(Namespace.DHT, "humidity") == AlertState.OK
