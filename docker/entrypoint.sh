#!/bin/sh
set -e

echo "Validating configuration..."
python -c "from rpi.lib.config import validate_config; validate_config()"

echo "Initializing database..."
python -c "from rpi.lib.db import init_db; init_db()"

echo "Starting application..."
exec "$@"
