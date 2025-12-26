"""Auditing service for the DHT22 sensor.

The service is responsible for:
- Auditing readings against predefined thresholds
- Publishing alert events to the event bus (notifications handled by web server)
"""

from rpi.dht.models import Measure, Reading, State
from rpi.lib.alerts import Namespace, get_alert_tracker, publish_alert
from rpi.lib.config import get_threshold_rules
from rpi.logging import get_logger

logger = get_logger("dht.audit")


def init() -> None:
    """Initialize the audit service by registering the alert callback."""
    tracker = get_alert_tracker()
    tracker.register_callback(Namespace.DHT, publish_alert)


def audit_reading(reading: Reading) -> None:
    """Audit reading values against thresholds and publish alert events."""
    tracker = get_alert_tracker()

    for name, rules in get_threshold_rules().items():
        measure: Measure = getattr(reading, name)

        # Check all threshold rules for this measure
        for threshold_type, threshold, hysteresis in rules:
            tracker.check(
                namespace=Namespace.DHT,
                sensor_name=name,
                value=measure.value,
                unit=measure.unit,
                threshold=threshold,
                threshold_type=threshold_type,
                hysteresis=hysteresis,
                recording_time=reading.recording_time,
            )

        # Set measure state based on any active alert
        measure.state = (
            State.IN_ALERT
            if tracker.is_any_alert(Namespace.DHT, name)
            else State.OK
        )
