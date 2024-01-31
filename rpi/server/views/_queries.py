from datetime import datetime

from rpi.lib.db import Db, Sql, SqlRow


def get_initial_dht_data(from_time: datetime) -> list[SqlRow]:
    with Db(dict_row_factory=True) as db:
        return db.query(Sql.from_file("dht_chart.sql"), (from_time,)).fetchall()


def get_latest_dht_data() -> SqlRow:
    with Db(dict_row_factory=True) as db:
        return db.query(Sql.from_file("dht_latest_recording.sql")).fetchone()


def get_stats_dht_data(from_time: datetime) -> SqlRow:
    with Db(dict_row_factory=True) as db:
        return db.query(Sql.from_file("dht_stats.sql"), (from_time,)).fetchone()
