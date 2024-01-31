# Rpi

In this directory you will find the Python code that is dedicated to run
on the Raspberry Pi. 

The code is splitted in two main services:
- The polling service, which polls data from the DHT22 sensor, and lives in `dht/`
- The Flask web server, which lives in `server/`

The code under `lib/` is library code shared by both services.
