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
    if git fetch upstream --prune >/dev/null 2>&1; then
      # Keep branch_train.fetch_age_hours honest — raw git fetch alone left
      # .git/novopay-upstream-fetch.stamp stale and blocked fixed-elsewhere (TDPQA-207).
      python3 -c "import time,pathlib; pathlib.Path(r'''$d/.git/novopay-upstream-fetch.stamp''').write_text(f'{time.time():.3f}\n')"
    else
      log "  WARN $repo: upstream fetch failed"
    fi
  fi
  log "  ✓ $repo"
  cd "$ROOT"
done

python3 "$ROOT/scripts/bin/git_workspace.py" status --write >/dev/null 2>&1 || true
log "Git fetch complete — state: .cursor/git-workspace-state.json"
