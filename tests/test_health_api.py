"""Tests for the health check API endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rpi.server.api.health import health_check


class TestHealthCheck:
    """Tests for health_check endpoint."""

    def _make_request(self):
        """Create a mock Starlette request."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_healthy_when_all_checks_pass(self):
        """Should return healthy status when database and Redis are OK."""
        with (
            patch(
                "rpi.server.api.health._check_database",
                new_callable=AsyncMock,
                return_value=(True, "ok"),
            ),
            patch(
                "rpi.server.api.health._check_redis",
                new_callable=AsyncMock,
                return_value=(True, "ok"),
            ),
            patch(
                "rpi.server.api.health._check_dht_sensor",
                new_callable=AsyncMock,
                return_value=(True, "2024-06-15T12:00:00"),
            ),
            patch(
                "rpi.server.api.health._check_pico_sensor",
                new_callable=AsyncMock,
                return_value=(True, "2024-06-15T12:00:00"),
            ),
        ):
            response = await health_check(self._make_request())

        assert response.status_code == 200
        assert b'"status":"healthy"' in response.body
        assert b'"database"' in response.body
        assert b'"redis"' in response.body
        assert b'"dht_sensor"' in response.body
        assert b'"pico_sensor"' in response.body

    @pytest.mark.asyncio
    async def test_unhealthy_when_database_fails(self):
        """Should return unhealthy status when database is down."""
        with (
            patch(
                "rpi.server.api.health._check_database",
                new_callable=AsyncMock,
                return_value=(False, "Connection refused"),
            ),
            patch(
                "rpi.server.api.health._check_redis",
                new_callable=AsyncMock,
                return_value=(True, "ok"),
            ),
            patch(
                "rpi.server.api.health._check_dht_sensor",
                new_callable=AsyncMock,
                return_value=(True, "2024-06-15T12:00:00"),
            ),
            patch(
                "rpi.server.api.health._check_pico_sensor",
                new_callable=AsyncMock,
                return_value=(True, "2024-06-15T12:00:00"),
            ),
        ):
            response = await health_check(self._make_request())

        assert response.status_code == 503
        assert b'"status":"unhealthy"' in response.body
        assert b"Connection refused" in response.body

    @pytest.mark.asyncio
    async def test_unhealthy_when_redis_fails(self):
        """Should return unhealthy status when Redis is down."""
        with (
            patch(
                "rpi.server.api.health._check_database",
                new_callable=AsyncMock,
                return_value=(True, "ok"),
            ),
            patch(
                "rpi.server.api.health._check_redis",
                new_callable=AsyncMock,
                return_value=(False, "Connection refused"),
            ),
            patch(
                "rpi.server.api.health._check_dht_sensor",
                new_callable=AsyncMock,
                return_value=(True, "2024-06-15T12:00:00"),
            ),
            patch(
                "rpi.server.api.health._check_pico_sensor",
                new_callable=AsyncMock,
                return_value=(True, "2024-06-15T12:00:00"),
            ),
        ):
            response = await health_check(self._make_request())

        assert response.status_code == 503
        assert b'"status":"unhealthy"' in response.body

    @pytest.mark.asyncio
    async def test_healthy_when_sensors_fail(self):
        """Should return healthy even if sensors have no data (core services OK)."""
        with (
            patch(
                "rpi.server.api.health._check_database",
                new_callable=AsyncMock,
                return_value=(True, "ok"),
            ),
            patch(
                "rpi.server.api.health._check_redis",
                new_callable=AsyncMock,
                return_value=(True, "ok"),
            ),
            patch(
                "rpi.server.api.health._check_dht_sensor",
                new_callable=AsyncMock,
                return_value=(False, "no data"),
            ),
            patch(
                "rpi.server.api.health._check_pico_sensor",
                new_callable=AsyncMock,
                return_value=(False, "no data"),
            ),
        ):
            response = await health_check(self._make_request())

        # Core services (database, Redis) are OK, so overall status is healthy
        assert response.status_code == 200
        assert b'"status":"healthy"' in response.body


