"""Tests for the WebSocket module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.websockets import WebSocketDisconnect

from rpi.server.websockets import ConnectionManager, connection_manager


class TestConnectionManager:
    """Tests for ConnectionManager class."""

    @pytest.fixture
    def manager(self):
        """Create a fresh ConnectionManager for each test."""
        return ConnectionManager()

    @pytest.fixture
    def mock_websocket(self):
        """Create a mock WebSocket."""
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.close = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_connect_accepts_websocket(self, manager, mock_websocket):
        """Connect should accept the WebSocket."""
        await manager.connect(mock_websocket, "/test")
        mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_returns_client_id(self, manager, mock_websocket):
        """Connect should return a unique client ID."""
        client_id = await manager.connect(mock_websocket, "/test")
        assert client_id == id(mock_websocket)

    @pytest.mark.asyncio
    async def test_connect_tracks_connection(self, manager, mock_websocket):
        """Connect should track the connection."""
        await manager.connect(mock_websocket, "/test")
        assert manager.get_connection_count("/test") == 1

    @pytest.mark.asyncio
    async def test_connect_multiple_endpoints(self, manager):
        """Connections to different endpoints should be tracked separately."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        await manager.connect(ws1, "/endpoint1")
        await manager.connect(ws2, "/endpoint2")

        assert manager.get_connection_count("/endpoint1") == 1
        assert manager.get_connection_count("/endpoint2") == 1
        assert manager.get_connection_count() == 2

    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(
        self, manager, mock_websocket
    ):
        """Disconnect should remove the connection."""
        await manager.connect(mock_websocket, "/test")
        manager.disconnect(mock_websocket, "/test")
        assert manager.get_connection_count("/test") == 0

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_connection(
        self, manager, mock_websocket
    ):
        """Disconnect on non-tracked connection should not error."""
        manager.disconnect(mock_websocket, "/test")
        assert manager.get_connection_count("/test") == 0

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_clients(self, manager):
        """Broadcast should send data to all clients on endpoint."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        await manager.connect(ws1, "/test")
        await manager.connect(ws2, "/test")

        data = {"message": "hello"}
        sent_count = await manager.broadcast("/test", data)

        assert sent_count == 2
        ws1.send_json.assert_called_once_with(data)
        ws2.send_json.assert_called_once_with(data)

    @pytest.mark.asyncio
    async def test_broadcast_to_empty_endpoint(self, manager):
        """Broadcast to endpoint with no connections should return 0."""
        sent_count = await manager.broadcast("/empty", {"data": "test"})
        assert sent_count == 0

    @pytest.mark.asyncio
    async def test_broadcast_removes_disconnected_clients(self, manager):
        """Broadcast should remove clients that fail to receive."""
        ws_good = AsyncMock()
        ws_bad = AsyncMock()
        ws_bad.send_json.side_effect = WebSocketDisconnect()

        await manager.connect(ws_good, "/test")
        await manager.connect(ws_bad, "/test")
        assert manager.get_connection_count("/test") == 2

        sent_count = await manager.broadcast("/test", {"data": "test"})

        assert sent_count == 1
        assert manager.get_connection_count("/test") == 1

    @pytest.mark.asyncio
    async def test_broadcast_handles_runtime_error(self, manager):
        """Broadcast should handle RuntimeError from closed connections."""
        ws = AsyncMock()
        ws.send_json.side_effect = RuntimeError("Connection closed")

        await manager.connect(ws, "/test")
        sent_count = await manager.broadcast("/test", {"data": "test"})

        assert sent_count == 0
        assert manager.get_connection_count("/test") == 0

    @pytest.mark.asyncio
    async def test_broadcast_handles_connection_reset(self, manager):
        """Broadcast should handle ConnectionResetError."""
        ws = AsyncMock()
        ws.send_json.side_effect = ConnectionResetError()

        await manager.connect(ws, "/test")
        sent_count = await manager.broadcast("/test", {"data": "test"})

        assert sent_count == 0
        assert manager.get_connection_count("/test") == 0

    @pytest.mark.asyncio
    async def test_broadcast_handles_os_error(self, manager):
        """Broadcast should handle OSError."""
        ws = AsyncMock()
        ws.send_json.side_effect = OSError("Broken pipe")

        await manager.connect(ws, "/test")
        sent_count = await manager.broadcast("/test", {"data": "test"})

        assert sent_count == 0
        assert manager.get_connection_count("/test") == 0

    def test_get_connection_count_total(self, manager):
        """get_connection_count with no endpoint should return total."""
        assert manager.get_connection_count() == 0

    def test_get_connection_count_unknown_endpoint(self, manager):
        """get_connection_count for unknown endpoint should return 0."""
        assert manager.get_connection_count("/unknown") == 0


class TestWebSocketEndpoints:
    """Tests for WebSocket route handlers."""

    @pytest.fixture
    def mock_websocket(self):
        """Create a mock WebSocket for testing."""
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.close = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_ws_dht_latest_sends_initial_data(self, mock_websocket):
        """DHT WebSocket should send initial data on connect."""
        from rpi.server.websockets import ws_dht_latest

        initial_data = {"temperature": 22.5, "humidity": 55.0}

        with (
            patch(
                "rpi.server.websockets.get_latest_dht_data",
                new_callable=AsyncMock,
                return_value=initial_data,
            ),
            patch(
                "rpi.server.websockets._maintain_connection",
                new_callable=AsyncMock,
            ) as mock_maintain,
        ):
            await ws_dht_latest(mock_websocket)

            mock_maintain.assert_called_once_with(
                mock_websocket, "/dht/latest", initial_data
            )

    @pytest.mark.asyncio
    async def test_ws_pico_latest_sends_initial_data(self, mock_websocket):
        """Pico WebSocket should send initial data on connect."""
        from rpi.server.websockets import ws_pico_latest

        initial_data = [{"plant_id": 1, "moisture": 50.0}]

        with (
            patch(
                "rpi.server.websockets.get_latest_pico_data",
                new_callable=AsyncMock,
                return_value=initial_data,
            ),
            patch(
                "rpi.server.websockets._maintain_connection",
                new_callable=AsyncMock,
            ) as mock_maintain,
        ):
            await ws_pico_latest(mock_websocket)

            mock_maintain.assert_called_once_with(
                mock_websocket, "/pico/latest", initial_data
            )

    @pytest.mark.asyncio
    async def test_ws_alerts_no_initial_data(self, mock_websocket):
        """Alerts WebSocket should not send initial data."""
        from rpi.server.websockets import ws_alerts

        with patch(
            "rpi.server.websockets._maintain_connection",
            new_callable=AsyncMock,
        ) as mock_maintain:
            await ws_alerts(mock_websocket)

            # Called without initial_data (alerts are transient)
            mock_maintain.assert_called_once_with(mock_websocket, "/alerts")


class TestMaintainConnection:
    """Tests for the _maintain_connection helper."""

    @pytest.fixture
    def mock_websocket(self):
        """Create a mock WebSocket for testing."""
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.close = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_sends_initial_data_when_provided(self, mock_websocket):
        """Should send initial data after connection."""
        from rpi.server.websockets import _maintain_connection

        initial_data = {"key": "value"}

        # Make connection disconnect immediately after initial data
        mock_websocket.send_json.side_effect = [
            None,  # Initial data send succeeds
            WebSocketDisconnect(),  # Heartbeat fails (disconnect)
        ]

        with (
            patch("rpi.server.websockets.connection_manager") as mock_manager,
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_manager.connect = AsyncMock(return_value=123)
            mock_manager.disconnect = MagicMock()

            await _maintain_connection(mock_websocket, "/test", initial_data)

            # Verify initial data was sent
            mock_websocket.send_json.assert_any_call(initial_data)

    @pytest.mark.asyncio
    async def test_handles_disconnect_gracefully(self, mock_websocket):
        """Should handle WebSocketDisconnect gracefully."""
        from rpi.server.websockets import _maintain_connection

        mock_websocket.send_json.side_effect = WebSocketDisconnect()

        with (
            patch("rpi.server.websockets.connection_manager") as mock_manager,
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_manager.connect = AsyncMock(return_value=123)
            mock_manager.disconnect = MagicMock()

            # Should not raise
            await _maintain_connection(mock_websocket, "/test")

            mock_manager.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleans_up_on_disconnect(self, mock_websocket):
        """Should clean up resources on disconnect."""
        from rpi.server.websockets import _maintain_connection

        mock_websocket.send_json.side_effect = WebSocketDisconnect()

        with (
            patch("rpi.server.websockets.connection_manager") as mock_manager,
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_manager.connect = AsyncMock(return_value=123)
            mock_manager.disconnect = MagicMock()

            await _maintain_connection(mock_websocket, "/test")

            mock_manager.disconnect.assert_called_once_with(
                mock_websocket, "/test"
            )
            mock_websocket.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancellation_handling(self, mock_websocket):
        """Should re-raise CancelledError for proper shutdown."""
        from rpi.server.websockets import _maintain_connection

        with patch("rpi.server.websockets.connection_manager") as mock_manager:
            mock_manager.connect = AsyncMock(return_value=123)
            mock_manager.disconnect = MagicMock()

            # Simulate cancellation during initial data send
            mock_websocket.send_json.side_effect = asyncio.CancelledError()

            with pytest.raises(asyncio.CancelledError):
                await _maintain_connection(
                    mock_websocket, "/test", {"data": "initial"}
                )

            # Should still clean up
            mock_manager.disconnect.assert_called_once()


class TestHeartbeat:
    """Tests for heartbeat functionality."""

    @pytest.mark.asyncio
    async def test_heartbeat_sends_ping(self):
        """Heartbeat should send ping messages."""
        from rpi.server.websockets import _send_heartbeat

        mock_websocket = AsyncMock()

        # Set up to disconnect after first ping
        call_count = 0

        async def send_json_side_effect(data):
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise WebSocketDisconnect()

        mock_websocket.send_json = AsyncMock(side_effect=send_json_side_effect)

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(WebSocketDisconnect),
        ):
            await _send_heartbeat(mock_websocket, 123)

            # Should have sent at least one ping
            mock_websocket.send_json.assert_called_with({"type": "ping"})

    @pytest.mark.asyncio
    async def test_heartbeat_raises_on_connection_error(self):
        """Heartbeat should raise WebSocketDisconnect on connection error."""
        from rpi.server.websockets import _send_heartbeat

        mock_websocket = AsyncMock()
        mock_websocket.send_json.side_effect = RuntimeError(
            "Connection closed"
        )

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(WebSocketDisconnect),
        ):
            await _send_heartbeat(mock_websocket, 123)


class TestGlobalConnectionManager:
    """Tests for the global connection_manager instance."""

    def test_global_manager_exists(self):
        """Global connection_manager should exist."""
        assert connection_manager is not None
        assert isinstance(connection_manager, ConnectionManager)
