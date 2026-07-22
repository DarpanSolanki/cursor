#!/usr/bin/env bash
# Fetch origin + upstream for all service repos (no checkout/rebase). Updates workspace state.
#
# Usage:
#   git-fetch-all.sh              # fetch all
#   git-fetch-all.sh --quiet
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
QUIET=0
[[ "${1:-}" == "--quiet" || "${1:-}" == "-q" ]] && QUIET=1

log() { [[ "$QUIET" == 1 ]] || echo "$*"; }

for d in "$ROOT"/novopay-* "$ROOT"/trustt-*; do
  [[ -d "$d/.git" ]] || continue
  repo=$(basename "$d")
  case "$repo" in
    trustt-platform-simulators) continue ;;
  esac
  cd "$d"
  if git remote | grep -qx origin; then
    git fetch origin --prune >/dev/null 2>&1 || log "  WARN $repo: origin fetch failed"
  fi
  if git remote | grep -qx upstream; then
    git fetch upstream --prune >/dev/null 2>&1 || log "  WARN $repo: upstream fetch failed"
  fi
  log "  ✓ $repo"
  cd "$ROOT"
done

python3 "$ROOT/scripts/bin/git_workspace.py" status --write >/dev/null 2>&1 || true
log "Git fetch complete — state: .cursor/git-workspace-state.json"
