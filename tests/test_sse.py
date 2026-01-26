"""Tests for the SSE module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSSEEndpoints:
    """Tests for SSE route handlers."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock Request for testing."""
        request = MagicMock()
        request.is_disconnected = AsyncMock(return_value=False)
        return request

    @pytest.mark.asyncio
    async def test_sse_dht_latest_returns_streaming_response(self, mock_request):
        """DHT SSE endpoint should return StreamingResponse."""
        from rpi.server.sse import sse_dht_latest

        with patch(
            "rpi.server.sse.get_latest_dht_data",
            new_callable=AsyncMock,
            return_value={"temperature": 22.5, "humidity": 55.0},
        ):
            response = await sse_dht_latest(mock_request)
            assert response is not None
            assert response.media_type == "text/event-stream"

    @pytest.mark.asyncio
    async def test_sse_pico_latest_returns_streaming_response(self, mock_request):
        """Pico SSE endpoint should return StreamingResponse."""
        from rpi.server.sse import sse_pico_latest

        with patch(
            "rpi.server.sse.get_latest_pico_data",
            new_callable=AsyncMock,
            return_value=[{"plant_id": 1, "moisture": 50.0}],
        ):
            response = await sse_pico_latest(mock_request)
            assert response is not None
            assert response.media_type == "text/event-stream"

    @pytest.mark.asyncio
    async def test_sse_humidifier_state_returns_streaming_response(
        self, mock_request
    ):
        """Humidifier SSE endpoint should return StreamingResponse."""
        from rpi.server.sse import sse_humidifier_state

        with patch(
            "rpi.server.sse._get_last_humidifier_state",
            new_callable=AsyncMock,
            return_value={"is_on": True, "recording_time": "2024-01-01 12:00:00"},
        ):
            response = await sse_humidifier_state(mock_request)
            assert response is not None
            assert response.media_type == "text/event-stream"


class TestEventGenerator:
    """Tests for the _event_generator helper."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock Request for testing."""
        request = MagicMock()
        request.is_disconnected = AsyncMock(return_value=False)
        return request

    @pytest.mark.asyncio
    async def test_yields_initial_data(self, mock_request):
        """Generator should yield initial data first."""
        from rpi.lib.eventbus import Topic
        from rpi.server.sse import _event_generator

        initial_data = {"key": "value"}

        async def empty_gen():
            return
            yield  # Make it an async generator

        with patch("rpi.server.sse._subscribe_to_topic", return_value=empty_gen()):
            gen = _event_generator(
                mock_request, "/test", Topic.DHT_READING, initial_data
            )
            first_event = await gen.__anext__()

            # SSE format: "data: <json>\n\n"
            assert first_event.startswith("data: ")
            assert first_event.endswith("\n\n")
            assert '"key": "value"' in first_event

    @pytest.mark.asyncio
    async def test_stops_on_client_disconnect(self, mock_request):
        """Generator should stop when client disconnects."""
        from rpi.lib.eventbus import Topic
        from rpi.server.sse import _event_generator

        # Simulate client disconnect after first event
        call_count = 0

        async def is_disconnected():
            nonlocal call_count
            call_count += 1
            return call_count > 1

        mock_request.is_disconnected = is_disconnected

        async def infinite_events():
            while True:
                yield {"data": "test"}

        with patch(
            "rpi.server.sse._subscribe_to_topic", return_value=infinite_events()
        ):
            gen = _event_generator(
                mock_request, "/test", Topic.DHT_READING, {"initial": "data"}
            )

            events = []
            async for event in gen:
                events.append(event)
                if len(events) > 5:
                    break

            # Should have initial data + 1 event before disconnect check
            assert len(events) <= 3


class TestSubscribeToTopic:
    """Tests for the _subscribe_to_topic helper."""

    @pytest.mark.asyncio
    async def test_handles_redis_error_gracefully(self):
        """Should handle Redis connection errors gracefully."""
        import redis.asyncio as aioredis

        from rpi.lib.eventbus import Topic
        from rpi.server.sse import _subscribe_to_topic

        with patch(
            "rpi.server.sse.aioredis.from_url",
            side_effect=aioredis.RedisError("Connection refused"),
        ):
            events = []
            async for event in _subscribe_to_topic(Topic.DHT_READING):
                events.append(event)

            # Should complete without events, not raise
            assert events == []
