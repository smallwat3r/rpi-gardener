"""OLED display module for rendering sensor readings.

Provides a Display class for rendering temperature and humidity readings
on an SSD1306 OLED display connected via I2C.
"""

from typing import Protocol, Self

from rpi.lib.config import Unit, get_settings


class DisplayProtocol(Protocol):
    """Protocol for OLED display interface."""

    def clear(self) -> None: ...

    def render(self, temperature: float, humidity: float) -> None: ...

    def close(self) -> None: ...

    def __enter__(self) -> Self: ...

    def __exit__(self, *_: object) -> None: ...


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

    def render(self, temperature: float, humidity: float) -> None:
        """Render temperature and humidity on the display.

        Layout optimized for yellow/blue SSD1306 displays:
        - Yellow zone (top 16px): Header
        - Blue zone (below 16px): Temperature and humidity values
        """
        from PIL import Image, ImageDraw, ImageFont

        cfg = get_settings().display
        bold_font_path = cfg.font_path.replace(".ttf", "-Bold.ttf")
        image = Image.new("1", (cfg.width, cfg.height))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, cfg.width, cfg.height))

        # Yellow zone: Header (bold, centered)
        header_font = ImageFont.truetype(bold_font_path, 12)
        header_text = "ROOM CLIMATE"
        header_bbox = draw.textbbox((0, 0), header_text, font=header_font)
        header_width = header_bbox[2] - header_bbox[0]
        header_x = (cfg.width - header_width) // 2
        draw.text((header_x, 2), header_text, font=header_font, fill=255)

        # Blue zone: Values (larger font, spaced apart)
        value_font = ImageFont.truetype(cfg.font_path, 16)
        temp_str = f"{temperature}{Unit.CELSIUS}"
        humid_str = f"{humidity}{Unit.PERCENT}"
        draw.text((0, 24), temp_str, font=value_font, fill=255)
        draw.text((70, 24), humid_str, font=value_font, fill=255)

        # Labels below values
        label_font = ImageFont.truetype(cfg.font_path, 10)
        draw.text((0, 46), "temp", font=label_font, fill=255)
        draw.text((70, 46), "humid", font=label_font, fill=255)

        self._oled.image(image)
        self._oled.show()

    def close(self) -> None:
        """Close the display."""
        self.clear()

    def __enter__(self) -> Self:
        """Enter context manager."""
        self.clear()  # Ensure clean state before rendering
        return self

    def __exit__(self, *_: object) -> None:
        """Exit context manager."""
        self.close()
