#!/usr/bin/env python3
"""Seed the database with dummy data for development."""
import argparse
import random
from datetime import timedelta

from sqlitey import Sql

from rpi.lib.config import db_with_config
from rpi.lib.db import init_db
from rpi.lib.utils import utcnow

PLANTS = ["plant-1", "plant-2", "plant-3"]


def generate_dht_data(num_records: int, interval: timedelta) -> list[tuple]:
    """Generate DHT sensor readings."""
    now = utcnow()
    data = []
    for i in range(num_records):
        recording_time = now - (interval * (num_records - i))
        temperature = round(20 + random.uniform(-2, 5) + (i % 20) * 0.1, 1)
        humidity = round(50 + random.uniform(-5, 10) + (i % 15) * 0.2, 1)
        data.append((temperature, humidity, recording_time))
    return data


def generate_pico_data(num_records: int, interval: timedelta) -> list[tuple]:
    """Generate Pico moisture readings."""
    now = utcnow()
    data = []
    for i in range(num_records):
        recording_time = now - (interval * (num_records - i))
        for j, plant_id in enumerate(PLANTS):
            base_moisture = 60 - (j * 15)
            moisture = round(base_moisture + random.uniform(-10, 10) - (i % 30) * 0.3, 1)
            moisture = max(5.0, min(95.0, moisture))
            data.append((plant_id, moisture, recording_time))
    return data


def seed_data(hours: int = 6, clear: bool = False) -> None:
    """Insert dummy sensor data for the past N hours."""
    init_db()

    interval = timedelta(minutes=2)
    num_records = (hours * 60) // 2

    with db_with_config() as db:
        if clear:
            print("Clearing existing data...")
            db.execute(Sql.raw("DELETE FROM reading"))
            db.execute(Sql.raw("DELETE FROM pico_reading"))

        print(f"Generating {num_records} DHT readings...")
        dht_data = generate_dht_data(num_records, interval)

        print(f"Generating {num_records * len(PLANTS)} Pico readings...")
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
