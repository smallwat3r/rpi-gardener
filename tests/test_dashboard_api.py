"""Tests for the dashboard API endpoint."""

from sqlite3 import DatabaseError
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rpi.server.api.dashboard import get_dashboard


class TestGetDashboard:
    """Tests for get_dashboard endpoint."""

    def _make_request(self, query_params: dict[str, str] | None = None):
        """Create a mock Starlette request."""
        request = MagicMock()
        request.query_params = query_params or {}
        return request

    @pytest.mark.asyncio
    async def test_returns_dashboard_data(self):
        """Should return dashboard data with default hours."""
        with (
            patch(
                "rpi.server.api.dashboard.get_initial_dht_data",
                new_callable=AsyncMock,
                return_value=[{"temperature": 22.0, "humidity": 55.0}],
            ),
            patch(
                "rpi.server.api.dashboard.get_stats_dht_data",
                new_callable=AsyncMock,
                return_value={"avg_temp": 22.0},
            ),
            patch(
                "rpi.server.api.dashboard.get_latest_dht_data",
                new_callable=AsyncMock,
                return_value={"temperature": 22.5},
            ),
            patch(
                "rpi.server.api.dashboard.get_initial_pico_data",
                new_callable=AsyncMock,
                return_value=[{"plant-1": 50.0}],
            ),
            patch(
                "rpi.server.api.dashboard.get_latest_pico_data",
                new_callable=AsyncMock,
                return_value=[{"plant-1": 50.0}],
            ),
        ):
            response = await get_dashboard(self._make_request())

        assert response.status_code == 200
        body = bytes(response.body)
        assert b"hours" in body
        assert b"data" in body
        assert b"stats" in body
        assert b"latest" in body
        assert b"pico_data" in body
        assert b"pico_latest" in body

    @pytest.mark.asyncio
    async def test_accepts_hours_parameter(self):
        """Should accept custom hours parameter."""
        with (
            patch(
                "rpi.server.api.dashboard.get_initial_dht_data",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "rpi.server.api.dashboard.get_stats_dht_data",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "rpi.server.api.dashboard.get_latest_dht_data",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "rpi.server.api.dashboard.get_initial_pico_data",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "rpi.server.api.dashboard.get_latest_pico_data",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            response = await get_dashboard(self._make_request({"hours": "12"}))

        assert response.status_code == 200
        assert b'"hours":12' in response.body

    @pytest.mark.asyncio
    async def test_invalid_hours_returns_400(self):
        """Should return 400 for invalid hours parameter."""
        response = await get_dashboard(
            self._make_request({"hours": "invalid"})
        )

        assert response.status_code == 400
        assert b"error" in response.body

    @pytest.mark.asyncio
    async def test_hours_out_of_range_returns_400(self):
        """Should return 400 for hours out of valid range."""
        response = await get_dashboard(self._make_request({"hours": "0"}))

        assert response.status_code == 400
        assert b"error" in response.body

    @pytest.mark.asyncio
    async def test_database_error_returns_503(self):
        """Should return 503 when database is unavailable."""
        with (
            patch(
                "rpi.server.api.dashboard.get_initial_dht_data",
                new_callable=AsyncMock,
                side_effect=DatabaseError("Connection failed"),
            ),
            patch(
                "rpi.server.api.dashboard.get_stats_dht_data",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "rpi.server.api.dashboard.get_latest_dht_data",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "rpi.server.api.dashboard.get_initial_pico_data",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "rpi.server.api.dashboard.get_latest_pico_data",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            response = await get_dashboard(self._make_request())

        assert response.status_code == 503
        assert b"Database unavailable" in response.body
