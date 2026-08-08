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
ASSERT_REPO=""
ASSERT_BRANCH=""
for a in "$@"; do
  case "$a" in
    --help|-h)
      sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    --quiet|-q) QUIET=1 ;;
    --force|-f) FORCE=1 ;;
  esac
done
# Optional: --assert-repo NAME --assert-branch TRAIN (after sync; fail if KG watermark mismatches)
_prev=""
for a in "$@"; do
  if [[ "$_prev" == "--assert-repo" ]]; then ASSERT_REPO="$a"; fi
  if [[ "$_prev" == "--assert-branch" ]]; then ASSERT_BRANCH="$a"; fi
  _prev="$a"
done

log() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >>"$LOG"
  if [[ "$QUIET" == 0 ]]; then
    echo "$*"
  fi
}

mkdir -p "$DATA/cache" "$ROOT/.cursor"

# Share build.sh lock: one restore/rebuild at a time. Quiet hooks skip if busy
# (anti-stampede) instead of stacking hundreds of flock waiters.
exec 9>"$DATA/.build.lock"
if command -v flock >/dev/null 2>&1; then
  if [[ "$QUIET" == 1 ]]; then
    if ! flock -n 9; then
      log "skip: another kg-switch/build holds lock (quiet anti-stampede)"
      exit 0
    fi
  else
    flock -w 1800 9 || {
      log "FATAL: could not acquire $DATA/.build.lock (another build running too long)"
      exit 1
    }
  fi
fi

KEY=$(python3 "$BIN/kg_composite.py" key)
MANIFEST="$CACHE/$KEY.manifest.json"

# Atomic install: never truncate live kg.db before the new copy is ready.
_atomic_install() {
  local src="$1" dest="$2"
  local tmp="${dest}.restoring.$$"
  cp "$src" "$tmp"
  mv -f "$tmp" "$dest"
}

restore_cache() {
  local key="$1"
  [[ -f "$CACHE/$key.db" ]] || return 1
  _atomic_install "$CACHE/$key.db" "$DATA/kg.db"
  if [[ -f "$CACHE/$key.jsonl" ]]; then
    _atomic_install "$CACHE/$key.jsonl" "$DATA/kg.jsonl"
  fi
  if [[ -f "$CACHE/$key.json" ]]; then
    _atomic_install "$CACHE/$key.json" "$DATA/stats.json"
  fi
  touch "$DATA/kg.db"
  # Bump cache entry mtime so build.sh / hygiene LRU keeps recently used keys.
  touch "$CACHE/$key.db" "$CACHE/$key.manifest.json" 2>/dev/null || true
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
  if [[ -n "$ASSERT_REPO" && -n "$ASSERT_BRANCH" ]]; then
    if ! python3 "$BIN/kg.py" align --repo "$ASSERT_REPO" --branch "$ASSERT_BRANCH"; then
      log "FATAL: KG watermark not aligned to asserted train (cache hit)"
      exit 2
    fi
  fi
  exit 0
fi

log "⟳ KG cache miss (key $KEY) — building for current branch-set…"
_build_args=()
[[ "$FORCE" == 1 ]] && _build_args+=(--force)
# Parent already holds .build.lock — tell build.sh not to re-acquire (would deadlock).
export KG_BUILD_LOCK_HELD=1
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
# A rebuild without a restamp leaves .kg-composite-key on the old branch set, so every later
# banner reads mismatch_stored=<old> and stays [PROVISIONAL] forever. kg-enrich.sh stamps;
# kg-switch did not.
python3 "$BIN/kg_session.py" stamp >/dev/null 2>&1 || true
ELAPSED=$(( $(date +%s) - START ))
log "✓ KG ready (key $KEY) in ${ELAPSED}s"
bash "$ROOT/.cursor/hooks/kg-write-state.sh" >/dev/null 2>&1 || true
PYTHONPATH="$ROOT/scripts/lib" python3 -c "
from kg_state_banner import append_telemetry
append_telemetry('miss', float('$ELAPSED'), '$_TRIGGER', key_short='${KEY:0:8}')
" 2>/dev/null || true

if [[ -n "$ASSERT_REPO" && -n "$ASSERT_BRANCH" ]]; then
  log "assert: $ASSERT_REPO @ $ASSERT_BRANCH"
  if ! python3 "$BIN/kg.py" align --repo "$ASSERT_REPO" --branch "$ASSERT_BRANCH"; then
    log "FATAL: KG watermark not aligned to asserted train"
    exit 2
  fi
fi
