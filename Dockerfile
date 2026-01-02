# Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /build
COPY rpi/server/frontend/package*.json ./
RUN npm ci --ignore-scripts
COPY rpi/server/frontend/ ./
RUN npm run build

# Python dependencies
FROM python:3.14-slim-bookworm AS python-builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc python3-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
RUN pip install --no-cache-dir uv
COPY pyproject.toml ./
RUN python -m venv /opt/venv \
    && . /opt/venv/bin/activate \
    && uv pip install --no-cache ".[hardware]" \
    && uv pip install --no-cache supervisor

# Runtime
FROM python:3.14-slim-bookworm AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgpiod2 i2c-tools fonts-dejavu-core tini cron \
    && rm -rf /var/lib/apt/lists/* /root/.cache \
    && find /var/log -type f -delete

# Non-root user with hardware access (GIDs must match host: gpio=993, i2c=994)
RUN groupadd --gid 1000 appgroup \
    && groupadd --gid 993 gpio \
    && (groupmod --gid 994 i2c 2>/dev/null || groupadd --gid 994 i2c) \
    && useradd --uid 1000 --gid appgroup --shell /usr/sbin/nologin --no-create-home appuser \
    && usermod -aG dialout,i2c,gpio appuser

WORKDIR /app
COPY --from=python-builder /opt/venv /opt/venv
COPY --chown=appuser:appgroup rpi/ ./rpi/
RUN mkdir -p ./pico
COPY --chown=appuser:appgroup pico/main.py ./pico/main.py
COPY --from=frontend-builder --chown=appuser:appgroup /static/dist ./rpi/server/static/dist
COPY --chown=root:root docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY --chown=root:root docker/entrypoint.sh /entrypoint.sh
COPY --chown=root:root docker/pico-sync.sh /pico-sync.sh
COPY --chown=root:root docker/crontab /etc/cron.d/db-cleanup
RUN chmod 755 /entrypoint.sh /pico-sync.sh \
    && chmod 644 /etc/cron.d/db-cleanup \
    && mkdir -p /app/data \
    && chown appuser:appgroup /app/data

# Slim down venv
RUN rm -rf /opt/venv/bin/pip* /opt/venv/bin/wheel* /opt/venv/lib/*/site-packages/pip* \
    && find /opt/venv -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
    && find /opt/venv -type f -name "*.pyc" -delete

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1 \
    PATH="/opt/venv/bin:$PATH" \
    DB_PATH=/app/data/dht.sqlite3

VOLUME ["/app/data", "/tmp"]
ENTRYPOINT ["/usr/bin/tini", "--", "/entrypoint.sh"]
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
