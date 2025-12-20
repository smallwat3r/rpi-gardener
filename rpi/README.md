# RPi

Python code for the Raspberry Pi 4.

## Directory Structure

```
rpi/
├── dht/                 # DHT22 sensor polling service
│   ├── polling.py       # Main polling loop, sensor reading
│   └── service.py       # Event queue, threshold auditing
├── display/             # OLED display module
│   └── __init__.py      # SSD1306 display rendering
├── notifications/       # Alert notification system
│   └── __init__.py      # Abstract notifier, Gmail implementation
├── server/              # Flask web server
│   ├── api/             # REST API endpoints
│   │   ├── health.py    # GET /health - service health check
│   │   └── pico.py      # POST /pico - receive Pico readings
│   ├── views/           # Web UI routes
│   │   └── dashboard.py # Main dashboard
│   ├── websockets.py    # Real-time data via WebSocket
│   ├── static/          # JS, CSS assets
│   └── templates/       # Jinja2 HTML templates
└── lib/                 # Shared library code
    ├── config.py        # Centralized configuration
    ├── db.py            # Database queries
    ├── reading.py       # Data models
    └── sql/             # SQL templates
```

## Services

### Polling Service (`dht/`)

Reads temperature and humidity from the DHT22 sensor every 2 seconds.
Handles graceful shutdown on SIGTERM/SIGINT.

    make polling

### Flask Server (`server/`)

Web dashboard with real-time charts and REST API.

    make flask      # Development
    make server     # Production (Gunicorn)

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard with sensor charts |
| `/health` | GET | Service health check |
| `/pico` | POST | Receive Pico moisture readings |
| `/dht/latest` | WS | Real-time DHT22 readings |
| `/dht/stats` | WS | Real-time DHT22 statistics |
| `/pico/latest` | WS | Real-time Pico readings |