class TestCheckDatabase:
    """Tests for _check_database helper."""

    @pytest.mark.asyncio
    async def test_returns_true_when_db_accessible(self):
        """Should return True when database query succeeds."""
        from rpi.server.api.health import _check_database

        with patch("rpi.server.api.health.get_db") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.fetchone = AsyncMock(return_value={"1": 1})
            mock_get_db.return_value.__aenter__ = AsyncMock(
                return_value=mock_db
            )
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            ok, status = await _check_database()

        assert ok is True
        assert status == "ok"

    @pytest.mark.asyncio
    async def test_returns_false_on_db_error(self):
        """Should return False when database query fails."""
        import aiosqlite

        from rpi.server.api.health import _check_database

        with patch(
            "rpi.server.api.health.get_db",
            side_effect=aiosqlite.Error("Connection failed"),
        ):
            ok, status = await _check_database()

        assert ok is False
        assert "Connection failed" in status


class TestCheckDhtSensor:
    """Tests for _check_dht_sensor helper."""

    @pytest.mark.asyncio
    async def test_returns_true_with_recent_data(self):
        """Should return True when DHT sensor has data."""
        from rpi.server.api.health import _check_dht_sensor

        with patch(
            "rpi.server.api.health.get_latest_dht_data",
            new_callable=AsyncMock,
            return_value={"recording_time": "2024-06-15T12:00:00"},
        ):
            ok, last = await _check_dht_sensor()

        assert ok is True
        assert last == "2024-06-15T12:00:00"

    @pytest.mark.asyncio
    async def test_returns_false_with_no_data(self):
        """Should return False when DHT sensor has no data."""
        from rpi.server.api.health import _check_dht_sensor

        with patch(
            "rpi.server.api.health.get_latest_dht_data",
            new_callable=AsyncMock,
            return_value=None,
        ):
            ok, status = await _check_dht_sensor()

        assert ok is False
        assert status == "no data"


class TestCheckPicoSensor:
    """Tests for _check_pico_sensor helper."""

    @pytest.mark.asyncio
    async def test_returns_true_with_recent_data(self):
        """Should return True when Pico sensor has data."""
        from rpi.server.api.health import _check_pico_sensor

        with patch(
            "rpi.server.api.health.get_latest_pico_data",
            new_callable=AsyncMock,
            return_value=[{"recording_time": "2024-06-15T12:00:00"}],
        ):
            ok, last = await _check_pico_sensor()

        assert ok is True
        assert last == "2024-06-15T12:00:00"

    @pytest.mark.asyncio
    async def test_returns_false_with_no_data(self):
        """Should return False when Pico sensor has no data."""
        from rpi.server.api.health import _check_pico_sensor

        with patch(
            "rpi.server.api.health.get_latest_pico_data",
            new_callable=AsyncMock,
            return_value=[],
        ):
            ok, status = await _check_pico_sensor()

        assert ok is False
        assert status == "no data"


class TestCheckRedis:
    """Tests for _check_redis helper."""

    @pytest.mark.asyncio
    async def test_returns_true_when_redis_accessible(self):
        """Should return True when Redis ping succeeds."""
        from rpi.server.api.health import _check_redis

        with patch("rpi.server.api.health.redis.from_url") as mock_redis:
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock(return_value=True)
            mock_redis.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_redis.return_value.__aexit__ = AsyncMock(return_value=None)

            ok, status = await _check_redis()

        assert ok is True
        assert status == "ok"

    @pytest.mark.asyncio
    async def test_returns_false_on_redis_error(self):
        """Should return False when Redis ping fails."""
        import redis.asyncio as redis_lib

        from rpi.server.api.health import _check_redis

        with patch(
            "rpi.server.api.health.redis.from_url",
            side_effect=redis_lib.RedisError("Connection refused"),
        ):
            ok, status = await _check_redis()

        assert ok is False
        assert "Connection refused" in status
