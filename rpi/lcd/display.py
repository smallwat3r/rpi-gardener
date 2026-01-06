"""LCD 1602A display module for showing alert status with scrolling.

Provides a Display class for rendering active alerts on a 16x2 character LCD
connected via I2C (PCF8574 backpack).
"""

from typing import Protocol

from rpi.lib.config import get_settings


class DisplayProtocol(Protocol):
    """Protocol for LCD display interface."""

    def clear(self) -> None: ...

    def show_ok(self) -> None: ...

    def show_alerts(self, alerts: list[str]) -> None: ...

    def scroll_step(self) -> None: ...

    def close(self) -> None: ...


class Display:
    """LCD 1602A display for showing alert status with scrolling."""

    def __init__(self) -> None:
        """Initialize the display with I2C connection."""
        from RPLCD.i2c import CharLCD

        cfg = get_settings().lcd
        self._lcd = CharLCD(
            i2c_expander="PCF8574",
            address=cfg.i2c_address,
            port=1,
            cols=cfg.cols,
            rows=cfg.rows,
        )
        self._cols = cfg.cols
        self._rows = cfg.rows
        self._scroll_text = ""
        self._scroll_pos = 0
        self._alerts: list[str] = []

    def clear(self) -> None:
        """Clear the display."""
        self._lcd.clear()
        self._scroll_text = ""
        self._scroll_pos = 0

    def show_ok(self) -> None:
        """Display 'all ok' status when no alerts are active."""
        self.clear()
        self._lcd.cursor_pos = (0, 0)
        self._lcd.write_string("STATUS".center(self._cols))
        self._lcd.cursor_pos = (1, 0)
        self._lcd.write_string("All OK".center(self._cols))

    def show_alerts(self, alerts: list[str]) -> None:
        """Display alerts with scrolling on line 2.

        Args:
            alerts: List of alert messages to display.
        """
        self._alerts = alerts
        self._scroll_pos = 0

        # Build scroll text: join alerts with separator, add padding for wrap
        separator = " | "
        self._scroll_text = separator.join(alerts)

        # Add padding and repeat for seamless scrolling
        if len(self._scroll_text) > self._cols:
            self._scroll_text += separator

        self._render()

    def _render(self) -> None:
        """Render current state to LCD."""
        self._lcd.cursor_pos = (0, 0)
        alert_count = f"ALERTS: {len(self._alerts)}"
        self._lcd.write_string(alert_count.ljust(self._cols))

        self._lcd.cursor_pos = (1, 0)
        if len(self._scroll_text) <= self._cols:
            # No scrolling needed, center the text
            self._lcd.write_string(self._scroll_text.center(self._cols))
        else:
            # Show scrolling window
            display_text = self._get_scroll_window()
            self._lcd.write_string(display_text)

    def _get_scroll_window(self) -> str:
        """Get the current scroll window of text."""
        # Create seamless wrap by duplicating text
        doubled = self._scroll_text + self._scroll_text
        window = doubled[self._scroll_pos : self._scroll_pos + self._cols]
        return window.ljust(self._cols)

    def scroll_step(self) -> None:
        """Advance the scroll position by one character."""
        if not self._scroll_text or len(self._scroll_text) <= self._cols:
            return

        self._scroll_pos = (self._scroll_pos + 1) % len(self._scroll_text)
        self._render()

    def close(self) -> None:
        """Close the LCD connection."""
        self.clear()
        self._lcd.close()
