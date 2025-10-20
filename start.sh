#!/usr/bin/env bash
set -e

screen -ls | cut -d. -f1 | awk '{print $1}' | xargs kill >/dev/null 2>&1 || echo
make mprestart
screen -dS polling -m make polling
screen -dS server -m make server
sudo systemctl start nginx
