from collections import deque
from dataclasses import dataclass
from typing import Deque

from ._config import Threshold


@dataclass(frozen=True)
class Event:
    threshold: Threshold
    value: float


class _Queue:
    def __init__(self) -> None:
        self._events: Deque[Event] = deque()

    @property
    def has_work(self) -> bool:
        return bool(self._events)

    def enqueue(self, event: Event) -> None:
        self._events.append(event)

    def dequeue(self) -> Event:
        return self._events.popleft()


queue = _Queue()
