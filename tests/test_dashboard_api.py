"""Tests for the dashboard API endpoint."""

from contextlib import asynccontextmanager
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

    def _make_mock_db(
        self,
        dht_data=None,
        stats=None,
        latest=None,
        pico_data=None,
        pico_latest=None,
        raise_error=False,
    ):
        """Create a mock database context manager."""
        mock_db = AsyncMock()
        if raise_error:
            mock_db.fetchall.side_effect = DatabaseError("Connection failed")
        else:
            mock_db.fetchall.side_effect = [
                dht_data or [],
                pico_data or [],
                pico_latest or [],
            ]
            mock_db.fetchone.side_effect = [stats or {}, latest]

        @asynccontextmanager
        async def mock_get_db():
            yield mock_db

        return mock_get_db

    @pytest.mark.asyncio
    async def test_returns_dashboard_data(self):
        """Should return dashboard data with default hours."""
        mock_get_db = self._make_mock_db(
            dht_data=[{"temperature": 22.0, "humidity": 55.0, "epoch": 1000}],
            stats={"avg_temp": 22.0},
            latest={"temperature": 22.5},
            pico_data=[{"epoch": 1000, "plants": '{"1": 50.0}'}],
            pico_latest=[{"plant_id": 1, "moisture": 50.0}],
        )

        with patch("rpi.server.api.dashboard.get_db", mock_get_db):
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
        mock_get_db = self._make_mock_db()

        with patch("rpi.server.api.dashboard.get_db", mock_get_db):
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
        mock_get_db = self._make_mock_db(raise_error=True)

        with patch("rpi.server.api.dashboard.get_db", mock_get_db):
            response = await get_dashboard(self._make_request())

        assert response.status_code == 503
        assert b"Database unavailable" in response.body
