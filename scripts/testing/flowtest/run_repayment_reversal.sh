#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/scripts/testing:${PYTHONPATH:-}"
export ACCOUNT_NUMBER="${ACCOUNT_NUMBER:-6004044425}"
export LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-8060160}"
echo "=== flowtest.repayment_reversal ==="
python3 "$ROOT/scripts/testing/flowtest/scenarios/repayment_reversal.py"
