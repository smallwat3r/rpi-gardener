#!/bin/sh
set -e

echo "Validating configuration..."
python -c "from rpi.lib.config import validate_config; validate_config()"

echo "Initializing database..."
python -c "
import asyncio
from rpi.lib.db import init_db, close_async_db

async def main():
    await init_db()
    await close_async_db()

asyncio.run(main())
"

echo "Starting application..."
exec "$@"
