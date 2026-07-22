#!/usr/bin/env bash
# Sync KG to current multi-repo branch checkout (cache-restore or rebuild).
# Use after: git checkout/switch, sync-branches, or when kg fresh reports STALE.
#
# Usage:
#   scripts/bin/kg-switch.sh           # sync + validate + refresh workspace state
#   scripts/bin/kg-switch.sh --quiet   # stderr only; for git hooks
#   scripts/bin/kg-switch.sh --force   # ignore cache, full rebuild
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
BIN="$ROOT/cursor-bundle/kg/bin"
DATA="$ROOT/cursor-bundle/kg/data"
CACHE="$DATA/cache"
mkdir -p "$ROOT/scripts/scratch/logs"
LOG="$ROOT/scripts/scratch/logs/kg-switch.log"
# Truncate if log grows too large (hygiene)
if [[ -f "$LOG" ]] && [[ $(stat -c%s "$LOG" 2>/dev/null || echo 0) -gt 524288 ]]; then
  : >"$LOG"
fi
QUIET=0
FORCE=0
for a in "$@"; do
  case "$a" in
    --quiet|-q) QUIET=1 ;;
    --force|-f) FORCE=1 ;;
  esac
done

log() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >>"$LOG"
  if [[ "$QUIET" == 0 ]]; then
    echo "$*"
  fi
}

mkdir -p "$DATA/cache" "$ROOT/.cursor"
KEY=$(python3 "$BIN/kg_composite.py" key)
MANIFEST="$CACHE/$KEY.manifest.json"

restore_cache() {
  local key="$1"
  [[ -f "$CACHE/$key.db" ]] || return 1
  cp "$CACHE/$key.db" "$DATA/kg.db"
  cp "$CACHE/$key.jsonl" "$DATA/kg.jsonl" 2>/dev/null || true
  cp "$CACHE/$key.json" "$DATA/stats.json" 2>/dev/null || true
  touch "$DATA/kg.db"
  if ! python3 "$BIN/kg_validate.py" >/dev/null 2>&1; then
    log "cache $key failed validation — removing corrupt cache entry"
    rm -f "$CACHE/$key.db" "$CACHE/$key.jsonl" "$CACHE/$key.json" "$CACHE/$key.manifest.json"
    return 1
  fi
  return 0
}

write_manifest() {
  local key="$1"
  python3 "$BIN/kg_write_manifest.py" "$key" >/dev/null
}

START=$(date +%s)
_TRIGGER="${KG_TELEMETRY_TRIGGER:-manual}"
# Heuristic: checkout hook sets KG_TELEMETRY_TRIGGER=checkout
if [[ "$FORCE" == 0 ]] && restore_cache "$KEY"; then
  ELAPSED=$(( $(date +%s) - START ))
  log "✓ KG cache hit (key $KEY) in ${ELAPSED}s — branch-set matches live checkout"
  bash "$ROOT/.cursor/hooks/kg-write-state.sh" >/dev/null 2>&1 || true
  PYTHONPATH="$ROOT/scripts/lib" python3 -c "
from kg_state_banner import append_telemetry
append_telemetry('hit', float('$ELAPSED'), '$_TRIGGER', key_short='${KEY:0:8}')
" 2>/dev/null || true
  exit 0
fi

log "⟳ KG cache miss (key $KEY) — building for current branch-set…"
_build_args=()
[[ "$FORCE" == 1 ]] && _build_args+=(--force)
if [[ "$QUIET" == 1 ]]; then
  bash "$BIN/build.sh" "${_build_args[@]}" >>"$LOG" 2>&1
else
  bash "$BIN/build.sh" "${_build_args[@]}" 2>&1 | tee -a "$LOG"
fi

_validate_ok=0
if [[ "$QUIET" == 1 ]]; then
  python3 "$BIN/kg_validate.py" >/dev/null 2>&1 && _validate_ok=1
else
  python3 "$BIN/kg_validate.py" && _validate_ok=1
fi
if [[ "$_validate_ok" != 1 ]]; then
  log "FATAL: KG build produced invalid db"
  exit 1
fi

write_manifest "$KEY" 2>/dev/null || true
ELAPSED=$(( $(date +%s) - START ))
log "✓ KG ready (key $KEY) in ${ELAPSED}s"
bash "$ROOT/.cursor/hooks/kg-write-state.sh" >/dev/null 2>&1 || true
PYTHONPATH="$ROOT/scripts/lib" python3 -c "
from kg_state_banner import append_telemetry
append_telemetry('miss', float('$ELAPSED'), '$_TRIGGER', key_short='${KEY:0:8}')
" 2>/dev/null || true
