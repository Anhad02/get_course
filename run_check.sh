#!/bin/bash
# Wrapper that runs a single seat check. Called by launchd every 10 minutes.
# It self-expires after STOP_DATE so it won't run past the intended week.

cd "$(dirname "$0")" || exit 1

# Auto-stop date (epoch seconds). After this time the job unloads itself and
# does nothing. Set by setup_schedule.sh.
STOP_DATE_FILE=".stop_after"
if [ -f "$STOP_DATE_FILE" ]; then
  STOP_AFTER=$(cat "$STOP_DATE_FILE")
  NOW=$(date +%s)
  if [ "$NOW" -ge "$STOP_AFTER" ]; then
    echo "[$(date)] Past stop date; unloading scheduler." >> monitor.log
    launchctl unload "$HOME/Library/LaunchAgents/com.courseselection.monitor.plist" 2>/dev/null
    exit 0
  fi
fi

.venv/bin/python monitor.py --once >> monitor.log 2>&1
