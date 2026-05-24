#!/usr/bin/env bash
# Install meshcore-bot as a user LaunchAgent (recommended for USB serial).
# Main job: start at login, KeepAlive on crash.
# Second job: daily restart at 03:33.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="${MESHCORE_LAUNCHD_LABEL:-com.k0gen.meshcore-bot}"
RESTART_LABEL="${LABEL}.daily-restart"
SERIAL="${MESHCORE_SERIAL:-/dev/cu.usbserial-0001}"
AGENTS_DIR="${HOME}/Library/LaunchAgents"
MAIN_PLIST="${AGENTS_DIR}/${LABEL}.plist"
RESTART_PLIST="${AGENTS_DIR}/${RESTART_LABEL}.plist"
TARGET="gui/$(id -u)"
START_BOT="${ROOT}/scripts/start-bot.sh"

usage() {
  cat <<EOF
Usage: $(basename "$0") <command>

Commands:
  install     Install LaunchAgents (boot at login + daily 3:33 restart)
  uninstall   Remove LaunchAgents and stop bot
  restart     kickstart -k main service
  status      launchctl + bot process status

Note: Uses ~/Library/LaunchAgents (runs as your user — required for USB serial).
      For true system LaunchDaemons (/Library/LaunchDaemons) use root + adjust paths.

Edit schedule: ${RESTART_PLIST} (StartCalendarInterval Hour/Minute)
EOF
}

write_main_plist() {
  cat >"$MAIN_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${START_BOT}</string>
    <string>--foreground</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${ROOT}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ProcessType</key>
  <string>Background</string>
  <key>StandardOutPath</key>
  <string>${ROOT}/.run/launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>${ROOT}/.run/launchd.err.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>MESHCORE_SERIAL</key>
    <string>${SERIAL}</string>
    <key>MESHCORE_LAUNCHD_LABEL</key>
    <string>${LABEL}</string>
  </dict>
</dict>
</plist>
EOF
}

write_restart_plist() {
  cat >"$RESTART_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${RESTART_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${START_BOT}</string>
    <string>--restart</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${ROOT}</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>3</integer>
    <key>Minute</key>
    <integer>33</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>${ROOT}/.run/restart.out.log</string>
  <key>StandardErrorPath</key>
  <string>${ROOT}/.run/restart.err.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>MESHCORE_LAUNCHD_LABEL</key>
    <string>${LABEL}</string>
  </dict>
</dict>
</plist>
EOF
}

loaded() {
  launchctl print "${TARGET}/${1}" &>/dev/null
}

bootout_if_loaded() {
  local lbl=$1
  if loaded "$lbl"; then
    launchctl bootout "${TARGET}/${lbl}" 2>/dev/null || true
    sleep 1
  fi
}

cmd_install() {
  mkdir -p "${ROOT}/.run" "${AGENTS_DIR}"
  chmod +x "${ROOT}/scripts/start-bot.sh"
  # Stop manual/screen instances before handoff to launchd
  "${START_BOT}" --stop 2>/dev/null || true
  write_main_plist
  write_restart_plist
  bootout_if_loaded "$LABEL"
  bootout_if_loaded "$RESTART_LABEL"
  launchctl bootstrap "$TARGET" "$MAIN_PLIST"
  launchctl bootstrap "$TARGET" "$RESTART_PLIST"
  launchctl enable "${TARGET}/${LABEL}"
  launchctl enable "${TARGET}/${RESTART_LABEL}"
  launchctl kickstart "${TARGET}/${LABEL}"
  echo "Installed."
  echo "  Main:    ${MAIN_PLIST}"
  echo "  Restart: ${RESTART_PLIST} (daily 03:33)"
  echo "  Logs:    tail -f ${ROOT}/meshcore_bot.log"
  sleep 2
  "${START_BOT}" --status
}

cmd_uninstall() {
  bootout_if_loaded "$RESTART_LABEL"
  bootout_if_loaded "$LABEL"
  rm -f "$MAIN_PLIST" "$RESTART_PLIST"
  "${START_BOT}" --stop 2>/dev/null || true
  echo "Uninstalled LaunchAgents."
}

cmd_restart() {
  launchctl kickstart -k "${TARGET}/${LABEL}"
}

cmd_status() {
  echo "=== LaunchAgent: ${LABEL} ==="
  if loaded "$LABEL"; then
    launchctl print "${TARGET}/${LABEL}" | head -25
  else
    echo "not loaded"
  fi
  echo ""
  echo "=== Daily restart: ${RESTART_LABEL} ==="
  if loaded "$RESTART_LABEL"; then
    launchctl print "${TARGET}/${RESTART_LABEL}" | head -15
  else
    echo "not loaded"
  fi
  echo ""
  "${START_BOT}" --status
}

[[ $# -ge 1 ]] || { usage; exit 1; }
case "$1" in
  install) cmd_install ;;
  uninstall) cmd_uninstall ;;
  restart) cmd_restart ;;
  status) cmd_status ;;
  -h|--help) usage ;;
  *) echo "Unknown command: $1" >&2; usage; exit 1 ;;
esac
