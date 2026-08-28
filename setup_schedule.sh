#!/bin/bash
# Sets up a launchd agent that runs the seat check every 10 minutes for 7 days.
#
# Usage:
#   ./setup_schedule.sh          # install and start the schedule
#   ./setup_schedule.sh stop     # stop and remove the schedule
#
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.courseselection.monitor"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ "$1" = "stop" ]; then
  launchctl unload "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  rm -f "$PROJECT_DIR/.stop_after"
  echo "Schedule stopped and removed."
  exit 0
fi

chmod +x "$PROJECT_DIR/run_check.sh"

# Record the stop date: now + 7 days.
date -v+7d +%s > "$PROJECT_DIR/.stop_after"

mkdir -p "$HOME/Library/LaunchAgents"

cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$PROJECT_DIR/run_check.sh</string>
    </array>
    <key>StartInterval</key>
    <integer>600</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/launchd.out.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/launchd.err.log</string>
</dict>
</plist>
PLISTEOF

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo "Scheduled: checking every 10 minutes for 7 days."
echo "Logs:      $PROJECT_DIR/monitor.log"
echo "Stop with: ./setup_schedule.sh stop"
