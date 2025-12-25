"""Alert state tracking for sensor threshold violations.

Provides a unified AlertTracker singleton that tracks per-sensor alert states
across different namespaces (DHT, Pico) and triggers callbacks only on state
transitions (to prevent notification spam).
"""
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto

from rpi.lib.config import PlantIdValue
from rpi.logging import get_logger

logger = get_logger("lib.alerts")


class AlertState(Enum):
    """Possible alert states for a sensor."""
    OK = auto()
    IN_ALERT = auto()


type SensorName = str | PlantIdValue


class Namespace(Enum):
    """Alert namespace identifiers."""
    DHT = "dht"
    PICO = "pico"


@dataclass(slots=True)
class AlertEvent:
    """Details about an alert state transition."""
    namespace: Namespace
    sensor_name: SensorName
    value: float
    unit: str
    threshold: float | None  # None for resolution events
    recording_time: datetime
    is_resolved: bool = False


type AlertCallback = Callable[[AlertEvent], None]


class AlertTracker:
    """Tracks alert states per sensor and triggers callbacks on state transitions.

    This prevents notification spam by only calling the callback when a sensor
    transitions between states (not on every reading).

    Supports multiple namespaces (DHT, Pico) to keep sensor states organized.
    """

    def __init__(self) -> None:
        """Initialize the tracker with empty state."""
        self._states: dict[tuple[Namespace, SensorName], AlertState] = {}
        self._callbacks: dict[Namespace, AlertCallback] = {}

    def register_callback(self, namespace: Namespace, callback: AlertCallback) -> None:
        """Register a callback for a specific namespace.

        Args:
            namespace: The namespace to register for.
            callback: Function called when a sensor transitions state.
        """
        self._callbacks[namespace] = callback
        logger.debug("Registered alert callback for namespace %s", namespace.value)

    def _make_key(self, namespace: Namespace, sensor_name: SensorName) -> tuple[Namespace, SensorName]:
        """Create a unique key for a sensor in a namespace."""
        return (namespace, sensor_name)

    def check(
        self,
        namespace: Namespace,
        sensor_name: SensorName,
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

        callback = self._callbacks.get(namespace)

        if new_state == AlertState.IN_ALERT and previous_state != AlertState.IN_ALERT:
            logger.info(
                "[%s] %s crossed threshold: %.1f%s (threshold: %.0f)",
                namespace.value, sensor_name, value, unit, threshold
            )
            if callback:
                callback(AlertEvent(
                    namespace=namespace,
                    sensor_name=sensor_name,
                    value=value,
                    unit=unit,
                    threshold=threshold,
                    recording_time=recording_time,
                    is_resolved=False,
                ))

        elif new_state == AlertState.OK and previous_state == AlertState.IN_ALERT:
            logger.info(
                "[%s] %s returned to normal: %.1f%s",
                namespace.value, sensor_name, value, unit
            )
            if callback:
                callback(AlertEvent(
                    namespace=namespace,
                    sensor_name=sensor_name,
                    value=value,
                    unit=unit,
                    threshold=None,
                    recording_time=recording_time,
                    is_resolved=True,
                ))

        self._states[key] = new_state
        return new_state

    def get_state(self, namespace: Namespace, sensor_name: SensorName) -> AlertState:
        """Get current alert state for a sensor."""
        key = self._make_key(namespace, sensor_name)
        return self._states.get(key, AlertState.OK)

    def reset(
        self,
        namespace: Namespace | None = None,
        sensor_name: SensorName | None = None,
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
