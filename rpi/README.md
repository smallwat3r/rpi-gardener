# RPi

Python code for the Raspberry Pi 4.

## Architecture

Services communicate via Redis pub/sub:

```
DHT Polling ──┐                  ┌── Web Server (WebSocket)
              │                  ├── Notification Service (Gmail/Slack)
              ├── Redis ─────────┼── Humidifier Service (Kasa smart plug)
Pico Reader ──┘                  ├── OLED Service (SSD1306 display)
                                 └── LCD Service (1602A alert display)
```

## Services

### DHT22 Polling Service (`dht/`)

Reads temperature and humidity from the DHT22 sensor every 2 seconds.
Publishes readings to the event bus.

    make polling

### Pico Serial Reader (`pico/`)

Reads soil moisture data from a Pico microcontroller via USB serial.
Parses JSON lines and publishes readings to the event bus.

    make pico

### Web Server (`server/`)

REST API and WebSocket server for the dashboard. Uses Starlette (ASGI).
Subscribes to the event bus for real-time updates.

    make serve       # Development (with hot reload)
    make serve-prod  # Production (Unix socket for Nginx)

### Notification Service (`notifications/`)

Subscribes to alert events and sends notifications via Gmail/Slack.
Runs independently of the web server.

    python -m rpi.notifications

### Humidifier Service (`humidifier/`)

Controls a humidifier via TP-Link Kasa smart plug based on humidity alerts.
Turns on when humidity drops below the threshold,
and turns off when humidity recovers.

    python -m rpi.humidifier

### OLED Service (`oled/`)

Displays temperature and humidity readings on an SSD1306 OLED display (128x64).
Subscribes to DHT reading events and renders the latest values.

    python -m rpi.oled

Example display:
```
  ROOM CLIMATE
22.5°C    55.0%
temp      humid
```

### LCD Service (`lcd/`)

Displays active alerts on a 16x2 character LCD (1602A with I2C backpack).
Shows "All OK" when no alerts are active, or scrolling alert text when
thresholds are exceeded.

    python -m rpi.lcd

Example display:
```
ALERTS: 3
P1 dry | Temp low | Humid high
       ^^^^^^^^^^^^^^^^^^^^^^^^ (scrolling)
```

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Service health check |
| `/api/dashboard` | GET | Dashboard data (JSON) |
| `/api/thresholds` | GET | Configured alert thresholds (JSON) |
| `/api/admin/settings` | GET | Admin settings (requires auth) |
| `/api/admin/settings` | PUT | Update admin settings (requires auth) |
| `/dht/latest` | WS | Real-time DHT22 readings |
| `/pico/latest` | WS | Real-time Pico readings |

## Dashboard Features

The web dashboard displays:

- **Room Climate**: Temperature and humidity charts with min/max threshold lines
- **Soil Moisture**: Per-plant moisture charts with minimum threshold lines
- **Visual Alerts**: Warning badges appear when values exceed thresholds
  - Temperature: "Too hot" / "Too cold"
  - Humidity: "Too humid" / "Too dry"
  - Moisture: "Thirsty"
- **Danger Zones**: Red-shaded areas on charts indicate out-of-range values
