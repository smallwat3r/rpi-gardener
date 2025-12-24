"""Alert state tracking for sensor threshold violations.

Provides a unified AlertTracker singleton that tracks per-sensor alert states
across different namespaces (DHT, Pico) and triggers callbacks only on state
transitions (to prevent notification spam).
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from typing import Callable, TypeAlias

from rpi.logging import get_logger

logger = get_logger("lib.alerts")


class AlertState(Enum):
    """Possible alert states for a sensor."""
    OK = auto()
    IN_ALERT = auto()


class Namespace(Enum):
    """Alert namespace identifiers."""
    DHT = "dht"
    PICO = "pico"


@dataclass
class ThresholdViolation:
    """Details about a threshold violation."""
    namespace: Namespace
    sensor_name: str | int
    value: float
    unit: str
    threshold: float
    recording_time: datetime


# Type alias for alert callbacks
AlertCallback: TypeAlias = Callable[[ThresholdViolation], None]


class AlertTracker:
    """Tracks alert states per sensor and triggers callbacks on state transitions.

    This prevents notification spam by only calling the callback when a sensor
    transitions from OK to IN_ALERT (not on every reading that exceeds threshold).

    Supports multiple namespaces (DHT, Pico) to keep sensor states organized.
    """

    def __init__(self) -> None:
        """Initialize the tracker with empty state."""
        self._states: dict[tuple[Namespace, str | int], AlertState] = {}
        self._callbacks: dict[Namespace, AlertCallback] = {}

    def register_callback(self, namespace: Namespace, callback: AlertCallback) -> None:
        """Register a callback for a specific namespace.

        Args:
            namespace: The namespace to register for.
            callback: Function called when a sensor transitions to alert state.
        """
        self._callbacks[namespace] = callback
        logger.debug("Registered alert callback for namespace %s", namespace.value)

    def _make_key(self, namespace: Namespace, sensor_name: str | int) -> tuple[Namespace, str | int]:
        """Create a unique key for a sensor in a namespace."""
        return (namespace, sensor_name)

    def check(
        self,
        namespace: Namespace,
        sensor_name: str | int,
        value: float,
        unit: str,
        threshold: float,
        is_violated: bool,
        recording_time: datetime,
    ) -> AlertState:
        """Check if sensor is in alert state and trigger callback on transition.

        Args:
            namespace: The namespace this sensor belongs to.
            sensor_name: Identifier for the sensor being checked.
            value: Current sensor reading value.
            unit: Unit of measurement (e.g., "c", "%").
            threshold: The threshold value that was checked against.
            is_violated: True if the value violates the threshold.
            recording_time: When the reading was taken.

        Returns:
            The new alert state for this sensor.
        """
        key = self._make_key(namespace, sensor_name)
        previous_state = self._states.get(key, AlertState.OK)
        new_state = AlertState.IN_ALERT if is_violated else AlertState.OK

        if new_state == AlertState.IN_ALERT and previous_state != AlertState.IN_ALERT:
            logger.info(
                "[%s] %s crossed threshold: %.1f%s (threshold: %.0f)",
                namespace.value, sensor_name, value, unit, threshold
            )

            callback = self._callbacks.get(namespace)
            if callback:
                violation = ThresholdViolation(
                    namespace=namespace,
                    sensor_name=sensor_name,
                    value=value,
                    unit=unit,
                    threshold=threshold,
                    recording_time=recording_time,
                )
                callback(violation)

        self._states[key] = new_state
        return new_state

    def get_state(self, namespace: Namespace, sensor_name: str | int) -> AlertState:
        """Get current alert state for a sensor."""
        key = self._make_key(namespace, sensor_name)
        return self._states.get(key, AlertState.OK)

    def reset(
        self,
        namespace: Namespace | None = None,
        sensor_name: str | int | None = None,
    ) -> None:
        """Reset alert state for one sensor, one namespace, or all.

        Args:
            namespace: Specific namespace to reset, or None for all namespaces.
            sensor_name: Specific sensor to reset within the namespace.
        """
        if namespace is None:
            self._states.clear()
        elif sensor_name is None:
            # Reset all sensors in this namespace
            keys_to_remove = [k for k in self._states if k[0] == namespace]
            for key in keys_to_remove:
                del self._states[key]
        else:
            key = self._make_key(namespace, sensor_name)
            if key in self._states:
                del self._states[key]

    def get_all_states(self, namespace: Namespace | None = None) -> dict[tuple[Namespace, str | int], AlertState]:
        """Get all current alert states, optionally filtered by namespace."""
        if namespace is None:
            return dict(self._states)
        return {k: v for k, v in self._states.items() if k[0] == namespace}


# Global singleton instance
_alert_tracker: AlertTracker | None = None


def get_alert_tracker() -> AlertTracker:
    """Get the global AlertTracker singleton."""
    global _alert_tracker
    if _alert_tracker is None:
        _alert_tracker = AlertTracker()
    return _alert_tracker


def reset_alert_tracker() -> None:
    """Reset the global AlertTracker (mainly for testing)."""
    global _alert_tracker
    if _alert_tracker is not None:
        _alert_tracker.reset()
    _alert_tracker = None
