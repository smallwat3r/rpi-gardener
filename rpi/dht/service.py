"""Event handling and auditing service for the DHT22 sensor.

The service is responsible for:
- Auditing readings against predefined thresholds
- Queuing notification events when thresholds are crossed
- Processing events via a background worker thread
"""
from queue import Queue
from threading import Thread

from rpi import logging
from rpi.lib.config import THRESHOLD_RULES
from rpi.lib.notifications import Event, get_notifier
from rpi.dht.models import Measure, Reading, State

logger = logging.getLogger("dht-service")

_alert_state: dict[str, State] = {}
_queue: Queue[Event] = Queue()


def _event_worker() -> None:
    """Process events from the queue (blocks until event available)."""
    notifier = get_notifier()
    while True:
        event = _queue.get()
        logger.info("Processing event %s", id(event))
        notifier.send(event)
        _queue.task_done()


def start_worker() -> None:
    """Start the background worker thread for processing events."""
    Thread(target=_event_worker, daemon=True).start()


def _check_threshold(measure: Measure, rules: tuple) -> tuple[State, int | None]:
    """Check if measure violates any threshold rule."""
    for comparator, threshold in rules:
        if comparator(measure.value, threshold):
            return State.IN_ALERT, threshold
    return State.OK, None


def audit_reading(reading: Reading) -> None:
    """Audit reading values against thresholds and enqueue notification events."""
    for name, rules in THRESHOLD_RULES.items():
        measure: Measure = getattr(reading, name)
        previous_state = _alert_state.get(name, State.OK)

        new_state, threshold = _check_threshold(measure, rules)

        if new_state == State.IN_ALERT and previous_state != State.IN_ALERT:
            logger.info("%s crossed threshold: %.1f %s (threshold: %d)",
                        name, measure.value, measure.unit, threshold)
            _queue.put(Event(
                sensor_name=name,
                value=measure.value,
                unit=measure.unit,
                threshold=threshold,
                recording_time=reading.recording_time,
            ))

        _alert_state[name] = new_state
        measure.state = new_state
