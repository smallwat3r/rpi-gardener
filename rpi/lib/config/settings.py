"""Settings models and configuration loading for the RPi Gardener application."""

import os
import re
from functools import cached_property, lru_cache
from typing import Annotated, Any, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    HttpUrl,
    SecretStr,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from rpi.lib.config.constants import HYSTERESIS_MOISTURE
from rpi.lib.config.enums import MeasureName, NotificationBackend

# Type alias for raw plant ID values (used when parsing from Pico data)
type PlantIdValue = int

# Patterns
_PICO_PLANT_ID_PATTERN = re.compile(r"^plant-(\d+)$")

# Spike rejection: max allowed jump to 100% between consecutive readings
# Jumps to 100% larger than this are rejected as sensor errors
_SPIKE_THRESHOLD_MOISTURE = 20.0  # %

# Alert confirmation: consecutive readings required to confirm state change
# Prevents transient sensor errors from triggering alerts
_ALERT_CONFIRMATION_COUNT = 3

# DHT22 sensor physical bounds
DHT22_BOUNDS = {
    MeasureName.TEMPERATURE: (-40, 80),
    MeasureName.HUMIDITY: (0, 100),
}


def _parse_bool(v: Any) -> bool:
    """Parse boolean from string '1'/'0' or actual bool."""
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v == "1"
    return bool(v)


def _parse_hex_int(v: Any) -> int:
    """Parse integer from string, supporting hex format (0x...)."""
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        return int(v, 0)  # base 0 auto-detects hex/octal/decimal
    return int(v)


_BoolFromStr = Annotated[bool, BeforeValidator(_parse_bool)]
_HexInt = Annotated[int, BeforeValidator(_parse_hex_int)]


def _validate_email_or_empty(v: str) -> str:
    """Validate email format, allowing empty string."""
    if not v:
        return v
    from pydantic import validate_email

    validate_email(v)
    return v


def _validate_http_url_or_empty(v: str) -> str:
    """Validate HTTP URL format, allowing empty string."""
    if not v:
        return v
    HttpUrl(v)
    return v


def _detect_pico_port() -> str | None:
    """Auto-detect Pico serial port (ttyACM0 or ttyACM1)."""
    for port in ("/dev/ttyACM0", "/dev/ttyACM1"):
        if os.path.exists(port):
            return port
    return None


_EmailOrEmpty = Annotated[str, AfterValidator(_validate_email_or_empty)]
_HttpUrlOrEmpty = Annotated[str, AfterValidator(_validate_http_url_or_empty)]


class GmailSettings(BaseModel):
    """Gmail notification settings."""

    model_config = ConfigDict(frozen=True)

    sender: str = ""
    recipients: str = ""  # Comma-separated list, validated separately
    username: _EmailOrEmpty = ""
    password: SecretStr = SecretStr("")


class SlackSettings(BaseModel):
    """Slack notification settings."""

    model_config = ConfigDict(frozen=True)

    webhook_url: _HttpUrlOrEmpty = ""


class ThresholdSettings(BaseModel):
    """Sensor threshold settings."""

    model_config = ConfigDict(frozen=True)

    max_temperature: int = 25
    min_temperature: int = 18
    max_humidity: int = 65
    min_humidity: int = 40
    min_moisture: int = 30
    plant_moisture_thresholds: dict[int, int] = {}

    @property
    def moisture_hysteresis(self) -> int:
        """Hysteresis offset for moisture alerts."""
        return HYSTERESIS_MOISTURE

    def get_moisture_threshold(self, plant_id: int) -> int:
        """Get moisture threshold for a plant, falling back to default."""
        return self.plant_moisture_thresholds.get(plant_id, self.min_moisture)


class NotificationSettings(BaseModel):
    """Notification service settings."""

    model_config = ConfigDict(frozen=True)

    enabled: bool = False
    backends: list[NotificationBackend] = []
    gmail: GmailSettings = GmailSettings()
    slack: SlackSettings = SlackSettings()
    max_retries: int = 3
    initial_backoff_sec: int = 2
    timeout_sec: int = 30


class PicoSettings(BaseModel):
    """Pico serial connection settings."""

    model_config = ConfigDict(frozen=True)

    serial_port: str = "/dev/ttyACM0"
    serial_baud: int = 115200
    serial_timeout_sec: float = 30.0
    moisture_min: float = 0.0
    moisture_max: float = 100.0
    plant_id_max_length: int = 64
    spike_threshold: float = _SPIKE_THRESHOLD_MOISTURE


class AlertSettings(BaseModel):
    """Alert behavior settings."""

    model_config = ConfigDict(frozen=True)

    confirmation_count: int = _ALERT_CONFIRMATION_COUNT


