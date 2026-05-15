#!/usr/bin/env bash
# Configure origin (fork) and upstream (agessaman) remotes.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

FORK_URL="${FORK_REMOTE_URL:-https://github.com/k0gen/meshcore-bot.git}"
UPSTREAM_URL="${UPSTREAM_REMOTE_URL:-https://github.com/agessaman/meshcore-bot.git}"

if git remote get-url origin &>/dev/null; then
  echo "Setting origin → $FORK_URL"
  git remote set-url origin "$FORK_URL"
else
  echo "Adding origin → $FORK_URL"
  git remote add origin "$FORK_URL"
fi

if git remote get-url upstream &>/dev/null; then
  echo "Setting upstream → $UPSTREAM_URL"
  git remote set-url upstream "$UPSTREAM_URL"
else
  echo "Adding upstream → $UPSTREAM_URL"
  git remote add upstream "$UPSTREAM_URL"
fi

echo ""
git remote -v
echo ""
echo "Fetch upstream:  git fetch upstream"
echo "Sync:            ./scripts/sync-upstream.sh"
