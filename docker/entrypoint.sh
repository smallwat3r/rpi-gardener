#!/bin/sh
set -e

echo "Validating configuration..."
python -c "from rpi.lib.config import validate_config; validate_config()"

echo "Initializing database..."
python -c "
import asyncio
from rpi.lib.db import init_db, close_db

async def setup():
    await init_db()
    await close_db()

asyncio.run(setup())
"

echo "Starting application..."
exec "$@"
