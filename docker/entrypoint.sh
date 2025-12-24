#!/bin/sh
set -e

echo "Initializing database..."
python -c "from rpi.lib.db import init_db; init_db()"

echo "Starting supervisord..."
exec supervisord -c /etc/supervisor/conf.d/supervisord.conf
