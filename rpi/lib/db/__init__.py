"""Async database operations for the RPi Gardener application.

This package provides async database operations using aiosqlite for non-blocking
database access throughout the application.

See connection.py for details on connection patterns (persistent vs pooled).
"""

from rpi.lib.db.admin import get_admin_password_hash as get_admin_password_hash
from rpi.lib.db.admin import set_admin_password_hash as set_admin_password_hash
from rpi.lib.db.connection import ConnectionPool as ConnectionPool
from rpi.lib.db.connection import Database as Database
from rpi.lib.db.connection import close_db as close_db
from rpi.lib.db.connection import get_db as get_db
from rpi.lib.db.connection import init_db as init_db
from rpi.lib.db.queries import get_latest_dht_data as get_latest_dht_data
from rpi.lib.db.queries import get_latest_pico_data as get_latest_pico_data
from rpi.lib.db.settings import get_all_settings as get_all_settings
from rpi.lib.db.settings import set_settings_batch as set_settings_batch
from rpi.lib.db.types import DHTReading as DHTReading
from rpi.lib.db.types import PicoReading as PicoReading
from rpi.lib.db.types import SQLParams as SQLParams
