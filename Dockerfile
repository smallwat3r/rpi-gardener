FROM python:3.12-slim-bookworm

# Install system dependencies for GPIO, I2C, and display
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgpiod2 \
    i2c-tools \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir supervisor

# Create data directory for SQLite database
RUN mkdir -p /app/data

# Copy application code
COPY rpi/ ./rpi/

# Copy supervisor configuration
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DB_PATH=/app/data/dht.sqlite3

# Expose nothing - nginx handles external access via Unix socket
VOLUME ["/app/data", "/tmp"]

CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
