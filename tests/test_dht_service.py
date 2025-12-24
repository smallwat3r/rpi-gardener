"""Tests for the DHT22 audit and event service."""
from unittest.mock import patch

import pytest

from rpi.dht import service
from rpi.dht.models import Measure, Reading, State, Unit
from rpi.dht.service import audit_reading
from rpi.lib.alerts import AlertState


class TestAuditReading:
    """Tests for audit_reading function."""

    def setup_method(self):
        """Reset alert state and queue before each test."""
        service._alert_tracker.reset()
        # Clear the queue
        while not service._queue.empty():
            try:
                service._queue.get_nowait()
            except Exception:
                break

    def test_normal_reading_no_event(self, sample_reading):
        """Normal reading within thresholds should not queue events."""
        initial_queue_size = service._queue.qsize()

        audit_reading(sample_reading)

        assert service._queue.qsize() == initial_queue_size
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
        assert not service._queue.empty()
        event = service._queue.get_nowait()
        assert event.sensor_name == "temperature"
        assert event.value == 80.0

    def test_low_temperature_triggers_event(self, frozen_time):
        """Temperature below min should trigger an event."""
        reading = Reading(
            temperature=Measure(-10.0, Unit.CELSIUS),  # Very low, definitely under threshold
            humidity=Measure(50.0, Unit.PERCENT),
            recording_time=frozen_time,
        )

        audit_reading(reading)

        assert reading.temperature.state == State.IN_ALERT
        event = service._queue.get_nowait()
        assert event.sensor_name == "temperature"

    def test_high_humidity_triggers_event(self, frozen_time):
        """Humidity above max should trigger an event."""
        reading = Reading(
            temperature=Measure(22.0, Unit.CELSIUS),
            humidity=Measure(99.0, Unit.PERCENT),  # Very high, definitely over threshold
            recording_time=frozen_time,
        )

        audit_reading(reading)

        assert reading.humidity.state == State.IN_ALERT
        event = service._queue.get_nowait()
        assert event.sensor_name == "humidity"

    def test_low_humidity_triggers_event(self, frozen_time):
        """Humidity below min should trigger an event."""
        reading = Reading(
            temperature=Measure(22.0, Unit.CELSIUS),
            humidity=Measure(5.0, Unit.PERCENT),  # Very low, definitely under threshold
            recording_time=frozen_time,
        )

        audit_reading(reading)

        assert reading.humidity.state == State.IN_ALERT
        event = service._queue.get_nowait()
        assert event.sensor_name == "humidity"

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
        while not service._queue.empty():
            event = service._queue.get_nowait()
            if event.sensor_name == "temperature":
                initial_temp_events += 1

        audit_reading(reading2)

        # No new temperature event should be queued (still in alert state)
        temp_events = 0
        while not service._queue.empty():
            event = service._queue.get_nowait()
            if event.sensor_name == "temperature":
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
        while not service._queue.empty():
            service._queue.get_nowait()

        # Recovery - use very safe middle value
        reading2 = Reading(
            temperature=Measure(20.0, Unit.CELSIUS),
            humidity=Measure(50.0, Unit.PERCENT),
            recording_time=frozen_time,
        )
        audit_reading(reading2)
        # Clear any humidity alerts
        while not service._queue.empty():
            service._queue.get_nowait()

        # New alert
        reading3 = Reading(
            temperature=Measure(80.0, Unit.CELSIUS),  # Definitely triggers again
            humidity=Measure(50.0, Unit.PERCENT),
            recording_time=frozen_time,
        )
        audit_reading(reading3)

        # New temperature event should be queued
        temp_events = []
        while not service._queue.empty():
            event = service._queue.get_nowait()
            if event.sensor_name == "temperature":
                temp_events.append(event)
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
        while not service._queue.empty():
            events.append(service._queue.get_nowait())
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
