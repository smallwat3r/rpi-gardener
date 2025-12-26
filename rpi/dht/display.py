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
        """Render a reading on the display."""
        from PIL import Image, ImageDraw, ImageFont

        cfg = get_settings().display
        font = ImageFont.truetype(cfg.font_path, cfg.font_size)

        image = Image.new("1", (cfg.width, cfg.height))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, cfg.width, cfg.height))
        draw.text(
            (cfg.text_x_offset, cfg.text_y_temp),
            f"T: {reading.temperature}",
            font=font,
            fill=255,
        )
        draw.text(
            (cfg.text_x_offset, cfg.text_y_humidity),
            f"H: {reading.humidity}",
            font=font,
            fill=255,
        )
        self._oled.image(image)
        self._oled.show()
