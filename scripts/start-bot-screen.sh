#!/usr/bin/env bash
# Deprecated: use scripts/start-bot.sh (screen removed).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "Note: start-bot-screen.sh is deprecated — using start-bot.sh" >&2
exec "$ROOT/scripts/start-bot.sh" "$@"
