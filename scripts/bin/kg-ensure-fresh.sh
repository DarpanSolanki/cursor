#!/usr/bin/env bash
# Ensure KG matches live multi-repo branch-set before money-path analysis.
# Cache-first: restores prior branch-set snapshot in ~1s when seen before.
#
# Usage:
#   kg-ensure-fresh.sh           # sync if needed; exit 0=fresh, 2=stale
#   kg-ensure-fresh.sh --strict  # sets KG_STRICT=1 on sync failure
#   kg-ensure-fresh.sh --quiet
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
KG="python3 cursor-bundle/kg/bin/kg.py"
QUIET=0
STRICT=0
for a in "$@"; do
  case "$a" in
    --quiet|-q) QUIET=1 ;;
    --strict) STRICT=1 ;;
    --check-only) CHECK_ONLY=1 ;;
  esac
done
CHECK_ONLY="${CHECK_ONLY:-0}"

log() { [[ "$QUIET" == 1 ]] || echo "$*"; }
warn() { echo "$*" >&2; }

if bash scripts/bin/kg-quick-check.sh >/dev/null 2>&1; then
  bash "$ROOT/.cursor/hooks/kg-write-state.sh" >/dev/null 2>&1 || true
  log "KG FRESH (quick-check)"
  exit 0
fi

[[ "$CHECK_ONLY" == 1 ]] && exit 1

log "KG needs sync — cache-first branch-set restore…"
[[ "$STRICT" == 1 ]] && export KG_STRICT=1

if bash scripts/bin/kg-session-sync.sh $([[ "$QUIET" == 1 ]] && echo --quiet); then
  if bash scripts/bin/kg-quick-check.sh >/dev/null 2>&1; then
    log "KG FRESH (after sync)"
    exit 0
  fi
fi

warn "KG still not fresh:"
python3 cursor-bundle/kg/bin/kg_session.py decide 2>/dev/null | head -20 >&2 || true
warn "Try: scripts/bin/kg-session-sync.sh --force"
exit 2
