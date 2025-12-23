#!/usr/bin/env python3
"""Seed the database with dummy data for development."""
import argparse
import random
from datetime import timedelta

from sqlitey import Sql

from rpi.lib.config import PLANT_IDS, db_with_config
from rpi.lib.db import init_db
from rpi.lib.utils import utcnow


def _random_walk(current: float, drift: float, min_val: float, max_val: float) -> float:
    """Generate next value using random walk with bounds."""
    change = random.gauss(0, drift)
    new_val = current + change
    return max(min_val, min(max_val, new_val))


def generate_dht_data(num_records: int, interval: timedelta) -> list[tuple]:
    """Generate realistic DHT sensor readings using random walk."""
    now = utcnow()
    data = []

    temperature = random.uniform(20.0, 23.0)
    humidity = random.uniform(45.0, 55.0)

    for i in range(num_records):
        recording_time = now - (interval * (num_records - 1 - i))
        temperature = _random_walk(temperature, drift=0.15, min_val=15.0, max_val=30.0)
        humidity = _random_walk(humidity, drift=0.3, min_val=30.0, max_val=70.0)
        data.append((round(temperature, 1), round(humidity, 1), recording_time))

    return data


def generate_pico_data(num_records: int, interval: timedelta) -> list[tuple]:
    """Generate realistic Pico moisture readings using random walk."""
    now = utcnow()
    data = []

    moisture = {plant_id: random.uniform(40.0, 70.0) for plant_id in PLANT_IDS}

    for i in range(num_records):
        recording_time = now - (interval * (num_records - 1 - i))
        for plant_id in PLANT_IDS:
            moisture[plant_id] = _random_walk(
                moisture[plant_id], drift=0.5, min_val=10.0, max_val=90.0
            )
            data.append((plant_id, round(moisture[plant_id], 1), recording_time))

    return data


def seed_data(hours: int = 6, clear: bool = False) -> None:
    """Insert dummy sensor data for the past N hours."""
    init_db()

    interval = timedelta(minutes=2)
    num_records = (hours * 60) // 2

    with db_with_config(autocommit=True) as db:
        if clear:
            print("Clearing existing data...")
            db.execute(Sql.raw("DELETE FROM reading"))
            db.execute(Sql.raw("DELETE FROM pico_reading"))

        print(f"Generating {num_records} DHT readings...")
        dht_data = generate_dht_data(num_records, interval)

        print(f"Generating {num_records * len(PLANT_IDS)} Pico readings...")
        pico_data = generate_pico_data(num_records, interval)

        print("Inserting DHT data...")
        db.executemany(Sql.raw("INSERT INTO reading VALUES (?, ?, ?)"), dht_data)

        print("Inserting Pico data...")
        db.executemany(Sql.raw("INSERT INTO pico_reading VALUES (?, ?, ?)"), pico_data)

    print("Done!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed database with dummy data")
    parser.add_argument("-hours", type=int, default=6, help="Hours of data to generate (default: 6)")
    parser.add_argument("-clear", action="store_true", help="Clear existing data before seeding")
    args = parser.parse_args()

    seed_data(hours=args.hours, clear=args.clear)
