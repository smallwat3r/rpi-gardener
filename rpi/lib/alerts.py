"""Alert state tracking for sensor threshold violations.

Provides a unified AlertTracker singleton that tracks per-sensor alert states
across different namespaces (DHT, Pico) and triggers callbacks only on state
transitions (to prevent notification spam).

Uses hysteresis to prevent flapping when values oscillate around thresholds.
Uses confirmation window to require consecutive readings before state change.

Async-safe: Uses asyncio.Lock to protect shared state when accessed from
multiple async contexts without blocking the event loop.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto

from rpi.lib.config import PlantIdValue, ThresholdType, Unit, get_settings
from rpi.lib.eventbus import EventPublisher
from rpi.logging import get_logger

logger = get_logger("lib.alerts")


class AlertState(Enum):
    """Possible alert states for a sensor."""

    OK = auto()
    IN_ALERT = auto()


type _SensorName = str | PlantIdValue
type _AlertKey = tuple[Namespace, _SensorName, ThresholdType]


class Namespace(Enum):
    """Alert namespace identifiers."""

    DHT = "dht"
    PICO = "pico"


@dataclass(slots=True)
class AlertEvent:
    """Details about an alert state transition."""

    namespace: Namespace
    sensor_name: _SensorName
    value: float
    unit: Unit
    threshold: float | None  # None for resolution events
    recording_time: datetime
    is_resolved: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "AlertEvent":
        """Parse an AlertEvent from event bus data."""
        return cls(
            namespace=Namespace(str(data["namespace"])),
            sensor_name=data["sensor_name"],  # type: ignore[arg-type]
            value=float(data["value"]),  # type: ignore[arg-type]
            unit=str(data["unit"]),  # type: ignore[arg-type]
            threshold=float(data["threshold"]) if data["threshold"] else None,  # type: ignore[arg-type]
            recording_time=datetime.strptime(
                str(data["recording_time"]), "%Y-%m-%d %H:%M:%S"
            ),
            is_resolved=bool(data["is_resolved"]),
        )


@dataclass(frozen=True, slots=True)
class _ThresholdCheck:
    """Parameters for a threshold check."""

    namespace: Namespace
    sensor_name: _SensorName
    value: float
    unit: Unit
    threshold: float
    threshold_type: ThresholdType
    hysteresis: float
    recording_time: datetime

    def is_violated(self) -> bool:
        """Check if the threshold is currently violated."""
        if self.threshold_type == ThresholdType.MIN:
            return self.value < self.threshold
        return self.value > self.threshold

    def has_recovered(self) -> bool:
        """Check if value has recovered past the hysteresis band."""
        if self.threshold_type == ThresholdType.MIN:
            return self.value >= self.threshold + self.hysteresis
        return self.value <= self.threshold - self.hysteresis


type AlertCallback = Callable[[AlertEvent], None]


class AlertTracker:
    """Tracks alert states per sensor/threshold and triggers callbacks on transitions.

    This prevents notification spam by only calling the callback when a sensor
    transitions between states (not on every reading).

    Uses hysteresis to prevent flapping when values oscillate around thresholds.
    Uses confirmation window to require N consecutive readings in a new state
    before actually transitioning, preventing transient sensor errors from
    triggering false alerts.

    Supports multiple namespaces (DHT, Pico) to keep sensor states organized.

    Async-safe: All state mutations are protected by an asyncio.Lock.
    """

    def __init__(self, confirmation_count: int | None = None) -> None:
        """Initialize the tracker with empty state.

        Args:
            confirmation_count: Number of consecutive readings required to
                confirm a state change. If None, uses config default.
        """
        self._lock: asyncio.Lock | None = None
        self._states: dict[_AlertKey, AlertState] = {}
        self._callbacks: dict[Namespace, AlertCallback] = {}
        self._pending_counts: dict[_AlertKey, int] = {}
        # Track alert count per (namespace, sensor) for O(1) is_any_alert lookup
        self._alert_counts: dict[tuple[Namespace, _SensorName], int] = {}
        self._confirmation_count = (
            confirmation_count
            if confirmation_count is not None
            else get_settings().alerts.confirmation_count
        )

    def _get_lock(self) -> asyncio.Lock:
        """Get or create the async lock (lazy init for event loop compatibility)."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def register_callback(
        self, namespace: Namespace, callback: AlertCallback
    ) -> None:
        """Register a callback for a specific namespace.

        Args:
            namespace: The namespace to register for.
            callback: Function called when a sensor transitions state.
        """
        async with self._get_lock():
            self._callbacks[namespace] = callback
        logger.debug(
            "Registered alert callback for namespace %s", namespace.value
        )

    def _make_key(self, check: _ThresholdCheck) -> _AlertKey:
        """Create a unique key for a sensor threshold in a namespace."""
        return (check.namespace, check.sensor_name, check.threshold_type)

    def _wants_transition(
        self, check: _ThresholdCheck, current: AlertState
    ) -> AlertState | None:
        """Determine if the reading wants to transition to a different state.

        Returns the desired new state if a transition is warranted, or None
        if the reading is consistent with the current state.
        """
        if current == AlertState.OK and check.is_violated():
            return AlertState.IN_ALERT
        if current == AlertState.IN_ALERT and check.has_recovered():
            return AlertState.OK
        return None

    def _compute_new_state(
        self, check: _ThresholdCheck, key: _AlertKey, current: AlertState
    ) -> AlertState:
        """Compute the new alert state with confirmation window.

        Requires multiple consecutive readings indicating a transition before
        actually changing state. This prevents transient sensor errors from
        triggering false alerts.
        """
        desired = self._wants_transition(check, current)

        if desired is None:
            # Reading is consistent with current state - reset pending counter
            self._pending_counts.pop(key, None)
            return current

        # Reading wants to transition - increment pending counter
        pending = self._pending_counts.get(key, 0) + 1
        self._pending_counts[key] = pending

        if pending >= self._confirmation_count:
            self._pending_counts.pop(key, None)
            return desired

        return current

    def _handle_transition(
        self,
        check: _ThresholdCheck,
        previous: AlertState,
        new: AlertState,
        callback: AlertCallback | None,
    ) -> None:
        """Log and invoke callback for state transitions."""
        if previous == new:
            return

        is_resolved = new == AlertState.OK

        base_args = (
            check.namespace.value,
            check.sensor_name,
            check.value,
            check.unit,
        )
        if is_resolved:
            logger.info("[%s] %s returned to normal: %.1f%s", *base_args)
        else:
            logger.info(
                "[%s] %s crossed threshold: %.1f%s (threshold: %.0f)",
                *base_args,
                check.threshold,
            )

        if callback:
            callback(
                AlertEvent(
                    namespace=check.namespace,
                    sensor_name=check.sensor_name,
                    value=check.value,
                    unit=check.unit,
                    threshold=None if is_resolved else check.threshold,
                    recording_time=check.recording_time,
                    is_resolved=is_resolved,
                )
            )

    async def check(
        self,
        namespace: Namespace,
        sensor_name: _SensorName,
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
        """
        check = _ThresholdCheck(
            namespace=namespace,
            sensor_name=sensor_name,
            value=value,
            unit=unit,
            threshold=threshold,
            threshold_type=threshold_type,
            hysteresis=hysteresis,
            recording_time=recording_time,
        )
        key = self._make_key(check)

        async with self._get_lock():
            previous_state = self._states.get(key, AlertState.OK)
            new_state = self._compute_new_state(check, key, previous_state)
            self._states[key] = new_state
            callback = self._callbacks.get(namespace)

            # Update alert count for O(1) is_any_alert lookup
            sensor_key = (namespace, sensor_name)
            if previous_state != new_state:
                if new_state == AlertState.IN_ALERT:
                    self._alert_counts[sensor_key] = (
                        self._alert_counts.get(sensor_key, 0) + 1
                    )
                elif previous_state == AlertState.IN_ALERT:
                    count = self._alert_counts.get(sensor_key, 1) - 1
                    if count <= 0:
                        self._alert_counts.pop(sensor_key, None)
                    else:
                        self._alert_counts[sensor_key] = count

        # Call callback outside of lock to prevent deadlocks
        self._handle_transition(check, previous_state, new_state, callback)
        return new_state

    async def get_state(
        self,
        namespace: Namespace,
        sensor_name: _SensorName,
        threshold_type: ThresholdType,
    ) -> AlertState:
        """Get current alert state for a sensor threshold."""
        key: _AlertKey = (namespace, sensor_name, threshold_type)
        async with self._get_lock():
            return self._states.get(key, AlertState.OK)

    async def is_any_alert(
        self, namespace: Namespace, sensor_name: _SensorName
    ) -> bool:
        """Check if any threshold for this sensor is in alert state."""
        async with self._get_lock():
            return self._alert_counts.get((namespace, sensor_name), 0) > 0

    def _key_matches(
        self,
        key: _AlertKey,
        namespace: Namespace | None,
        sensor_name: _SensorName | None,
        threshold_type: ThresholdType | None,
    ) -> bool:
        """Check if a key matches the given filter criteria."""
        if namespace is not None and key[0] != namespace:
            return False
        if sensor_name is not None and key[1] != sensor_name:
            return False
        return threshold_type is None or key[2] == threshold_type

    async def reset(
        self,
        namespace: Namespace | None = None,
        sensor_name: _SensorName | None = None,
        threshold_type: ThresholdType | None = None,
    ) -> None:
        """Reset alert state and pending counts matching the filter criteria.

        All parameters are optional filters. If all are None, clears everything.
        """
        async with self._get_lock():
            to_delete = [
                k
                for k in self._states
                if self._key_matches(k, namespace, sensor_name, threshold_type)
            ]
            for k in to_delete:
                # Update alert count if we're deleting an alert state
                if self._states.get(k) == AlertState.IN_ALERT:
                    sensor_key = (k[0], k[1])
                    count = self._alert_counts.get(sensor_key, 1) - 1
                    if count <= 0:
                        self._alert_counts.pop(sensor_key, None)
                    else:
                        self._alert_counts[sensor_key] = count
                self._states.pop(k, None)
                self._pending_counts.pop(k, None)


def create_alert_publisher(publisher: EventPublisher) -> AlertCallback:
    """Create an alert callback that publishes to the event bus.

    Args:
        publisher: The EventPublisher to use for publishing alerts.

    Returns:
        A callback function that can be registered with AlertTracker.
    """
    from rpi.lib.eventbus import AlertEventPayload

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
        publisher.publish(payload)

    return publish_alert
