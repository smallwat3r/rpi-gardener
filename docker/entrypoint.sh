#!/bin/sh
set -e

# Fix data directory permissions (for mounted volumes)
if [ -d /app/data ] && id appuser >/dev/null 2>&1; then
    chown -R appuser:appgroup /app/data
fi

# Give appuser the host's gpio and i2c group ids. They differ between
# Raspberry Pi OS images, so read them off the device nodes at start.
for dev in /dev/gpiochip0 /dev/i2c-1; do
    [ -e "$dev" ] || continue
    gid=$(stat -c %g "$dev")
    getent group "$gid" >/dev/null || groupadd --gid "$gid" "hw$gid"
    usermod -aG "$gid" appuser
done

echo "Validating configuration..."
python -c "from rpi.lib.config import get_settings; get_settings()"

echo "Initializing database..."
python -c "
import asyncio
from rpi.lib.db import init_db, close_db

async def setup():
    await init_db()
    await close_db()

asyncio.run(setup())
"

# Fix database file permissions after creation
if [ -d /app/data ] && id appuser >/dev/null 2>&1; then
    chown -R appuser:appgroup /app/data
fi

# Sync main.py to Pico and start it
echo "Syncing Pico..."
/pico-sync.sh

echo "Starting application..."
exec "$@"
