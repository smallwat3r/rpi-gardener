#!/bin/sh
# Sync main.py to the Pico and start it
# This script is run at container startup before services start

PICO_SCRIPT="/app/pico/main.py"
MAX_RETRIES=3
RETRY_DELAY=2

log() {
    echo "[pico-sync] $1"
}

# Detect Pico device (try ttyACM0 first, then ttyACM1)
PICO_DEVICE=""
for dev in /dev/ttyACM0 /dev/ttyACM1; do
    if [ -c "$dev" ]; then
        PICO_DEVICE="$dev"
        break
    fi
done

# Check if Pico is connected
if [ -z "$PICO_DEVICE" ]; then
    log "Pico not found on ttyACM0 or ttyACM1, skipping sync"
    exit 0
fi

# Check if script exists
if [ ! -f "$PICO_SCRIPT" ]; then
    log "Pico script not found at $PICO_SCRIPT, skipping sync"
    exit 0
fi

log "Pico found at $PICO_DEVICE"

# Try to sync with retries (Pico might be busy)
attempt=1
while [ $attempt -le $MAX_RETRIES ]; do
    log "Sync attempt $attempt/$MAX_RETRIES..."

    # Interrupt any running code with soft-reset
    if mpremote connect "$PICO_DEVICE" soft-reset 2>/dev/null; then
        sleep 1

        # Copy main.py to the Pico
        if mpremote connect "$PICO_DEVICE" cp "$PICO_SCRIPT" :main.py 2>/dev/null; then
            log "Copied main.py to Pico"

            # Soft-reset to start the script
            if mpremote connect "$PICO_DEVICE" soft-reset 2>/dev/null; then
                log "Pico restarted successfully"
                exit 0
            fi
        fi
    fi

    log "Attempt $attempt failed, retrying in ${RETRY_DELAY}s..."
    sleep $RETRY_DELAY
    attempt=$((attempt + 1))
done

log "Warning: Failed to sync after $MAX_RETRIES attempts (Pico may still work with existing code)"
exit 0
