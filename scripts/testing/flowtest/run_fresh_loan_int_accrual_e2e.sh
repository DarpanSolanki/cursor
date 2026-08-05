#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/scripts/testing:${ROOT}/scripts/dcf_sanity:${PYTHONPATH:-}"
export DCF_STACK_SKIP_ACCOUNTING_RESTART="${DCF_STACK_SKIP_ACCOUNTING_RESTART:-1}"
export FLOWTEST_BATCH_TIMEOUT="${FLOWTEST_BATCH_TIMEOUT:-300}"
echo "=== flowtest.fresh_loan_int_accrual_e2e (LAN=${LAN:-unset}) ==="
python3 "$ROOT/scripts/testing/flowtest/scenarios/fresh_loan_int_accrual_e2e.py"
