# Pico

This module uses MicroPython and needs to be set up on the Raspberry Pico
board, to read values from capacitive soil moisture sensors (v1.2).

## Features

- Reads moisture levels from up to 3 capacitive soil sensors
- Sends readings to the RPi via USB serial (no WiFi required)
- Displays readings on an SSD1306 OLED display

## Installation

Connect the Pico to the RPi via USB cable.

From the RPi, install the requirements:

    make mpdeps

Use `mpremote` to connect to the Pico and install the `ssd1306` lib:

    mpremote a0
    mpremote mip install ssd1306

Copy `main.py` to the Pico:

    mpremote cp pico/main.py :main.py

## Configuration

The following constants can be adjusted in `main.py`:

| Constant | Default | Description |
|----------|---------|-------------|
| `POLLING_INTERVAL_SEC` | 2 | Seconds between sensor readings |

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

**Incorrect moisture readings**: Calibration values vary by sensor.
Submerge sensor in water (100%) and dry air (0%) to determine min/max.

**Serial port not found**: Ensure the Pico is connected via USB and check
that `/dev/ttyACM0` exists on the RPi.
