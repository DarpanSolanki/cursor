#!/usr/bin/env bash
# Cache-first KG sync — multi-repo branch-set aware (LRU cache per composite key).
#
# Strategy:
#   1. One Python pass decides tier (skip / cases / restore / full) — no redundant git/doctor.
#   2. kg-switch restores from cache when this branch-set was built before (~1s).
#   3. Full build only on cache miss for the current branch-set mix.
#
# Usage:
#   kg-session-sync.sh              # sync only when branch-set or changelog needs it
#   kg-session-sync.sh --fast       # workspaceOpen: skip when key+fresh unchanged (<2s)
#   kg-session-sync.sh --force      # kg-switch --force (ignore cache)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
BIN="$ROOT/cursor-bundle/kg/bin"
FAST=0
FORCE=0
QUIET=0
for a in "$@"; do
  case "$a" in
    --fast|-f) FAST=1 ;;
    --force) FORCE=1 ;;
    --quiet|-q) QUIET=1 ;;
  esac
done

log() { [[ "$QUIET" == 1 ]] || echo "$*"; }
logq() { echo "$*" >>"$ROOT/scripts/scratch/logs/kg-session-sync.log"; }

mkdir -p "$ROOT/.cursor" "$ROOT/scripts/scratch/logs"
START=$(date +%s)

_decision="$("$BIN/kg_session.py" decide $([[ "$FAST" == 1 ]] && echo --fast) 2>/dev/null || echo '{}')"
_tier="$(python3 -c "import json,sys; print(json.loads(sys.argv[1]).get('tier','full'))" "$_decision")"
_action="$(python3 -c "import json,sys; print(json.loads(sys.argv[1]).get('action','kg-switch'))" "$_decision")"
_reason="$(python3 -c "import json,sys; print(json.loads(sys.argv[1]).get('reason',''))" "$_decision")"
_key="$(python3 -c "import json,sys; print(json.loads(sys.argv[1]).get('key','?'))" "$_decision")"
_cache="$(python3 -c "import json,sys; print(json.loads(sys.argv[1]).get('cache_hit',False))" "$_decision")"

if [[ "$FORCE" == 1 ]]; then
  _action="kg-switch"
  _tier="full"
fi

case "$_action" in
  none)
    logq "[$(date -u +%H:%M:%S)] FAST skip key=${_key:0:8} tier=$_tier"
    bash "$ROOT/.cursor/hooks/kg-write-state.sh" >/dev/null 2>&1 || true
    ELAPSED=$(( $(date +%s) - START ))
    PYTHONPATH="$ROOT/scripts/lib" python3 -c "
from kg_state_banner import append_telemetry
append_telemetry('hit', float('$ELAPSED'), 'session', key_short='${_key:0:8}')
" 2>/dev/null || true
    log "KG session: fast skip (branch-set unchanged, ${_key:0:8}…)"
    exit 0
    ;;
  refresh_cases)
    logq "[$(date -u +%H:%M:%S)] CASES key=${_key:0:8} $_reason"
    python3 "$BIN/refresh_cases.py" >>"$ROOT/.cursor/enrichment-sync.log" 2>&1
    rm -f "$ROOT/.cursor/.pending-kg-rebuild"
    python3 "$BIN/kg_session.py" stamp >/dev/null
    bash "$ROOT/.cursor/hooks/kg-write-state.sh" >/dev/null 2>&1 || true
    ELAPSED=$(( $(date +%s) - START ))
    PYTHONPATH="$ROOT/scripts/lib" python3 -c "
from kg_state_banner import append_telemetry
append_telemetry('hit', float('$ELAPSED'), 'session', key_short='${_key:0:8}', note='cases')
" 2>/dev/null || true
    log "KG session: cases refresh ($_reason)"
    ;;
  kg-switch)
    logq "[$(date -u +%H:%M:%S)] $_tier key=${_key:0:8} cache=$_cache $_reason"
    _sw_args=(--quiet)
    [[ "$FORCE" == 1 ]] && _sw_args+=(--force)
    # Tell kg-switch the trigger so telemetry is not double-tagged as checkout
    export KG_TELEMETRY_TRIGGER="${KG_TELEMETRY_TRIGGER:-session}"
    bash "$ROOT/scripts/bin/kg-switch.sh" "${_sw_args[@]}"
    python3 "$BIN/kg_session.py" stamp >/dev/null
    rm -f "$ROOT/.cursor/.pending-kg-rebuild"
    ELAPSED=$(( $(date +%s) - START ))
    if [[ "$_cache" == "True" && "$FORCE" != 1 ]]; then
      log "KG session: cache restore branch-set ${_key:0:8}… (${ELAPSED}s)"
    else
      log "KG session: built branch-set ${_key:0:8}… (${ELAPSED}s)"
    fi
    ;;
  *)
    logq "[$(date -u +%H:%M:%S)] fallback kg-switch"
    export KG_TELEMETRY_TRIGGER="${KG_TELEMETRY_TRIGGER:-session}"
    bash "$ROOT/scripts/bin/kg-switch.sh" --quiet
    python3 "$BIN/kg_session.py" stamp >/dev/null
    bash "$ROOT/.cursor/hooks/kg-write-state.sh" >/dev/null 2>&1 || true
    ;;
esac

exit 0
