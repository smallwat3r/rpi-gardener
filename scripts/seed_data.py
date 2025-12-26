#!/usr/bin/env python3
"""Seed the database with dummy data for development."""

import argparse
import asyncio
import random
from datetime import UTC, datetime, timedelta

from rpi.lib.config import PlantId
from rpi.lib.db import close_db, get_db, init_db
from rpi.lib.mock import random_walk


def generate_dht_data(
    num_records: int, interval: timedelta
) -> list[tuple[float, float, datetime]]:
    """Generate realistic DHT sensor readings using random walk."""
    now = datetime.now(UTC)
    data = []

    temperature = random.uniform(20.0, 23.0)
    humidity = random.uniform(45.0, 55.0)

    for i in range(num_records):
        recording_time = now - (interval * (num_records - 1 - i))
        temperature = random_walk(
            temperature, drift=0.15, min_val=15.0, max_val=30.0
        )
        humidity = random_walk(humidity, drift=0.3, min_val=30.0, max_val=70.0)
        data.append(
            (round(temperature, 1), round(humidity, 1), recording_time)
        )

    return data


def generate_pico_data(
    num_records: int, interval: timedelta
) -> list[tuple[int, float, datetime]]:
    """Generate realistic Pico moisture readings using random walk."""
    now = datetime.now(UTC)
    data: list[tuple[int, float, datetime]] = []
    plant_ids = list(PlantId)

    moisture = {plant_id: random.uniform(40.0, 70.0) for plant_id in plant_ids}

    for i in range(num_records):
        recording_time = now - (interval * (num_records - 1 - i))
        for plant_id in plant_ids:
            moisture[plant_id] = random_walk(
                moisture[plant_id], drift=0.5, min_val=10.0, max_val=90.0
            )
            data.append(
                (int(plant_id), round(moisture[plant_id], 1), recording_time)
            )

    return data


async def seed_data(hours: int = 6, clear: bool = False) -> None:
    """Insert dummy sensor data for the past N hours."""
    await init_db()

    interval = timedelta(minutes=2)
    num_records = (hours * 60) // 2

    print(f"Generating {num_records} DHT readings...")
    dht_data = generate_dht_data(num_records, interval)

    print(f"Generating {num_records * len(PlantId)} Pico readings...")
    pico_data = generate_pico_data(num_records, interval)

    async with get_db() as db, db.transaction():
        if clear:
            print("Clearing existing data...")
            await db.execute("DELETE FROM reading")
            await db.execute("DELETE FROM pico_reading")

        print("Inserting DHT data...")
        await db.executemany(
            "INSERT INTO reading (temperature, humidity, recording_time) VALUES (?, ?, ?)",
            dht_data,
        )

        print("Inserting Pico data...")
        await db.executemany(
            "INSERT INTO pico_reading (plant_id, moisture, recording_time) VALUES (?, ?, ?)",
            pico_data,
        )

    await close_db()
    print("Done!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Seed database with dummy data"
    )
    parser.add_argument(
        "-hours",
        type=int,
        default=24,
        help="Hours of data to generate (default: 24, max: 168 for 7 days)",
    )
    parser.add_argument(
        "-clear",
        action="store_true",
        help="Clear existing data before seeding",
    )
    args = parser.parse_args()

    asyncio.run(seed_data(hours=args.hours, clear=args.clear))
