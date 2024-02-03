from datetime import datetime
from sqlite3 import Cursor

from rpi.lib.db import Db, Sql, SqlRow, dict_factory


def get_initial_dht_data(from_time: datetime) -> list[SqlRow]:
    with Db(row_factory=dict_factory) as db:
        return db.query(Sql.from_file("dht_chart.sql"), (from_time,)).fetchall()


def get_latest_dht_data() -> SqlRow:
    with Db(row_factory=dict_factory) as db:
        return db.query(Sql.from_file("dht_latest_recording.sql")).fetchone()


def get_stats_dht_data(from_time: datetime) -> SqlRow:
    with Db(row_factory=dict_factory) as db:
        return db.query(Sql.from_file("dht_stats.sql"), (from_time,)).fetchone()


def _pico_dict_factory(cursor: Cursor, row: tuple) -> SqlRow:
    plant_id, moisture, epoch = row
    return {plant_id: moisture, "epoch": epoch}


def get_initial_pico_data(from_time: datetime) -> list[SqlRow]:
    with Db(row_factory=_pico_dict_factory) as db:
        return db.query(Sql.from_file("pico_chart.sql"), (from_time,)).fetchall()


def get_latest_pico_data() -> SqlRow:
    with Db(row_factory=dict_factory) as db:
        return db.query(Sql.from_file("pico_latest_recording.sql")).fetchall()
