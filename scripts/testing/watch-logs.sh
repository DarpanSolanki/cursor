#!/usr/bin/env bash
# Tail accounting log with error-focused grep (local RCA).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOG="${ACCOUNTING_LOG:-$ROOT/novopay-platform-accounting-v2/logs/mfi/accounting-mfi.log}"
PATTERN="${PATTERN:-ERROR|FATAL|NovopayFatal|writeSkipCount|error_code|Exception}"

if [[ ! -f "$LOG" ]]; then
  echo "Log not found: $LOG" >&2
  echo "Set ACCOUNTING_LOG or start accounting service." >&2
  exit 1
fi

echo "Watching $LOG (pattern: $PATTERN)"
echo "Ctrl-C to stop"
tail -n 50 -f "$LOG" | grep --line-buffered -E "$PATTERN" || true
