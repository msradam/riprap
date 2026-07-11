#!/usr/bin/env bash
# One-time, foreground: starts the root-owned powermetrics sampler that
# app/power_mac.py tails for real Apple Silicon energy readings.
# Needs a sudo password, so it can't be launched by the app process itself.
#
# Run this once per boot (or wrap it in your own launchd plist as
# UserName=root if you want it survives reboots), then leave it running:
#
#   ./scripts/mac_powermetrics_start.sh &
#   export RIPRAP_POWERMETRICS_LOG=/tmp/riprap-powermetrics.log
#
# Stop with: sudo pkill -f 'powermetrics.*riprap-powermetrics'
set -euo pipefail

LOG_PATH="${RIPRAP_POWERMETRICS_LOG:-/tmp/riprap-powermetrics.log}"

echo "Sampling Combined Power every 200ms to $LOG_PATH (Ctrl-C to stop)"
exec sudo powermetrics -i 200 --samplers cpu_power,gpu_power,ane_power -o "$LOG_PATH"
