"""Auditing service for the DHT22 sensor.

The service is responsible for:
- Auditing readings against predefined thresholds
- Publishing alert events to the event bus (notifications handled by web server)
"""

from rpi.dht.models import Measure, Reading, State
from rpi.lib.alerts import AlertTracker, Namespace
from rpi.lib.config import get_threshold_rules_async
from rpi.logging import get_logger

logger = get_logger("dht.audit")


async def audit_reading(reading: Reading, tracker: AlertTracker) -> None:
    """Audit reading values against thresholds and publish alert events.

    Fetches current thresholds from DB to support runtime configuration
    changes made via the admin API.
    """
    threshold_rules = await get_threshold_rules_async()

    for name, rules in threshold_rules.items():
        measure: Measure = getattr(reading, name)

        # Check all threshold rules for this measure
        for threshold_type, threshold, hysteresis in rules:
            await tracker.check(
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
            if await tracker.is_any_alert(Namespace.DHT, name)
            else State.OK
        )