class DisplaySettings(BaseModel):
    """OLED display settings."""

    model_config = ConfigDict(frozen=True)

    width: int = 128
    height: int = 64
    font_path: str = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"


class PollingSettings(BaseModel):
    """Polling service settings."""

    model_config = ConfigDict(frozen=True)

    frequency_sec: int = 2


class CleanupSettings(BaseModel):
    """Database cleanup settings (used by cron job)."""

    model_config = ConfigDict(frozen=True)

    retention_days: int = 7


class EventBusSettings(BaseModel):
    """Redis event bus settings."""

    model_config = ConfigDict(frozen=True)

    redis_url: str = "redis://localhost:6379/0"


class HumidifierSettings(BaseModel):
    """Humidifier automation settings (TP-Link Kasa smart plug)."""

    model_config = ConfigDict(frozen=True)

    enabled: bool = False
    host: str = ""  # IP address or hostname of the Kasa smart plug


class OLEDSettings(BaseModel):
    """OLED display service settings."""

    model_config = ConfigDict(frozen=True)

    enabled: bool = False


class LCDSettings(BaseModel):
    """LCD 1602A display settings for alert display."""

    model_config = ConfigDict(frozen=True)

    enabled: bool = False
    i2c_address: int = 0x27  # Common addresses: 0x27 or 0x3F
    cols: int = 16
    rows: int = 2
    scroll_delay_sec: float = 0.3  # Delay between scroll steps


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    db_path: str = "dht.sqlite3"
    db_timeout_sec: float = 30.0

    # Sensors
    mock_sensors: _BoolFromStr = False

    # Thresholds (DHT22 bounds: temp -40 to 80, humidity 0 to 100)
    max_temperature: int = Field(default=25, ge=-40, le=80)
    min_temperature: int = Field(default=18, ge=-40, le=80)
    max_humidity: int = Field(default=65, ge=0, le=100)
    min_humidity: int = Field(default=40, ge=0, le=100)
    min_moisture: int = Field(default=30, ge=0, le=100)
    min_moisture_plant_1: int | None = Field(default=None, ge=0, le=100)
    min_moisture_plant_2: int | None = Field(default=None, ge=0, le=100)
    min_moisture_plant_3: int | None = Field(default=None, ge=0, le=100)

    # Notifications
    enable_notification_service: _BoolFromStr = False
    notification_backends: str = "gmail"
    gmail_sender: str = ""
    gmail_recipients: str = ""  # Comma-separated list
    gmail_username: _EmailOrEmpty = ""
    gmail_password: SecretStr = SecretStr("")
    slack_webhook_url: _HttpUrlOrEmpty = ""
    email_max_retries: int = Field(default=3, ge=0)
    email_initial_backoff_sec: int = Field(default=2, ge=0)
    email_timeout_sec: int = Field(default=30, ge=1)

    # Pico
    pico_serial_port: str = "auto"
    pico_serial_baud: int = Field(default=115200, gt=0)
    pico_serial_timeout_sec: float = Field(default=30.0, gt=0)

    # Cleanup
    retention_days: int = Field(default=7, ge=1)

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Humidifier (Kasa smart plug)
    enable_humidifier: _BoolFromStr = False
    humidifier_host: str = ""

    # OLED display (SSD1306)
    enable_oled: _BoolFromStr = False

    # LCD 1602A display
    enable_lcd: _BoolFromStr = False
    lcd_i2c_address: _HexInt = Field(default=0x27, ge=0x00, le=0x7F)
    lcd_scroll_delay_sec: float = Field(default=0.7, gt=0)

    @cached_property
    def thresholds(self) -> ThresholdSettings:
        """Get threshold settings as nested object."""
        plant_thresholds = {}
        for plant_id, val in [
            (1, self.min_moisture_plant_1),
            (2, self.min_moisture_plant_2),
            (3, self.min_moisture_plant_3),
        ]:
            plant_thresholds[plant_id] = (
                val if val is not None else self.min_moisture
            )
        return ThresholdSettings(
            max_temperature=self.max_temperature,
            min_temperature=self.min_temperature,
            max_humidity=self.max_humidity,
            min_humidity=self.min_humidity,
            min_moisture=self.min_moisture,
            plant_moisture_thresholds=plant_thresholds,
        )

    @cached_property
    def notifications(self) -> NotificationSettings:
        """Get notification settings as nested object."""
        backends = [
            NotificationBackend(b.strip())
            for b in self.notification_backends.split(",")
            if b.strip()
        ]
        return NotificationSettings(
            enabled=self.enable_notification_service,
            backends=backends,
            gmail=GmailSettings(
                sender=self.gmail_sender,
                recipients=self.gmail_recipients,
                username=self.gmail_username,
                password=self.gmail_password,
            ),
            slack=SlackSettings(webhook_url=self.slack_webhook_url),
            max_retries=self.email_max_retries,
            initial_backoff_sec=self.email_initial_backoff_sec,
            timeout_sec=self.email_timeout_sec,
        )

    def _resolve_pico_serial_port(self) -> str:
        """Resolve the Pico serial port, with auto-detection if needed."""
        port = self.pico_serial_port
        if self.mock_sensors:
            return port
        if port != "auto" and os.path.exists(port):
            return port
        detected = _detect_pico_port()
        if detected:
            return detected
        if port == "auto":
            raise RuntimeError(
                "No Pico serial port detected. Set PICO_SERIAL_PORT explicitly."
            )
        return port  # Use configured port even if it doesn't exist yet

    @cached_property
    def pico(self) -> PicoSettings:
        """Get Pico settings as nested object."""
        return PicoSettings(
            serial_port=self._resolve_pico_serial_port(),
            serial_baud=self.pico_serial_baud,
            serial_timeout_sec=self.pico_serial_timeout_sec,
        )

    @cached_property
    def display(self) -> DisplaySettings:
        """Get display settings."""
        return DisplaySettings()

    @cached_property
    def polling(self) -> PollingSettings:
        """Get polling settings."""
        return PollingSettings()

    @cached_property
    def cleanup(self) -> CleanupSettings:
        """Get cleanup settings."""
        return CleanupSettings(retention_days=self.retention_days)

    @cached_property
    def eventbus(self) -> EventBusSettings:
        """Get event bus settings."""
        return EventBusSettings(redis_url=self.redis_url)

    @cached_property
    def humidifier(self) -> HumidifierSettings:
        """Get humidifier automation settings."""
        return HumidifierSettings(
            enabled=self.enable_humidifier,
            host=self.humidifier_host,
        )

    @cached_property
    def oled(self) -> OLEDSettings:
        """Get OLED display settings."""
        return OLEDSettings(enabled=self.enable_oled)

    @cached_property
    def lcd(self) -> LCDSettings:
        """Get LCD display settings."""
        return LCDSettings(
            enabled=self.enable_lcd,
            i2c_address=self.lcd_i2c_address,
            scroll_delay_sec=self.lcd_scroll_delay_sec,
        )

    @cached_property
    def alerts(self) -> AlertSettings:
        """Get alert behavior settings."""
        return AlertSettings()

    @model_validator(mode="after")
    def validate_settings(self) -> Self:
        """Validate cross-field configuration constraints."""
        errors: list[str] = []

        # Cross-field comparisons (individual bounds handled by Field constraints)
        if self.min_temperature >= self.max_temperature:
            errors.append(
                f"MIN_TEMPERATURE ({self.min_temperature}) must be less than "
                f"MAX_TEMPERATURE ({self.max_temperature})"
            )

        if self.min_humidity >= self.max_humidity:
            errors.append(
                f"MIN_HUMIDITY ({self.min_humidity}) must be less than "
                f"MAX_HUMIDITY ({self.max_humidity})"
            )

        # Notification credential checks
        if self.enable_notification_service:
            backends = [
                b.strip()
                for b in self.notification_backends.split(",")
                if b.strip()
            ]

            if NotificationBackend.GMAIL in backends:
                missing = []
                if not self.gmail_sender:
                    missing.append("GMAIL_SENDER")
                if not self.gmail_recipients:
                    missing.append("GMAIL_RECIPIENTS")
                if not self.gmail_username:
                    missing.append("GMAIL_USERNAME")
                if not self.gmail_password.get_secret_value():
                    missing.append("GMAIL_PASSWORD")
                if missing:
                    errors.append(
                        f"Gmail enabled but missing: {', '.join(missing)}"
                    )

            if NotificationBackend.SLACK in backends:
                if not self.slack_webhook_url:
                    errors.append(
                        "Slack enabled but SLACK_WEBHOOK_URL is not set"
                    )

        if errors:
            raise ValueError(
                "Configuration validation failed:\n  - "
                + "\n  - ".join(errors)
            )

        return self


# Settings override for testing - allows injecting custom Settings without
# modifying environment variables or clearing the lru_cache.
_settings_override: Settings | None = None


@lru_cache(maxsize=1)
def _load_settings() -> Settings:
    """Load settings from environment (cached)."""
    return Settings()


def get_settings() -> Settings:
    """Get the global settings instance.

    Returns the test override if set, otherwise loads from environment
    variables (cached after first load). For testing, use set_settings()
    from rpi.lib.config.testing to override.
    """
    if _settings_override is not None:
        return _settings_override
    return _load_settings()


def parse_pico_plant_id(raw_id: str) -> int | None:
    """Parse Pico's 'plant-N' format to integer N. Returns None if invalid."""
    match = _PICO_PLANT_ID_PATTERN.match(raw_id)
    if match:
        return int(match.group(1))
    return None
