"""Event handling and auditing service for the DHT22 sensor.

The service is responsible for:
- Auditing readings against predefined thresholds
- Queuing notification events when thresholds are crossed
- Processing events via a background worker thread
"""
from queue import Queue
from threading import Thread

from rpi import logging
from rpi.lib.alerts import AlertState, AlertTracker
from rpi.lib.config import THRESHOLD_RULES
from rpi.lib.notifications import Event, get_notifier
from rpi.dht.models import Measure, Reading, State

logger = logging.getLogger("dht-service")

_queue: Queue[Event] = Queue()


def _enqueue_event(event: Event) -> None:
    """Enqueue an event for processing by the background worker."""
    _queue.put(event)


_alert_tracker = AlertTracker(on_alert=_enqueue_event)


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


def audit_reading(reading: Reading) -> None:
    """Audit reading values against thresholds and enqueue notification events."""
    for name, rules in THRESHOLD_RULES.items():
        measure: Measure = getattr(reading, name)

        # Check each rule for this measure
        for comparator, threshold in rules:
            is_violated = comparator(measure.value, threshold)
            if is_violated:
                alert_state = _alert_tracker.check(
                    sensor_name=name,
                    value=measure.value,
                    unit=str(measure.unit),
                    threshold=threshold,
                    is_violated=True,
                    recording_time=reading.recording_time,
                )
                measure.state = State.IN_ALERT if alert_state == AlertState.IN_ALERT else State.OK
                break
        else:
            # No threshold violated
            _alert_tracker.check(
                sensor_name=name,
                value=measure.value,
                unit=str(measure.unit),
                threshold=0,
                is_violated=False,
                recording_time=reading.recording_time,
            )
            measure.state = State.OK
