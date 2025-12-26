# RPi

Python code for the Raspberry Pi 4.

## Architecture

Services communicate via Redis pub/sub:

```
DHT Polling ──┐                  ┌── Web Server (WebSocket)
              ├── Redis ─────────┤
Pico Reader ──┘                  └── Notification Service (Gmail/Slack)
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

    make serve     # Development (with reload)
    make server    # Production (uvicorn)

### Notification Service (`notifications/`)

Subscribes to alert events and sends notifications via Gmail/Slack.
Runs independently of the web server.

    python -m rpi.notifications

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
| `/alerts` | WS | Real-time threshold alerts |

## Dashboard Features

The web dashboard displays:

- **Room Climate**: Temperature and humidity charts with min/max threshold lines
- **Soil Moisture**: Per-plant moisture charts with minimum threshold lines
- **Visual Alerts**: Warning badges appear when values exceed thresholds
  - Temperature: "Too hot" / "Too cold"
  - Humidity: "Too humid" / "Too dry"
  - Moisture: "Needs water"
- **Danger Zones**: Red-shaded areas on charts indicate out-of-range values
