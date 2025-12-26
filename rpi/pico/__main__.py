"""Pico serial reader entrypoint.

Reads moisture sensor data from the Raspberry Pi Pico via USB serial,
persists readings to the database, and triggers alerts when plants
need watering.

Usage: python -m rpi.pico
"""

from rpi.pico.reader import main

if __name__ == "__main__":
    main()
