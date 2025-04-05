#!/usr/bin/env bash
set -e

make polling &
sudo make server &
