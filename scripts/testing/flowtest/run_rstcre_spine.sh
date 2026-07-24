#!/usr/bin/env bash
# F1 pilot — RSTCRE spine (childLoanEventProcessingBatchJob).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/scripts/testing:${ROOT}/scripts/dcf_sanity:${PYTHONPATH:-}"
export DCF_STACK_SKIP_ACCOUNTING_RESTART="${DCF_STACK_SKIP_ACCOUNTING_RESTART:-1}"
export SEED_EXTRA="${SEED_EXTRA:-0}"
export DCF_SEED_EMI_LABD="${DCF_SEED_EMI_LABD:-0}"
export ACCEPTANCE_STRICT="${ACCEPTANCE_STRICT:-1}"
echo "=== flowtest.rstcre_spine ==="
python3 "$ROOT/scripts/testing/flowtest/scenarios/rstcre_spine.py"
