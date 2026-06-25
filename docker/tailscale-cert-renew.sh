#!/bin/sh
# Renew the Tailscale TLS cert used by nginx and reload it.
# Runs on the HOST (needs the tailscale + docker CLIs), not in the container.
# No-op if Tailscale isn't installed or isn't up.
#
# Tailscale certs last 90 days. Add to the host crontab to renew monthly:
#   0 4 1 * * /path/to/rpi-gardener/docker/tailscale-cert-renew.sh >> /var/log/ts-cert.log 2>&1
set -eu

command -v tailscale >/dev/null 2>&1 || { echo "tailscale not installed, skipping"; exit 0; }

# Self.DNSName is the first DNSName in the status JSON; strip the trailing dot.
# Capture first (don't pipe straight to head) so an early-closed pipe doesn't
# make tailscale print "got an empty response"; ": *" tolerates the JSON spacing.
status=$(tailscale status --json 2>/dev/null) || true
host=$(printf '%s\n' "$status" | grep -oE '"DNSName": *"[^"]+"' | head -1 | cut -d'"' -f4)
host=${host%.}
[ -n "$host" ] || { echo "tailscale not up, skipping"; exit 0; }

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
tailscale cert --cert-file "$tmp/ts.crt" --key-file "$tmp/ts.key" "$host"

# uid 101 = nginx worker; it loads the key lazily (SNI-selected) so must read it.
docker run --rm -v rpi-gardener-certs:/certs -v "$tmp":/in alpine sh -c \
  'cp /in/ts.crt /certs/ && cp /in/ts.key /certs/ &&
   chmod 644 /certs/ts.crt && chmod 600 /certs/ts.key && chown 101:101 /certs/ts.key'

# Reload nginx so it picks up the new cert without dropping connections.
docker compose -f "$(CDPATH= cd "$(dirname "$0")/.." && pwd)/docker-compose.yml" \
  exec -T nginx nginx -s reload

echo "renewed Tailscale cert for $host"
