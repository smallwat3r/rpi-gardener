from datetime import datetime
from sqlite3 import Cursor
from rpi.lib.config import DB_CONFIG

from sqlitey import Db, Sql, SqlRow, dict_factory


def get_initial_dht_data(from_time: datetime) -> list[SqlRow]:
    with Db.from_config(DB_CONFIG, row_factory=dict_factory) as db:
        return db.fetchall(Sql.template("dht_chart.sql"), (from_time,))


def get_latest_dht_data() -> SqlRow:
    with Db.from_config(DB_CONFIG, row_factory=dict_factory) as db:
        return db.fetchone(Sql.template("dht_latest_recording.sql"))


def get_stats_dht_data(from_time: datetime) -> SqlRow:
    with Db.from_config(DB_CONFIG, row_factory=dict_factory) as db:
        return db.fetchone(Sql.from_file("dht_stats.sql"), (from_time,))


def _pico_dict_factory(cursor: Cursor, row: tuple) -> SqlRow:
    plant_id, moisture, epoch = row
    return {plant_id: moisture, "epoch": epoch}


def get_initial_pico_data(from_time: datetime) -> list[SqlRow]:
    with Db.from_config(DB_CONFIG, row_factory=_pico_dict_factory) as db:
        return db.fetchall(Sql.template("pico_chart.sql"), (from_time,))


def get_latest_pico_data() -> SqlRow:
    with Db.from_config(DB_CONFIG, row_factory=dict_factory) as db:
        return db.fetchall(Sql.template("pico_latest_recording.sql"))
