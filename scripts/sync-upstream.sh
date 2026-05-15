#!/usr/bin/env bash
# Merge upstream into the current branch.
# On main/dev: resets to upstream (mirror). On local-llm: merges upstream/main.
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
      echo "Usage: $0 [--rebase] [--branch main|dev]"
      echo "  On branch main:  reset --hard upstream/main (mirror)"
      echo "  On branch dev:   reset --hard upstream/dev (mirror)"
      echo "  On local-llm:    merge upstream/main into local-llm"
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

mirror_reset() {
  local ref="$1"
  echo "Mirroring ${CURRENT} → ${ref}"
  git reset --hard "$ref"
  echo "Push mirror: git push origin ${CURRENT}"
}

case "$CURRENT" in
  main)
    mirror_reset "upstream/main"
    exit 0
    ;;
  dev)
    mirror_reset "upstream/dev"
    exit 0
    ;;
  local-llm)
    UPSTREAM_BRANCH="${UPSTREAM_BRANCH:-main}"
    echo "Syncing upstream/${UPSTREAM_BRANCH} → local-llm (${MODE})"
    if [[ "$MODE" == "rebase" ]]; then
      git rebase "upstream/${UPSTREAM_BRANCH}"
    else
      git merge "upstream/${UPSTREAM_BRANCH}" -m "Merge upstream/${UPSTREAM_BRANCH} into local-llm"
    fi
    echo "Done. Push: git push origin local-llm"
    exit 0
    ;;
esac

echo "Syncing upstream/${UPSTREAM_BRANCH} → ${CURRENT} (${MODE})"
if [[ "$MODE" == "rebase" ]]; then
  git rebase "upstream/${UPSTREAM_BRANCH}"
else
  git merge "upstream/${UPSTREAM_BRANCH}" -m "Merge upstream/${UPSTREAM_BRANCH} into ${CURRENT}"
fi
echo "Done. Push with: git push origin ${CURRENT}"
