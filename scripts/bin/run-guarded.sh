#!/usr/bin/env bash
# Global watchdog wrapper for ship-chain steps — per-step budget + heartbeats.
# Usage: run-guarded.sh --source <label> [--budget N] -- <cmd> [args...]
# Emits progress ticks ≤15s to stdout + .cursor/ship-progress.log (silence never >30s).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SOURCE_LABEL=""
STEP_BUDGET=""
PROGRESS_LOG="$ROOT/.cursor/ship-progress.log"

_prog() {
  local line="$1"
  echo "$line"
  mkdir -p "$(dirname "$PROGRESS_LOG")"
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$line" >>"$PROGRESS_LOG"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source)
      SOURCE_LABEL="${2:-}"
      shift 2
      ;;
    --budget)
      STEP_BUDGET="${2:-}"
      shift 2
      ;;
    *)
      break
      ;;
  esac
done

if [[ "${1:-}" != "--" ]]; then
  echo "run-guarded.sh: expected '--' delimiter (source=${SOURCE_LABEL:-unknown})" >&2
  exit 2
fi
shift

[[ -n "$SOURCE_LABEL" ]] && _prog "→ run-guarded ($SOURCE_LABEL)"

if [[ -z "$STEP_BUDGET" && -n "$SOURCE_LABEL" ]]; then
  if [[ "$SOURCE_LABEL" == "ship-loop-gate.sh" ]]; then
    # Outer wrapper: cases not known yet — long ceiling; per-case timeouts live inside.
    STEP_BUDGET="${SHIP_LOOP_OUTER_BUDGET_S:-10800}"
  else
    STEP_BUDGET="$(python3 "$ROOT/scripts/lib/chain_budgets.py" "$SOURCE_LABEL" 2>/dev/null || echo 300)"
  fi
fi
STEP_BUDGET="${STEP_BUDGET:-300}"

_chain_started="${RUN_GUARDED_CHAIN_STARTED:-$(date +%s)}"
export RUN_GUARDED_CHAIN_STARTED="$_chain_started"
_chain_ceiling="${RUN_GUARDED_CHAIN_CEILING:-}"
if [[ -z "$_chain_ceiling" && -n "${SHIP_LOOP_CASES:-}" ]]; then
  # shellcheck disable=SC2086
  _chain_ceiling="$(python3 "$ROOT/scripts/lib/chain_budgets.py" ship-loop-total --case ${SHIP_LOOP_CASES// / --case } 2>/dev/null || echo 5400)"
  export RUN_GUARDED_CHAIN_CEILING="$_chain_ceiling"
fi
if [[ -n "$_chain_ceiling" ]]; then
  _elapsed=$(( $(date +%s) - _chain_started ))
  if [[ "$_elapsed" -ge "$_chain_ceiling" ]]; then
    _prog "run-guarded FAIL: chain ceiling ${_chain_ceiling}s exceeded (elapsed=${_elapsed}s) before ${SOURCE_LABEL}"
    exit 124
  fi
fi

# Run child with 15s heartbeat wrapper (never silent >30s)
_start=$(date +%s)
# Prefer chain ceiling for the full ship-loop wrapper
if [[ "$SOURCE_LABEL" == "ship-loop-gate.sh" && -n "${RUN_GUARDED_CHAIN_CEILING:-}" ]]; then
  STEP_BUDGET="$RUN_GUARDED_CHAIN_CEILING"
elif [[ "$SOURCE_LABEL" == "ship-loop-gate.sh" && -n "${SHIP_LOOP_CASES:-}" ]]; then
  # shellcheck disable=SC2086
  STEP_BUDGET="$(python3 "$ROOT/scripts/lib/chain_budgets.py" ship-loop-total --case ${SHIP_LOOP_CASES// / --case } 2>/dev/null || echo 7200)"
fi
_prog "HEARTBEAT start ${SOURCE_LABEL:-cmd} budget=${STEP_BUDGET}s"
set +e
env RUN_GUARDED_ACTIVE=1 RUN_GUARDED_SOURCE="$SOURCE_LABEL" "$@" &
_child=$!
_last_hb=$_start
while kill -0 "$_child" 2>/dev/null; do
  sleep 1
  _now=$(date +%s)
  _el=$((_now - _start))
  if [[ $((_now - _last_hb)) -ge 15 ]]; then
    _prog "HEARTBEAT still running ${SOURCE_LABEL:-cmd} elapsed=${_el}s budget=${STEP_BUDGET}s"
    _last_hb=$_now
  fi
  if [[ "$_el" -ge "$STEP_BUDGET" ]]; then
    _prog "run-guarded TIMEOUT: ${SOURCE_LABEL:-cmd} exceeded ${STEP_BUDGET}s — killing pid $_child"
    kill -TERM "$_child" 2>/dev/null || true
    sleep 5
    kill -KILL "$_child" 2>/dev/null || true
    wait "$_child" 2>/dev/null || true
    {
      echo "=== TIMEOUT STATE DUMP ${SOURCE_LABEL} ==="
      uptime || true
      ps aux | rg -i 'yb-|java|gradle|ntest|batch' | head -40 || true
      bash "$ROOT/scripts/bin/novopay-logs.sh" snap accounting 2>/dev/null | tail -30 || true
    } | tee -a "$PROGRESS_LOG" >&2
    exit 124
  fi
done
wait "$_child"
_rc=$?
set -e
_el=$(( $(date +%s) - _start ))
_prog "HEARTBEAT done ${SOURCE_LABEL:-cmd} elapsed=${_el}s rc=${_rc}"
exit "$_rc"
