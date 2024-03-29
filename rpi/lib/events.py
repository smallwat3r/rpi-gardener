from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Deque

from rpi import logging

from .config import Threshold
from .reading import Measure

logger = logging.getLogger("queue-service")


@dataclass(frozen=True)
class Event:
    measure: Measure
    threshold: Threshold
    recording_time: datetime


class _Queue:
    def __init__(self) -> None:
        self._events: Deque[Event] = deque()

    @property
    def has_work(self) -> bool:
        return bool(self._events)

    def enqueue(self, event: Event) -> None:
        logger.info("Queuing event %s", id(event))
        self._events.append(event)

    def dequeue(self) -> Event:
        event = self._events.popleft()
        logger.info("Picking up event %s", id(event))
        return event


queue = _Queue()
