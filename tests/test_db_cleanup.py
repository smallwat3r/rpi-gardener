"""Tests for the database cleanup module."""

from contextlib import asynccontextmanager
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest

from rpi.cron.db_cleanup import cleanup


@asynccontextmanager
async def mock_transaction():
    """Mock transaction context manager."""
    yield


class TestDatabaseCleanup:
    """Tests for database cleanup functionality."""

    @pytest.mark.asyncio
    async def test_cleanup_skips_when_db_missing(self, tmp_path):
        """Cleanup should skip when database file doesn't exist."""
        db_file = tmp_path / "nonexistent.sqlite3"

        with patch("rpi.cron.db_cleanup.get_settings") as mock_settings:
            mock_settings.return_value.db_path = str(db_file)

            # Should not raise, just log and return
            await cleanup()

    @pytest.mark.asyncio
    async def test_cleanup_deletes_old_data(self, frozen_time, tmp_path):
        """Cleanup should delete records older than retention period."""
        db_file = tmp_path / "test.sqlite3"
        db_file.write_bytes(b"x" * 1000)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                10,  # DHT deleted count
                30,  # Pico deleted count
            ]
        )
        mock_db.fetchone = AsyncMock(
            side_effect=[
                None,  # no retention override in the settings table
                {"auto_vacuum": 2},
            ]
        )
        mock_db.transaction = mock_transaction
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("rpi.cron.db_cleanup.datetime") as mock_dt,
            patch("rpi.cron.db_cleanup.get_settings") as mock_settings,
            patch("rpi.cron.db_cleanup.Database", return_value=mock_db),
        ):
            mock_dt.now.return_value = frozen_time
            mock_settings.return_value.db_path = str(db_file)
            mock_settings.return_value.cleanup.retention_days = 3

            await cleanup()

        # Should delete from both tables
        assert mock_db.execute.call_count == 2

        # Check cutoff epoch (3 days retention) in first delete call
        first_delete = mock_db.execute.call_args_list[0]
        cutoff_epoch = first_delete[0][1][0]
        expected_cutoff = frozen_time - timedelta(days=3)
        assert cutoff_epoch == int(expected_cutoff.timestamp())

        # Vacuum goes through fetchall, the pragma only runs to completion
        # when its rows are read
        assert "incremental_vacuum" in mock_db.fetchall.call_args[0][0]

    @pytest.mark.asyncio
    async def test_cleanup_skips_vacuum_when_no_records(
        self, frozen_time, tmp_path
    ):
        """Cleanup should skip vacuum when no old records exist."""
        db_file = tmp_path / "test.sqlite3"
        db_file.write_bytes(b"x" * 1000)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                0,  # DHT deleted count
                0,  # Pico deleted count
            ]
        )
        mock_db.fetchone = AsyncMock(
            side_effect=[
                None,  # no retention override in the settings table
                {"auto_vacuum": 2},
            ]
        )
        mock_db.transaction = mock_transaction
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("rpi.cron.db_cleanup.datetime") as mock_dt,
            patch("rpi.cron.db_cleanup.get_settings") as mock_settings,
            patch("rpi.cron.db_cleanup.Database", return_value=mock_db),
        ):
            mock_dt.now.return_value = frozen_time
            mock_settings.return_value.db_path = str(db_file)
            mock_settings.return_value.cleanup.retention_days = 3

            await cleanup()

        # Should delete from both tables, but no vacuum
        assert mock_db.execute.call_count == 2
        mock_db.fetchall.assert_not_called()


class TestCleanupAgainstRealDatabase:
    """Uses the temporary database from the test_db fixture."""

    @pytest.mark.asyncio
    async def test_settings_ui_retention_wins_and_file_shrinks(self):
        import sqlite3
        import time
        from pathlib import Path

        from rpi.lib.config import SettingsKey, get_settings

        db_path = Path(get_settings().db_path)
        now = int(time.time())
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, '2')",
            (SettingsKey.RETENTION_DAYS,),
        )
        # Old enough for the 2 day override, not for the 7 day default
        conn.executemany(
            "INSERT INTO reading (temperature, humidity, recording_time)"
            " VALUES (20, 50, ?)",
            [(now - 3 * 86400,)] * 20000,
        )
        conn.execute(
            "INSERT INTO reading (temperature, humidity, recording_time)"
            " VALUES (20, 50, ?)",
            (now,),
        )
        conn.commit()
        conn.close()
        size_before = db_path.stat().st_size

        await cleanup()

        conn = sqlite3.connect(db_path)
        assert conn.execute("SELECT COUNT(*) FROM reading").fetchone()[0] == 1
        assert conn.execute("PRAGMA auto_vacuum").fetchone()[0] == 2
        assert conn.execute("PRAGMA freelist_count").fetchone()[0] == 0
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
        assert db_path.stat().st_size < size_before / 2
