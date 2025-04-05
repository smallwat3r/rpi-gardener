#!/usr/bin/env bash
set -e

sudo systemctl start nginx
screen -d -m make polling
screen -d -m sudo make server
