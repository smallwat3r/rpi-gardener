"""Redis-based event bus for real-time sensor data broadcasting.

Provides pub/sub messaging between polling services (publishers) and
the web server/notification service (subscribers) for real-time updates.
"""

import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Self

import redis
import redis.asyncio as aioredis

from rpi.lib.config import Unit, get_settings
from rpi.logging import get_logger

logger = get_logger("lib.eventbus")


class Topic(StrEnum):
    """Event bus topics."""

    DHT_READING = "dht.reading"
    PICO_READING = "pico.reading"
    ALERT = "alert"


@dataclass(frozen=True, slots=True)
class Event(ABC):
    """Base class for all event bus payloads."""

    @property
    @abstractmethod
    def event_type(self) -> str:
        """Discriminator field for event type identification."""

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for JSON serialization."""


@dataclass(frozen=True, slots=True)
class DHTReadingEvent(Event):
    """DHT sensor reading event."""

    temperature: float
    humidity: float
    recording_time: datetime

    @property
    def event_type(self) -> Literal["dht_reading"]:
        return "dht_reading"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.event_type,
            "temperature": self.temperature,
            "humidity": self.humidity,
            "recording_time": self.recording_time.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "epoch": int(self.recording_time.timestamp() * 1000),
        }


@dataclass(frozen=True, slots=True)
class PicoReadingEvent(Event):
    """Single plant moisture reading."""

    plant_id: int
    moisture: float
    recording_time: datetime

    @property
    def event_type(self) -> Literal["pico_reading"]:
        return "pico_reading"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.event_type,
            "plant_id": self.plant_id,
            "moisture": self.moisture,
            "recording_time": self.recording_time.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "epoch": int(self.recording_time.timestamp() * 1000),
        }


@dataclass(frozen=True, slots=True)
class AlertEventPayload(Event):
    """Alert event for threshold violations and resolutions."""

    namespace: str
    sensor_name: str | int
    value: float
    unit: Unit
    threshold: float | None
    recording_time: datetime
    is_resolved: bool = False

    @property
    def event_type(self) -> Literal["alert"]:
        return "alert"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.event_type,
            "namespace": self.namespace,
            "sensor_name": self.sensor_name,
            "value": self.value,
            "unit": self.unit,
            "threshold": self.threshold,
            "recording_time": self.recording_time.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "is_resolved": self.is_resolved,
        }


# Type alias for any concrete event type
type AnyEvent = DHTReadingEvent | PicoReadingEvent | AlertEventPayload


class EventPublisher:
    """Publishes sensor readings to the event bus.

    Used by polling services (DHT, Pico) to broadcast new readings.
    """

    def __init__(self) -> None:
        self._redis_url = get_settings().eventbus.redis_url
        self._client: redis.Redis[bytes] | None = None

    def connect(self) -> None:
        """Connect to Redis."""
        self._client = redis.from_url(self._redis_url)
        logger.info("Event publisher connected to Redis")

    def publish(self, topic: Topic, data: Event | Sequence[Event]) -> None:
        """Publish a message to the event bus.

        Args:
            topic: The topic to publish to (e.g., Topic.DHT_READING).
            data: Event or list of Events to publish.
        """
        if self._client is None:
            return

        payload: list[dict[str, Any]] | dict[str, Any]
        if isinstance(data, Event):
            payload = data.to_dict()
        else:
            payload = [event.to_dict() for event in data]

        message = json.dumps(payload)
        self._client.publish(topic, message)
        logger.debug("Published to %s: %s", topic, message)

    def close(self) -> None:
        """Close the publisher connection."""
        if self._client is not None:
            self._client.close()
            self._client = None
        logger.info("Event publisher closed")


class EventSubscriber:
    """Subscribes to sensor readings from the event bus.

    Used by the web server and notification service to receive real-time updates.
    """

    def __init__(self, topics: list[Topic] | None = None) -> None:
        """Initialize subscriber.

        Args:
            topics: List of topics to subscribe to. If None, subscribes to all.
        """
        self._redis_url = get_settings().eventbus.redis_url
        self._topics = topics or list(Topic)
        self._client: aioredis.Redis[bytes] | None = None
        self._pubsub: aioredis.client.PubSub | None = None

    async def connect(self) -> None:
        """Connect to Redis and subscribe to topics."""
        self._client = aioredis.from_url(self._redis_url)
        self._pubsub = self._client.pubsub()
        await self._pubsub.subscribe(*self._topics)
        logger.info(
            "Event subscriber connected to Redis, topics: %s", self._topics
        )

    async def receive(self) -> AsyncIterator[tuple[Topic, dict[str, Any]]]:
        """Async iterator that yields (topic, data) tuples as they arrive."""
        if self._pubsub is None:
            return

        async for message in self._pubsub.listen():
            if message["type"] != "message":
                continue

            try:
                topic = Topic(message["channel"].decode())
                data = json.loads(message["data"].decode())
                yield topic, data
            except (ValueError, json.JSONDecodeError) as e:
                logger.warning("Invalid message: %s", e)

    async def close(self) -> None:
        """Close the subscriber connection."""
        if self._pubsub is not None:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()
            self._pubsub = None
        if self._client is not None:
            await self._client.close()
            self._client = None
        logger.info("Event subscriber closed")

    async def __aenter__(self) -> Self:
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, *_: object) -> None:
        """Async context manager exit."""
        await self.close()


# Global publisher instance (initialized by polling services)
_publisher: EventPublisher | None = None


def get_publisher() -> EventPublisher:
    """Get or create the global publisher instance."""
    global _publisher
    if _publisher is None:
        _publisher = EventPublisher()
    return _publisher
