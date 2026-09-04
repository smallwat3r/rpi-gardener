#!/bin/sh
# shellcheck disable=SC2029  # $dir in ssh commands is meant to expand locally
# Deploy to the Pi over SSH: provision the host, sync the checkout, then
# rebuild and restart the stack. Usage: scripts/deploy.sh [host]
set -eu

host=${1:-pi@gardener.local}
dir=rpi-gardener  # relative to the login user's home on the Pi
cd "$(dirname "$0")/.."

echo "==> provisioning $host"
ssh "$host" 'sudo sh -s' < scripts/provision.sh

echo "==> syncing code"
rsync -az --delete --exclude .git --exclude-from .gitignore ./ "$host:$dir/"
if [ -f .env ]; then
    rsync -a --ignore-existing .env "$host:$dir/"
fi
ssh "$host" "test -f $dir/.env" || {
    echo "no .env on $host, copy .env.example to $dir/.env there and edit it" >&2
    exit 1
}

echo "==> rebuilding and restarting"
# Build while the old stack keeps serving, then swap. The static volume is
# recreated so nginx serves the freshly built frontend rather than the copy
# Docker kept from the first start.
ssh "$host" "cd $dir \
    && export GPIO_GID=\$(getent group gpio | cut -d: -f3) I2C_GID=\$(getent group i2c | cut -d: -f3) \
    && sudo -E docker compose build \
    && sudo -E docker compose down \
    && sudo docker volume rm -f rpi-gardener-static \
    && sudo -E docker compose up -d"
