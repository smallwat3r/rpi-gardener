"""Auditing service for the DHT22 sensor.

The service is responsible for:
- Auditing readings against predefined thresholds
- Publishing alert events to the event bus (notifications handled by web server)
"""

from rpi.dht.models import Measure, Reading, State
from rpi.lib.alerts import AlertEvent, AlertState, Namespace, get_alert_tracker
from rpi.lib.config import get_threshold_rules
from rpi.lib.eventbus import AlertEventPayload, Topic, get_publisher
from rpi.logging import get_logger

logger = get_logger("dht.audit")


def _publish_alert(event: AlertEvent) -> None:
    """Publish an alert event to the event bus."""
    payload = AlertEventPayload(
        namespace=event.namespace.value,
        sensor_name=event.sensor_name,
        value=event.value,
        unit=event.unit,
        threshold=event.threshold,
        recording_time=event.recording_time,
        is_resolved=event.is_resolved,
    )
    get_publisher().publish(Topic.ALERT, payload)


def init() -> None:
    """Initialize the audit service by registering the alert callback."""
    tracker = get_alert_tracker()
    tracker.register_callback(Namespace.DHT, _publish_alert)


def audit_reading(reading: Reading) -> None:
    """Audit reading values against thresholds and publish alert events."""
    tracker = get_alert_tracker()

    for name, rules in get_threshold_rules().items():
        measure: Measure = getattr(reading, name)

        # Check each rule for this measure
        for comparator, threshold in rules:
            is_violated = comparator(measure.value, threshold)
            if is_violated:
                alert_state = tracker.check(
                    namespace=Namespace.DHT,
                    sensor_name=name,
                    value=measure.value,
                    unit=str(measure.unit),
                    threshold=threshold,
                    is_violated=True,
                    recording_time=reading.recording_time,
                )
                measure.state = (
                    State.IN_ALERT
                    if alert_state == AlertState.IN_ALERT
                    else State.OK
                )
                break
        else:
            # No threshold violated
            tracker.check(
                namespace=Namespace.DHT,
                sensor_name=name,
                value=measure.value,
                unit=str(measure.unit),
                threshold=0,
                is_violated=False,
                recording_time=reading.recording_time,
            )
            measure.state = State.OK
