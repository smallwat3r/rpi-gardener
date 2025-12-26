"""Tests for the database cleanup module."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest

from rpi.db_cleanup import cleanup


class TestDatabaseCleanup:
    """Tests for database cleanup functionality."""

    @pytest.mark.asyncio
    async def test_cleanup_skips_when_db_missing(self, tmp_path):
        """Cleanup should skip when database file doesn't exist."""
        db_file = tmp_path / "nonexistent.sqlite3"

        with patch("rpi.db_cleanup.get_settings") as mock_settings:
            mock_settings.return_value.db_path = str(db_file)

            # Should not raise, just log and return
            await cleanup()

    @pytest.mark.asyncio
    async def test_cleanup_deletes_old_data(self, frozen_time, tmp_path):
        """Cleanup should delete records older than retention period."""
        db_file = tmp_path / "test.sqlite3"
        db_file.write_bytes(b"x" * 1000)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.fetchone = AsyncMock(side_effect=[
            {"count": 10},  # DHT count
            {"count": 30},  # Pico count
        ])
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("rpi.db_cleanup.datetime") as mock_dt,
            patch("rpi.db_cleanup.get_settings") as mock_settings,
            patch("rpi.db_cleanup.Database", return_value=mock_db),
        ):
            mock_dt.now.return_value = frozen_time
            mock_settings.return_value.db_path = str(db_file)
            mock_settings.return_value.cleanup.retention_days = 3

            await cleanup()

        # Should count (2 fetchone) + delete from both tables + vacuum (3 execute)
        assert mock_db.fetchone.call_count == 2
        assert mock_db.execute.call_count == 3

        # Check cutoff date (3 days retention) in first delete call
        first_delete = mock_db.execute.call_args_list[0]
        cutoff = first_delete[0][1][0]
        expected_cutoff = frozen_time - timedelta(days=3)
        assert cutoff == expected_cutoff

        # Check vacuum is called
        vacuum_call = mock_db.execute.call_args_list[2]
        assert "incremental_vacuum" in vacuum_call[0][0]

    @pytest.mark.asyncio
    async def test_cleanup_skips_delete_when_no_records(self, frozen_time, tmp_path):
        """Cleanup should skip deletion when no old records exist."""
        db_file = tmp_path / "test.sqlite3"
        db_file.write_bytes(b"x" * 1000)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.fetchone = AsyncMock(side_effect=[
            {"count": 0},  # DHT count
            {"count": 0},  # Pico count
        ])
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("rpi.db_cleanup.datetime") as mock_dt,
            patch("rpi.db_cleanup.get_settings") as mock_settings,
            patch("rpi.db_cleanup.Database", return_value=mock_db),
        ):
            mock_dt.now.return_value = frozen_time
            mock_settings.return_value.db_path = str(db_file)
            mock_settings.return_value.cleanup.retention_days = 3

            await cleanup()

        # Should only count, no delete or vacuum
        assert mock_db.fetchone.call_count == 2
        assert mock_db.execute.call_count == 0
