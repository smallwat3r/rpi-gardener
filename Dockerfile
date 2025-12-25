FROM node:20-alpine AS frontend-builder
WORKDIR /app/rpi/server/frontend
COPY rpi/server/frontend/package*.json ./
RUN npm ci
COPY rpi/server/frontend/ ./
RUN npm run build

FROM python:3.14-slim-bookworm

# Install system dependencies for GPIO, I2C, display, and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgpiod2 \
    i2c-tools \
    fonts-dejavu-core \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv and Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir uv \
    && uv pip install --system --no-cache ".[hardware]" \
    && uv pip install --system --no-cache supervisor

# Create data directory for SQLite database
RUN mkdir -p /app/data

# Copy application code
COPY rpi/ ./rpi/

# Copy frontend build from builder stage
COPY --from=frontend-builder /app/rpi/server/static/dist ./rpi/server/static/dist

# Copy supervisor configuration and entrypoint
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DB_PATH=/app/data/dht.sqlite3

# Expose nothing - nginx handles external access via Unix socket
VOLUME ["/app/data", "/tmp"]

ENTRYPOINT ["/entrypoint.sh"]
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
