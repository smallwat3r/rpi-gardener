"""OLED display module for rendering sensor readings.

Provides a Display class for rendering temperature and humidity readings
on an SSD1306 OLED display connected via I2C.
"""

from typing import Protocol

from rpi.dht.models import Reading
from rpi.lib.config import get_settings


class DisplayProtocol(Protocol):
    """Protocol for display interface."""

    def clear(self) -> None: ...

    def render_reading(self, reading: Reading) -> None: ...


class Display:
    """OLED display for rendering DHT22 sensor readings."""

    def __init__(self) -> None:
        """Initialize the display with I2C connection."""
        from adafruit_ssd1306 import SSD1306_I2C
        from board import SCL, SDA
        from busio import I2C

        cfg = get_settings().display
        self._oled = SSD1306_I2C(cfg.width, cfg.height, I2C(SCL, SDA))

    def clear(self) -> None:
        """Clear the display."""
        self._oled.fill(0)
        self._oled.show()

    def render_reading(self, reading: Reading) -> None:
        """Render a reading on the display.

        Layout optimized for yellow/blue SSD1306 displays:
        - Yellow zone (top 16px): Header
        - Blue zone (below 16px): Temperature and humidity values
        """
        from PIL import Image, ImageDraw, ImageFont

        cfg = get_settings().display
        image = Image.new("1", (cfg.width, cfg.height))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, cfg.width, cfg.height))

        # Yellow zone: Header (small font)
        header_font = ImageFont.truetype(cfg.font_path, 12)
        draw.text((0, 2), "ROOM CLIMATE", font=header_font, fill=255)

        # Blue zone: Values (larger font)
        value_font = ImageFont.truetype(cfg.font_path, 18)
        draw.text((0, 22), f"{reading.temperature}C", font=value_font, fill=255)
        draw.text((68, 22), f"{reading.humidity}%", font=value_font, fill=255)

        # Labels below values
        label_font = ImageFont.truetype(cfg.font_path, 10)
        draw.text((0, 46), "temp", font=label_font, fill=255)
        draw.text((68, 46), "humid", font=label_font, fill=255)

        self._oled.image(image)
        self._oled.show()
