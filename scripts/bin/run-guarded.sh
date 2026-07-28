#!/usr/bin/env bash
# Global watchdog wrapper for ship-chain steps — per-step budget + heartbeats.
# Usage: run-guarded.sh --source <label> -- <cmd> [args...]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SOURCE_LABEL=""
STEP_BUDGET=""

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

[[ -n "$SOURCE_LABEL" ]] && echo "→ run-guarded ($SOURCE_LABEL)"

if [[ -z "$STEP_BUDGET" && -n "$SOURCE_LABEL" ]]; then
  STEP_BUDGET="$(python3 "$ROOT/scripts/lib/chain_budgets.py" "$SOURCE_LABEL" 2>/dev/null || echo 300)"
fi
STEP_BUDGET="${STEP_BUDGET:-300}"

_chain_started="${RUN_GUARDED_CHAIN_STARTED:-$(date +%s)}"
export RUN_GUARDED_CHAIN_STARTED="$_chain_started"
_chain_ceiling="${RUN_GUARDED_CHAIN_CEILING:-}"
if [[ -z "$_chain_ceiling" && -n "${SHIP_LOOP_CASES:-}" ]]; then
  _chain_ceiling="$(python3 "$ROOT/scripts/lib/chain_budgets.py" ship-loop-total --case ${SHIP_LOOP_CASES// / --case } 2>/dev/null || echo 5400)"
  export RUN_GUARDED_CHAIN_CEILING="$_chain_ceiling"
fi
if [[ -n "$_chain_ceiling" ]]; then
  _elapsed=$(( $(date +%s) - _chain_started ))
  if [[ "$_elapsed" -ge "$_chain_ceiling" ]]; then
    echo "run-guarded FAIL: chain ceiling ${_chain_ceiling}s exceeded (elapsed=${_elapsed}s) before ${SOURCE_LABEL}" >&2
    exit 124
  fi
fi

if command -v timeout >/dev/null 2>&1; then
  # GNU timeout: kill on expiry; preserve exit 124
  exec timeout --signal=TERM --kill-after=30 "${STEP_BUDGET}s" \
    env RUN_GUARDED_ACTIVE=1 RUN_GUARDED_SOURCE="$SOURCE_LABEL" "$@"
else
  exec env RUN_GUARDED_ACTIVE=1 RUN_GUARDED_SOURCE="$SOURCE_LABEL" "$@"
fi
