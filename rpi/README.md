# RPi

Python code for the Raspberry Pi 4.

## Services

### DHT22 Polling Service (`dht/`)

Reads temperature and humidity from the DHT22 sensor every 2 seconds.
Handles graceful shutdown on SIGTERM/SIGINT.

    make polling

### Pico Serial Reader (`pico/`)

Reads soil moisture data from a Pico microcontroller via USB serial.
Parses JSON lines and persists readings to the database.

    make pico

### Web Server (`server/`)

REST API and WebSocket server for the dashboard. Uses Starlette (ASGI).
The frontend SPA is served by NGINX.

    make serve     # Development (with reload)
    make server    # Production (uvicorn)

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Service health check |
| `/api/dashboard` | GET | Dashboard data (JSON) |
| `/api/thresholds` | GET | Configured alert thresholds (JSON) |
| `/dht/latest` | WS | Real-time DHT22 readings |
| `/dht/stats` | WS | Real-time DHT22 statistics |
| `/pico/latest` | WS | Real-time Pico readings |

## Dashboard Features

The web dashboard displays:

- **Room Climate**: Temperature and humidity charts with min/max threshold lines
- **Soil Moisture**: Per-plant moisture charts with minimum threshold lines
- **Visual Alerts**: Warning badges appear when values exceed thresholds
  - Temperature: "Too hot" / "Too cold"
  - Humidity: "Too humid" / "Too dry"
  - Moisture: "Needs water"
- **Danger Zones**: Red-shaded areas on charts indicate out-of-range values
