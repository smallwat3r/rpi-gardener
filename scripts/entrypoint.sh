#!/bin/sh
set -e

echo "Initializing database..."
python -c "from rpi.lib.db import init_db; init_db()"
echo "Database initialized successfully"

exec "$@"
