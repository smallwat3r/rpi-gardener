"""Alert state tracking for sensor threshold violations.

Provides a unified AlertTracker singleton that tracks per-sensor alert states
across different namespaces (DHT, Pico) and triggers callbacks only on state
transitions (to prevent notification spam).

Uses hysteresis to prevent flapping when values oscillate around thresholds.

Thread-safe: Uses locks to protect shared state when accessed from multiple
polling services or async contexts.
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto

from rpi.lib.config import PlantIdValue, ThresholdType, Unit
from rpi.lib.eventbus import EventPublisher
from rpi.logging import get_logger

logger = get_logger("lib.alerts")


class AlertState(Enum):
    """Possible alert states for a sensor."""

    OK = auto()
    IN_ALERT = auto()


type SensorName = str | PlantIdValue
type AlertKey = tuple[Namespace, SensorName, ThresholdType]


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
    unit: Unit
    threshold: float | None  # None for resolution events
    recording_time: datetime
    is_resolved: bool = False


type AlertCallback = Callable[[AlertEvent], None]


class AlertTracker:
    """Tracks alert states per sensor/threshold and triggers callbacks on transitions.

    This prevents notification spam by only calling the callback when a sensor
    transitions between states (not on every reading).

    Uses hysteresis to prevent flapping when values oscillate around thresholds.
    Supports multiple namespaces (DHT, Pico) to keep sensor states organized.

    Thread-safe: All state mutations are protected by a lock.
    """

    def __init__(self) -> None:
        """Initialize the tracker with empty state."""
        self._lock = threading.Lock()
        self._states: dict[AlertKey, AlertState] = {}
        self._callbacks: dict[Namespace, AlertCallback] = {}

    def register_callback(
        self, namespace: Namespace, callback: AlertCallback
    ) -> None:
        """Register a callback for a specific namespace.

        Args:
            namespace: The namespace to register for.
            callback: Function called when a sensor transitions state.
        """
        with self._lock:
            self._callbacks[namespace] = callback
        logger.debug(
            "Registered alert callback for namespace %s", namespace.value
        )

    def _make_key(
        self,
        namespace: Namespace,
        sensor_name: SensorName,
        threshold_type: ThresholdType,
    ) -> AlertKey:
        """Create a unique key for a sensor threshold in a namespace."""
        return (namespace, sensor_name, threshold_type)

    def check(
        self,
        namespace: Namespace,
        sensor_name: SensorName,
        value: float,
        unit: Unit,
        threshold: float,
        threshold_type: ThresholdType,
        hysteresis: float,
        recording_time: datetime,
    ) -> AlertState:
        """Check if sensor is in alert state and trigger callback on transition.

        Uses hysteresis to prevent flapping. Alert triggers when value crosses
        the threshold, but only clears when value recovers past threshold by
        the hysteresis amount.

        Args:
            namespace: The namespace this sensor belongs to.
            sensor_name: Identifier for the sensor being checked.
            value: Current sensor reading value.
            unit: Unit of measurement.
            threshold: The threshold value being checked against.
            threshold_type: Whether this is a MIN or MAX threshold.
            hysteresis: Recovery offset to prevent flapping.
            recording_time: When the reading was taken.

        Returns:
            The new alert state for this sensor.
        """
        key = self._make_key(namespace, sensor_name, threshold_type)

        # Determine state transition while holding the lock
        with self._lock:
            previous_state = self._states.get(key, AlertState.OK)

            # Determine if threshold is violated
            if threshold_type == ThresholdType.MIN:
                is_violated = value < threshold
                # Recovery requires value to rise above threshold + hysteresis
                has_recovered = value >= threshold + hysteresis
            else:  # MAX
                is_violated = value > threshold
                # Recovery requires value to drop below threshold - hysteresis
                has_recovered = value <= threshold - hysteresis

            # Apply state transition logic with hysteresis
            if previous_state == AlertState.OK:
                new_state = (
                    AlertState.IN_ALERT if is_violated else AlertState.OK
                )
            else:  # Currently IN_ALERT
                # Only clear if recovered past hysteresis band
                new_state = (
                    AlertState.OK if has_recovered else AlertState.IN_ALERT
                )

            self._states[key] = new_state
            callback = self._callbacks.get(namespace)

        # Call callback outside of lock to prevent deadlocks
        if (
            new_state == AlertState.IN_ALERT
            and previous_state != AlertState.IN_ALERT
        ):
            logger.info(
                "[%s] %s crossed threshold: %.1f%s (threshold: %.0f)",
                namespace.value,
                sensor_name,
                value,
                unit,
                threshold,
            )
            if callback:
                callback(
                    AlertEvent(
                        namespace=namespace,
                        sensor_name=sensor_name,
                        value=value,
                        unit=unit,
                        threshold=threshold,
                        recording_time=recording_time,
                        is_resolved=False,
                    )
                )

        elif (
            new_state == AlertState.OK
            and previous_state == AlertState.IN_ALERT
        ):
            logger.info(
                "[%s] %s returned to normal: %.1f%s",
                namespace.value,
                sensor_name,
                value,
                unit,
            )
            if callback:
                callback(
                    AlertEvent(
                        namespace=namespace,
                        sensor_name=sensor_name,
                        value=value,
                        unit=unit,
                        threshold=None,
                        recording_time=recording_time,
                        is_resolved=True,
                    )
                )

        return new_state

    def get_state(
        self,
        namespace: Namespace,
        sensor_name: SensorName,
        threshold_type: ThresholdType,
    ) -> AlertState:
        """Get current alert state for a sensor threshold."""
        key = self._make_key(namespace, sensor_name, threshold_type)
        with self._lock:
            return self._states.get(key, AlertState.OK)

    def is_any_alert(
        self, namespace: Namespace, sensor_name: SensorName
    ) -> bool:
        """Check if any threshold for this sensor is in alert state."""
        with self._lock:
            return any(
                state == AlertState.IN_ALERT
                for key, state in self._states.items()
                if key[0] == namespace and key[1] == sensor_name
            )

    def reset(
        self,
        namespace: Namespace | None = None,
        sensor_name: SensorName | None = None,
        threshold_type: ThresholdType | None = None,
    ) -> None:
        """Reset alert state for specific threshold, sensor, namespace, or all.

        Args:
            namespace: Specific namespace to reset, or None for all namespaces.
            sensor_name: Specific sensor to reset within the namespace.
            threshold_type: Specific threshold type to reset.
        """
        with self._lock:
            if namespace is None:
                self._states.clear()
            elif sensor_name is None:
                # Reset all sensors in this namespace
                keys_to_remove = [k for k in self._states if k[0] == namespace]
                for key in keys_to_remove:
                    del self._states[key]
            elif threshold_type is None:
                # Reset all thresholds for this sensor
                keys_to_remove = [
                    k
                    for k in self._states
                    if k[0] == namespace and k[1] == sensor_name
                ]
                for key in keys_to_remove:
                    del self._states[key]
            else:
                key = self._make_key(namespace, sensor_name, threshold_type)
                if key in self._states:
                    del self._states[key]


def create_alert_publisher(publisher: EventPublisher) -> AlertCallback:
    """Create an alert callback that publishes to the event bus.

    Args:
        publisher: The EventPublisher to use for publishing alerts.

    Returns:
        A callback function that can be registered with AlertTracker.
    """
    from rpi.lib.eventbus import AlertEventPayload, Topic

    def publish_alert(event: AlertEvent) -> None:
        payload = AlertEventPayload(
            namespace=event.namespace.value,
            sensor_name=event.sensor_name,
            value=event.value,
            unit=event.unit,
            threshold=event.threshold,
            recording_time=event.recording_time,
            is_resolved=event.is_resolved,
        )
        publisher.publish(Topic.ALERT, payload)

    return publish_alert
