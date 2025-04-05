#!/usr/bin/env bash
set -e

screen -ls | grep Detached | cut -d. -f1 | awk '{print $1}' | xargs kill
make mprestart
screen -d -m make polling
screen -d -m make server
sudo systemctl start nginx
