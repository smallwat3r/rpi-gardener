# Pico

This module uses MicroPython and needs to be set up on the Raspberry Pico
board, to read values from capacitive soil moisture sensors (v1.2).

## Features

- Reads moisture levels from up to 3 capacitive soil sensors
- Sends readings to the RPi server via HTTP
- Displays readings on an SSD1306 OLED display
- Auto-reconnects to WiFi if connection drops
- Handles HTTP errors gracefully without crashing

## Installation

Install the `main.py` file onto the Pico.

From the RPi, install the requirements:

    make mpdeps

Use `mpremote` to connect remotely to the Pico and install the `ssd1306`
lib.

    mpremote a0
    mpremote mip install ssd1306

Create a `secrets.py` file on the Pico, in the same directory as the
`main.py` file. This file needs to contain secret values in order to
communicate with the main RPi.

```python
SSID = "<ssid name>"
SSID_PASSWORD = "<ssid password>"
RPI_HOST = "http://192.168.1.XXX"
```

## Configuration

The following constants can be adjusted in `main.py`:

| Constant | Default | Description |
|----------|---------|-------------|
| `POLLING_INTERVAL_SEC` | 2 | Seconds between sensor readings |
| `WIFI_CONNECT_TIMEOUT_SEC` | 10 | WiFi connection timeout |
| `HTTP_TIMEOUT_SEC` | 10 | HTTP request timeout |

Plant calibration values may need adjustment based on your sensors:

```python
plants = (
    Plant("plant-1", ADC(Pin(26)), Calibration(15600, 43500)),
    Plant("plant-2", ADC(Pin(27)), Calibration(15600, 43500)),
    Plant("plant-3", ADC(Pin(28)), Calibration(14500, 44000)),
)
```

## Useful Commands

Edit a file directly on the Pico:

    make mpedit file=<file>

Restart the main script on the Pico:

    make mprestart

## Troubleshooting

**Pico stops sending data**: The Pico can sometimes lose sync. A cron job
on the RPi can restart it periodically:

    0 */3 * * * (cd /home/pi/rpi-gardener && make mprestart)

**WiFi connection issues**: Check the serial output for connection status.
The Pico will print its IP address on successful connection.

**Incorrect moisture readings**: Calibration values vary by sensor.
Submerge sensor in water (100%) and dry air (0%) to determine min/max.
