#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/scripts/testing:${ROOT}/scripts/dcf_sanity:${PYTHONPATH:-}"
export DCF_STACK_SKIP_ACCOUNTING_RESTART="${DCF_STACK_SKIP_ACCOUNTING_RESTART:-1}"
export CLEAR_BATCH_FAILURE_AUDIT="${CLEAR_BATCH_FAILURE_AUDIT:-0}"
export FLOWTEST_BATCH_TIMEOUT="${FLOWTEST_BATCH_TIMEOUT:-300}"
echo "=== flowtest.shg_int_accrual_stitch ==="
python3 "$ROOT/scripts/testing/flowtest/scenarios/shg_int_accrual_stitch.py"
