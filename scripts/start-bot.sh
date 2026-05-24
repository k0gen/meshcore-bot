#!/usr/bin/env bash
# Start / stop / restart meshcore-bot (background or foreground for launchd).
# No screen — PID file under .run/ or supervised by macOS LaunchAgent.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RUN_DIR="${BOT_RUN_DIR:-$ROOT/.run}"
PIDFILE="$RUN_DIR/meshcore-bot.pid"
SERIAL="${MESHCORE_SERIAL:-/dev/cu.usbserial-0001}"
RELOAD="${BOT_RELOAD:-1}"
LABEL="${MESHCORE_LAUNCHD_LABEL:-com.k0gen.meshcore-bot}"
PYTHON="${BOT_PYTHON:-$ROOT/.venv/bin/python}"
BOT_SCRIPT="$ROOT/meshcore_bot.py"

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

  Start meshcore-bot with caffeinate (prevents idle sleep).

Options:
  --start           Start in background (default)
  --foreground      Run in foreground (for launchd; blocks until exit)
  --stop            Stop bot (and unload launchd service if installed)
  --restart         Stop then start (or kickstart launchd job)
  --no-restart      If already running, exit without changes
  --force           Same as --restart when already running
  --status          Show running state and exit
  -h, --help        This help

Environment:
  BOT_RELOAD=0              Same as --no-restart
  MESHCORE_SERIAL           Serial device to check before start
  MESHCORE_LAUNCHD_LABEL    launchd label (default: com.k0gen.meshcore-bot)
  BOT_PYTHON                Python interpreter (default: .venv/bin/python)

macOS auto-start + daily 3:33 restart:
  ./scripts/install-macos-service.sh install
  ./scripts/install-macos-service.sh status
EOF
}

launchd_target() {
  echo "gui/$(id -u)/$LABEL"
}

launchd_loaded() {
  launchctl print "$(launchd_target)" &>/dev/null
}

bot_pids() {
  pgrep -f "[.]venv/bin/python .*meshcore_bot\\.py|[Pp]ython.*meshcore_bot\\.py" 2>/dev/null || true
}

bot_running() {
  [[ -n "$(bot_pids)" ]]
}

read_pidfile() {
  if [[ -f "$PIDFILE" ]]; then
    cat "$PIDFILE" 2>/dev/null || true
  fi
}

pidfile_running() {
  local pid
  pid="$(read_pidfile)"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

stop_bot() {
  echo "Stopping meshcore-bot..."
  if launchd_loaded; then
    launchctl bootout "$(launchd_target)" 2>/dev/null || true
    sleep 2
  fi
  if pidfile_running; then
    kill "$(read_pidfile)" 2>/dev/null || true
    sleep 2
  fi
  if bot_running; then
    kill $(bot_pids) 2>/dev/null || true
    sleep 2
    if bot_running; then
      echo "  Force kill..."
      kill -9 $(bot_pids) 2>/dev/null || true
      sleep 1
    fi
  fi
  rm -f "$PIDFILE"
}

check_serial() {
  if [[ ! -e "$SERIAL" ]]; then
    echo "Warning: serial device not found: $SERIAL" >&2
    echo "  Check USB and config.ini [Connection] serial_port" >&2
  fi
}

check_python() {
  if [[ ! -x "$PYTHON" ]]; then
    echo "ERROR: Python not found: $PYTHON" >&2
    echo "  Create venv: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
    exit 1
  fi
  if [[ ! -f "$BOT_SCRIPT" ]]; then
    echo "ERROR: $BOT_SCRIPT not found" >&2
    exit 1
  fi
}

start_foreground() {
  check_python
  check_serial
  mkdir -p "$RUN_DIR"
  echo "Starting meshcore-bot (foreground, PID $$)..."
  exec caffeinate -i "$PYTHON" "$BOT_SCRIPT"
}

start_background() {
  check_python
  check_serial
  mkdir -p "$RUN_DIR"
  echo "Starting meshcore-bot (background)..."
  # shellcheck disable=SC2091
  nohup caffeinate -i "$PYTHON" "$BOT_SCRIPT" </dev/null >/dev/null 2>&1 &
  local pid=$!
  echo "$pid" >"$PIDFILE"
  disown "$pid" 2>/dev/null || true
  sleep 3
  if kill -0 "$pid" 2>/dev/null; then
    local count
    count=$(bot_pids | wc -l | tr -d ' ')
    if [[ "$count" -gt 1 ]]; then
      echo "WARNING: multiple bot processes: $(bot_pids | tr '\n' ' ')" >&2
    fi
    echo "OK: bot running (PID $pid)"
    echo "Logs: tail -f '$ROOT/meshcore_bot.log'"
    return 0
  fi
  echo "ERROR: bot did not start. Check: tail -50 '$ROOT/meshcore_bot.log'" >&2
  rm -f "$PIDFILE"
  return 1
}

restart_bot() {
  if launchd_loaded; then
    echo "Restarting via launchd ($(launchd_target))..."
    launchctl kickstart -k "$(launchd_target)"
    sleep 3
    if bot_running; then
      echo "OK: bot running (launchd): $(bot_pids | tr '\n' ' ')"
      return 0
    fi
    echo "ERROR: launchd restart failed. Check: launchctl print $(launchd_target)" >&2
    return 1
  fi
  stop_bot
  start_background
}

show_status() {
  if launchd_loaded; then
    echo "LaunchAgent: loaded ($(launchd_target))"
    launchctl print "$(launchd_target)" 2>/dev/null | head -20 || true
  else
    echo "LaunchAgent: not loaded (install: ./scripts/install-macos-service.sh install)"
  fi
  if bot_running; then
    echo "Bot process(es): $(bot_pids | tr '\n' ' ')"
  else
    echo "Bot process: not running"
  fi
  if [[ -f "$PIDFILE" ]]; then
    echo "PID file: $PIDFILE ($(read_pidfile))"
  fi
}

MODE="start"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --start) MODE="start"; shift ;;
    --foreground) MODE="foreground"; shift ;;
    --stop) MODE="stop"; shift ;;
    --restart|--force) MODE="restart"; shift ;;
    --no-restart) RELOAD=0; shift ;;
    --status) show_status; exit 0 ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

case "$MODE" in
  stop)
    stop_bot
    echo "Stopped."
    ;;
  restart)
    restart_bot
    ;;
  foreground)
    if bot_running; then
      echo "Bot already running: $(bot_pids | tr '\n' ' ')" >&2
      exit 1
    fi
    start_foreground
    ;;
  start)
    if launchd_loaded; then
      echo "LaunchAgent is loaded — use: launchctl kickstart $(launchd_target)"
      echo "  Or: $0 --restart   |   ./scripts/install-macos-service.sh restart"
      exit 0
    fi
    if bot_running || pidfile_running; then
      if [[ "$RELOAD" == "1" ]]; then
        echo "Bot already running — reloading..."
        stop_bot
      else
        echo "Bot already running (PID: $(bot_pids | tr '\n' ' '))."
        echo "  Restart: $0 --restart"
        exit 0
      fi
    else
      echo "No running bot found — starting..."
    fi
    start_background
    ;;
esac
