#!/bin/sh
# One-time host setup for the Raspberry Pi. Run as root via sudo, which is
# how `make deploy` streams it over SSH. Safe to re-run: every step checks
# before changing anything.
set -eu

user=${SUDO_USER:?run with sudo}
home=$(getent passwd "$user" | cut -d: -f6)

# I2C for the OLED and LCD displays
if [ "$(raspi-config nonint get_i2c)" != 0 ]; then
    raspi-config nonint do_i2c 0
    echo "enabled i2c"
fi

# Cap the journal and drop swap, both to limit SD card wear
if [ ! -f /etc/systemd/journald.conf.d/sdcard.conf ]; then
    mkdir -p /etc/systemd/journald.conf.d
    printf '[Journal]\nSystemMaxUse=50M\n' > /etc/systemd/journald.conf.d/sdcard.conf
    systemctl restart systemd-journald
    echo "capped journald"
fi
if systemctl is-enabled --quiet dphys-swapfile 2>/dev/null; then
    systemctl disable --now dphys-swapfile
    echo "disabled swap"
fi

# Docker with the compose plugin, from Docker's own install script
if ! command -v docker >/dev/null 2>&1; then
    tmp=$(mktemp)
    curl -fsSL https://get.docker.com -o "$tmp"
    sh "$tmp"
    rm -f "$tmp"
    echo "installed docker"
fi
systemctl enable --now docker
if ! id -nG "$user" | grep -qw docker; then
    usermod -aG docker "$user"
    echo "added $user to docker group (takes effect on next login)"
fi

# Monthly Tailscale cert renewal in root's crontab, a no-op without Tailscale
renew="$home/rpi-gardener/docker/tailscale-cert-renew.sh"
if ! crontab -l 2>/dev/null | grep -qF "$renew"; then
    { crontab -l 2>/dev/null; echo "0 4 1 * * $renew >> /var/log/ts-cert.log 2>&1"; } | crontab -
    echo "scheduled tailscale cert renewal"
fi
