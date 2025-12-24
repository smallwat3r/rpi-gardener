"""Alert state tracking for sensor threshold violations.

Provides a reusable AlertTracker class that tracks per-sensor alert states
and triggers callbacks only on state transitions (to prevent notification spam).
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from typing import Callable

from rpi.lib.notifications import Event
from rpi.logging import get_logger

logger = get_logger("lib.alerts")


class AlertState(Enum):
    """Possible alert states for a sensor."""
    OK = auto()
    IN_ALERT = auto()


@dataclass
class ThresholdViolation:
    """Details about a threshold violation."""
    sensor_name: str | int
    value: float
    unit: str
    threshold: float
    recording_time: datetime


class AlertTracker:
    """Tracks alert states per sensor and triggers callbacks on state transitions.

    This prevents notification spam by only calling the callback when a sensor
    transitions from OK to IN_ALERT (not on every reading that exceeds threshold).
    """

    def __init__(self, on_alert: Callable[[Event], None]) -> None:
        """Initialize tracker with a callback for alert events.

        Args:
            on_alert: Callback invoked when a sensor transitions to alert state.
        """
        self._states: dict[str | int, AlertState] = {}
        self._on_alert = on_alert

    def check(
        self,
        sensor_name: str | int,
        value: float,
        unit: str,
        threshold: float,
        is_violated: bool,
        recording_time: datetime,
    ) -> AlertState:
        """Check if sensor is in alert state and trigger callback on transition.

        Args:
            sensor_name: Identifier for the sensor being checked.
            value: Current sensor reading value.
            unit: Unit of measurement (e.g., "c", "%").
            threshold: The threshold value that was checked against.
            is_violated: True if the value violates the threshold.
            recording_time: When the reading was taken.

        Returns:
            The new alert state for this sensor.
        """
        previous_state = self._states.get(sensor_name, AlertState.OK)
        new_state = AlertState.IN_ALERT if is_violated else AlertState.OK

        if new_state == AlertState.IN_ALERT and previous_state != AlertState.IN_ALERT:
            logger.info(
                "%s crossed threshold: %.1f%s (threshold: %.0f)",
                sensor_name, value, unit, threshold
            )
            self._on_alert(Event(
                sensor_name=sensor_name,
                value=value,
                unit=unit,
                threshold=threshold,
                recording_time=recording_time,
            ))

        self._states[sensor_name] = new_state
        return new_state

    def get_state(self, sensor_name: str | int) -> AlertState:
        """Get current alert state for a sensor."""
        return self._states.get(sensor_name, AlertState.OK)

    def reset(self, sensor_name: str | int | None = None) -> None:
        """Reset alert state for one or all sensors.

        Args:
            sensor_name: Specific sensor to reset, or None to reset all.
        """
        if sensor_name is None:
            self._states.clear()
        elif sensor_name in self._states:
            del self._states[sensor_name]
