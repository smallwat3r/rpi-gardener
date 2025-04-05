#!/usr/bin/env bash
set -e

screen -ls | grep Detached | cut -d. -f1 | awk '{print $1}' | xargs kill
sudo systemctl start nginx
screen -d -m make polling
screen -d -m sudo make server
