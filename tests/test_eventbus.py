"""Tests for the Redis event bus."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rpi.lib.config import Unit
from rpi.lib.eventbus import (
    AlertEventPayload,
    DHTReadingEvent,
    EventPublisher,
    EventSubscriber,
    PicoReadingEvent,
    Topic,
)


class TestDHTReadingEvent:
    """Tests for DHTReadingEvent dataclass."""

    def test_to_dict(self):
        """Event serializes to dictionary correctly."""
        event = DHTReadingEvent(
            temperature=23.5,
            humidity=65.0,
            recording_time=datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC),
        )
        result = event.to_dict()

        assert result["temperature"] == 23.5
        assert result["humidity"] == 65.0
        assert result["recording_time"] == "2024-06-15 12:00:00"
        assert result["epoch"] == 1718452800000


class TestPicoReadingEvent:
    """Tests for PicoReadingEvent dataclass."""

    def test_to_dict(self):
        """Event serializes to dictionary correctly."""
        event = PicoReadingEvent(
            plant_id=1,
            moisture=45.5,
            recording_time=datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC),
        )
        result = event.to_dict()

        assert result["plant_id"] == 1
        assert result["moisture"] == 45.5
        assert result["recording_time"] == "2024-06-15 12:00:00"
        assert result["epoch"] == 1718452800000


class TestAlertEventPayload:
    """Tests for AlertEventPayload dataclass."""

    def test_to_dict_alert(self):
        """Alert event serializes correctly."""
        event = AlertEventPayload(
            namespace="dht",
            sensor_name="temperature",
            value=28.0,
            unit=Unit.CELSIUS,
            threshold=25.0,
            recording_time=datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC),
            is_resolved=False,
        )
        result = event.to_dict()

        assert result["namespace"] == "dht"
        assert result["sensor_name"] == "temperature"
        assert result["value"] == 28.0
        assert result["unit"] == Unit.CELSIUS
        assert result["threshold"] == 25.0
        assert result["recording_time"] == "2024-06-15 12:00:00"
        assert result["is_resolved"] is False

    def test_to_dict_resolved(self):
        """Resolved event serializes with null threshold."""
        event = AlertEventPayload(
            namespace="pico",
            sensor_name=1,
            value=35.0,
            unit=Unit.PERCENT,
            threshold=None,
            recording_time=datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC),
            is_resolved=True,
        )
        result = event.to_dict()

        assert result["sensor_name"] == 1
        assert result["threshold"] is None
        assert result["is_resolved"] is True


class TestEventPublisher:
    """Tests for EventPublisher."""

    @patch("rpi.lib.eventbus.redis")
    def test_connect_creates_client(self, mock_redis):
        """Connect creates a Redis client."""
        mock_client = MagicMock()
        mock_redis.from_url.return_value = mock_client

        publisher = EventPublisher()
        publisher.connect()

        mock_redis.from_url.assert_called_once()
        assert publisher._client is mock_client

    @patch("rpi.lib.eventbus.redis")
    def test_publish_single_event(self, mock_redis):
        """Publish serializes and sends a single event."""
        mock_client = MagicMock()
        mock_redis.from_url.return_value = mock_client

        publisher = EventPublisher()
        publisher.connect()

        event = DHTReadingEvent(
            temperature=22.0,
            humidity=50.0,
            recording_time=datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC),
        )
        publisher.publish(Topic.DHT_READING, event)

        mock_client.publish.assert_called_once()
        call_args = mock_client.publish.call_args
        assert call_args[0][0] == Topic.DHT_READING
        payload = json.loads(call_args[0][1])
        assert payload["temperature"] == 22.0
        assert payload["humidity"] == 50.0

    @patch("rpi.lib.eventbus.redis")
    def test_publish_event_list(self, mock_redis):
        """Publish serializes and sends a list of events."""
        mock_client = MagicMock()
        mock_redis.from_url.return_value = mock_client

        publisher = EventPublisher()
        publisher.connect()

        events = [
            PicoReadingEvent(
                1, 40.0, datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
            ),
            PicoReadingEvent(
                2, 55.0, datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
            ),
        ]
        publisher.publish(Topic.PICO_READING, events)

        mock_client.publish.assert_called_once()
        call_args = mock_client.publish.call_args
        payload = json.loads(call_args[0][1])
        assert len(payload) == 2
        assert payload[0]["plant_id"] == 1
        assert payload[1]["plant_id"] == 2

    @patch("rpi.lib.eventbus.redis")
    def test_publish_without_connect_does_nothing(self, mock_redis):
        """Publish without connect silently returns."""
        publisher = EventPublisher()
        event = DHTReadingEvent(22.0, 50.0, datetime.now(UTC))

        # Should not raise
        publisher.publish(Topic.DHT_READING, event)

    @patch("rpi.lib.eventbus.redis")
    def test_close(self, mock_redis):
        """Close closes the Redis client."""
        mock_client = MagicMock()
        mock_redis.from_url.return_value = mock_client

        publisher = EventPublisher()
        publisher.connect()
        publisher.close()

        mock_client.close.assert_called_once()
        assert publisher._client is None


class TestEventSubscriber:
    """Tests for EventSubscriber."""

    @pytest.mark.asyncio
    @patch("rpi.lib.eventbus.aioredis")
    async def test_connect_subscribes_to_topics(self, mock_aioredis):
        """Connect creates client and subscribes to specified topics."""
        mock_pubsub = MagicMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_client = MagicMock()
        mock_client.pubsub.return_value = mock_pubsub
        mock_aioredis.from_url.return_value = mock_client

        subscriber = EventSubscriber(topics=[Topic.DHT_READING, Topic.ALERT])
        await subscriber.connect()

        mock_aioredis.from_url.assert_called_once()
        mock_pubsub.subscribe.assert_called_once_with(
            Topic.DHT_READING, Topic.ALERT
        )

    @pytest.mark.asyncio
    @patch("rpi.lib.eventbus.aioredis")
    async def test_connect_subscribes_to_all_topics_by_default(
        self, mock_aioredis
    ):
        """Connect subscribes to all topics when none specified."""
        mock_pubsub = MagicMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_client = MagicMock()
        mock_client.pubsub.return_value = mock_pubsub
        mock_aioredis.from_url.return_value = mock_client

        subscriber = EventSubscriber()
        await subscriber.connect()

        mock_pubsub.subscribe.assert_called_once()
        subscribed_topics = mock_pubsub.subscribe.call_args[0]
        assert set(subscribed_topics) == set(Topic)

    @pytest.mark.asyncio
    @patch("rpi.lib.eventbus.aioredis")
    async def test_receive_yields_messages(self, mock_aioredis):
        """Receive yields topic/data tuples from messages."""
        # Simulate messages from Redis
        messages = [
            {"type": "subscribe", "channel": b"dht.reading", "data": 1},
            {
                "type": "message",
                "channel": b"dht.reading",
                "data": b'{"temperature": 22.5}',
            },
            {
                "type": "message",
                "channel": b"alert",
                "data": b'{"sensor_name": "humidity"}',
            },
        ]

        async def mock_listen():
            for msg in messages:
                yield msg

        mock_pubsub = MagicMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.listen.return_value = mock_listen()
        mock_client = MagicMock()
        mock_client.pubsub.return_value = mock_pubsub
        mock_aioredis.from_url.return_value = mock_client

        subscriber = EventSubscriber()
        await subscriber.connect()

        results = []
        async for topic, data in subscriber.receive():
            results.append((topic, data))

        # Should only get the "message" types, not "subscribe"
        assert len(results) == 2
        assert results[0] == (Topic.DHT_READING, {"temperature": 22.5})
        assert results[1] == (Topic.ALERT, {"sensor_name": "humidity"})

    @pytest.mark.asyncio
    @patch("rpi.lib.eventbus.aioredis")
    async def test_close(self, mock_aioredis):
        """Close unsubscribes and closes client."""
        mock_pubsub = MagicMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()
        mock_client = MagicMock()
        mock_client.pubsub.return_value = mock_pubsub
        mock_client.close = AsyncMock()
        mock_aioredis.from_url.return_value = mock_client

        subscriber = EventSubscriber()
        await subscriber.connect()
        await subscriber.close()

        mock_pubsub.unsubscribe.assert_called_once()
        mock_pubsub.close.assert_called_once()
        mock_client.close.assert_called_once()
