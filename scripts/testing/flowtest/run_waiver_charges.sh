#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/scripts/testing:${ROOT}/scripts/dcf_sanity:${PYTHONPATH:-}"
export DCF_STACK_SKIP_ACCOUNTING_RESTART="${DCF_STACK_SKIP_ACCOUNTING_RESTART:-1}"
echo "=== flowtest.waiver_charges ==="
python3 "$ROOT/scripts/testing/flowtest/scenarios/waiver_charges.py"
