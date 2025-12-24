# RPi

Python code for the Raspberry Pi 4.

## Services

### Polling Service (`dht/`)

Reads temperature and humidity from the DHT22 sensor every 2 seconds.
Handles graceful shutdown on SIGTERM/SIGINT.

    make polling

### Web Server (`server/`)

Web dashboard with real-time charts and REST API. Uses Starlette (ASGI).

    make serve     # Development (with reload)
    make server    # Production (uvicorn)

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard SPA |
| `/health` | GET | Service health check |
| `/api/dashboard` | GET | Dashboard data (JSON) |
| `/api/thresholds` | GET | Configured alert thresholds (JSON) |
| `/pico` | POST | Receive Pico moisture readings |
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
