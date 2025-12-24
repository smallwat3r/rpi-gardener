"""Event handling and auditing service for the DHT22 sensor.

The service is responsible for:
- Auditing readings against predefined thresholds
- Queuing notification events when thresholds are crossed
- Processing events via a background async task
"""
import asyncio

from rpi.dht.models import Measure, Reading, State
from rpi.lib.alerts import AlertEvent, AlertState, Namespace, get_alert_tracker
from rpi.lib.config import get_threshold_rules
from rpi.lib.notifications import get_notifier
from rpi.logging import get_logger

logger = get_logger("dht.audit")

_queue: asyncio.Queue[AlertEvent] | None = None
_worker_task: asyncio.Task | None = None


def _enqueue_event(event: AlertEvent) -> None:
    """Enqueue an alert event for processing by the background worker."""
    if _queue is not None:
        _queue.put_nowait(event)


async def _event_worker() -> None:
    """Process events from the queue asynchronously."""
    notifier = get_notifier()
    while True:
        event = await _queue.get()
        event_type = "resolution" if event.is_resolved else "alert"
        logger.info("Processing %s for %s", event_type, event.sensor_name)
        await notifier.send(event)
        _queue.task_done()


def start_worker() -> None:
    """Start the background worker task for processing events."""
    global _queue, _worker_task
    _queue = asyncio.Queue()
    _worker_task = asyncio.create_task(_event_worker())
    tracker = get_alert_tracker()
    tracker.register_callback(Namespace.DHT, _enqueue_event)


def audit_reading(reading: Reading) -> None:
    """Audit reading values against thresholds and enqueue notification events."""
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
                measure.state = State.IN_ALERT if alert_state == AlertState.IN_ALERT else State.OK
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
