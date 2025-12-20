"""Event handling and auditing service for the DHT22 sensor.

The service is responsible for:
- Auditing readings against predefined thresholds
- Queuing notification events when thresholds are crossed
- Processing events via a background worker thread
"""
from collections import deque
from dataclasses import dataclass
from threading import Thread
from time import sleep
from typing import Deque

from rpi import logging
from rpi.lib.config import THRESHOLD_RULES
from rpi.lib.reading import Measure, Reading, State
from rpi.notifications import Event, get_notifier

logger = logging.getLogger("dht-service")


class EventQueue:
    """A simple thread-safe in-memory queue for notification events."""

    def __init__(self) -> None:
        self._events: Deque[Event] = deque()

    @property
    def has_work(self) -> bool:
        """Return True if there are events in the queue."""
        return bool(self._events)

    def enqueue(self, event: Event) -> None:
        """Enqueue a new event."""
        logger.info("Queuing event %s", id(event))
        self._events.append(event)

    def dequeue(self) -> Event:
        """Dequeue an event."""
        event = self._events.popleft()
        logger.info("Picking up event %s", id(event))
        return event


# Global event queue
queue = EventQueue()


def _process_event() -> None:
    """Process a single event from the queue."""
    event = queue.dequeue()
    notifier = get_notifier()
    notifier.send(event)


def _event_handler() -> None:
    """Continuously process events from the queue."""
    while True:
        sleep(1)
        if queue.has_work:
            _process_event()


def start_worker() -> None:
    """Start the background worker thread for processing events."""
    Thread(target=_event_handler, daemon=True).start()


@dataclass
class _StateTracker:
    """Tracks alert state for temperature and humidity."""
    temperature: State = State.OK
    humidity: State = State.OK


def audit_reading(reading: Reading) -> None:
    """Audit reading values against thresholds and enqueue notification events.

    Compares reading values against configured threshold rules. When a threshold
    is crossed and the measure wasn't already in alert state, queues a
    notification event.
    """
    tracker = _StateTracker()
    for name, rules in THRESHOLD_RULES.items():
        for rule in rules:
            comparator, threshold = rule
            measure: Measure = getattr(reading, name)
            if comparator(measure.value, threshold):
                setattr(tracker, name, State.IN_ALERT)
                if measure.state != State.IN_ALERT:
                    queue.enqueue(
                        Event(measure, threshold, reading.recording_time)
                    )
                break
        getattr(reading, name).state = getattr(tracker, name)
