#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/scripts/testing:${PYTHONPATH:-}"
echo "=== flowtest.w4_reversal_after_billing ==="
python3 "$ROOT/scripts/testing/flowtest/scenarios/w4_reversal_after_billing.py"
