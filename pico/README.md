# Pico

This module uses MicroPython and needs to be set up on the Raspberry Pico
board, to read values from capacitive soil moisture sensors (v1.2).

## Features

- Reads moisture levels from up to 3 capacitive soil sensors
- Sends readings to the RPi via USB serial (no WiFi required)
- Displays readings on an SSD1306 OLED display

## Installation

Connect the Pico to the RPi via USB cable.

From the RPi, install the MicroPython tooling:

    make mpdeps

### First-time setup

1. Install MicroPython on the Pico if not already done:
   - Hold BOOTSEL button while plugging in USB
   - Download the `.uf2` file from https://micropython.org/download/RPI_PICO/
   - Copy it to the mounted drive

2. Install the `ssd1306` display library:

       uv run mpremote mip install ssd1306

3. Copy `main.py` to the Pico:

       uv run mpremote cp pico/main.py :main.py

4. Restart the Pico to start the script:

       uv run mpremote soft-reset

5. Verify it's working (should see JSON output every 2 seconds):

       cat /dev/ttyACM0

   Example output:

       {"plant-1": 45.2, "plant-2": 67.8, "plant-3": 52.1}

The script auto-runs on boot, so unplugging and replugging the Pico will
restart it automatically.

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
which device it's on:

    ls /dev/ttyACM*

If it's on `/dev/ttyACM1` instead of `/dev/ttyACM0`, update the device
mapping in `docker-compose.yml`:

```yaml
devices:
  - /dev/ttyACM1:/dev/ttyACM0
```

**mpremote can't connect (raw repl error)**: The Pico is busy running code.
Unplug and replug the USB cable, then quickly run `mpremote` before `main.py`
starts.
