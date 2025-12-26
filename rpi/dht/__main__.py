"""DHT22 polling service entrypoint.

Polls the DHT22 sensor for temperature and humidity readings,
persists them to the database, and triggers alerts when thresholds
are exceeded.

Usage: python -m rpi.dht
"""

from rpi.dht.polling import main

if __name__ == "__main__":
    main()
