#!/usr/bin/env bash
# Merge or rebase upstream/main into the current branch.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODE=merge
UPSTREAM_BRANCH="${UPSTREAM_BRANCH:-main}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rebase) MODE=rebase; shift ;;
    --branch) UPSTREAM_BRANCH="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--rebase] [--branch main]"
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

if ! git remote get-url upstream &>/dev/null; then
  echo "No 'upstream' remote. Run: ./scripts/fork-remotes.sh" >&2
  exit 1
fi

CURRENT="$(git branch --show-current)"
echo "Fetching upstream..."
git fetch upstream

echo "Syncing upstream/${UPSTREAM_BRANCH} → ${CURRENT} (${MODE})"
if [[ "$MODE" == "rebase" ]]; then
  git rebase "upstream/${UPSTREAM_BRANCH}"
else
  git merge "upstream/${UPSTREAM_BRANCH}" -m "Merge upstream/${UPSTREAM_BRANCH} into ${CURRENT}"
fi

echo "Done. Push with: git push origin ${CURRENT}"
