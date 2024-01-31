import atexit
from collections import namedtuple

from adafruit_ssd1306 import SSD1306_I2C
from board import SCL, SDA
from busio import I2C
from PIL import Image, ImageDraw, ImageFont

from ._reading import Reading

_ScreenSize = namedtuple("ScreenSize", "w h")
_size = _ScreenSize(128, 64)
_font = ImageFont.truetype(
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 17)


class _Display(SSD1306_I2C):
    def clear(self) -> None:
        self.fill(0)
        self.show()

    def add_text(self, draw: ImageDraw,
                 pos: tuple[int, int], text: str) -> None:
        draw.text(pos, text, font=_font, fill=255)

    def render_reading(self, reading: Reading) -> None:
        image = Image.new("1", _size)
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, _size.w, _size.h))
        self.add_text(draw, (23, 0), f"T: {reading.temperature}")
        self.add_text(draw, (23, 20), f"H: {reading.humidity}")
        self.image(image)
        self.show()


display = _Display(_size.w, _size.h, I2C(SCL, SDA))


@atexit.register
def _clear_display():
    """Hook to clear the display screen when the program exits."""
    display.clear()
