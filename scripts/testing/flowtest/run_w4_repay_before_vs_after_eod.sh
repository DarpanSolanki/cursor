#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/scripts/testing:${PYTHONPATH:-}"
echo "=== flowtest.w4_repay_before_vs_after_eod ==="
python3 "$ROOT/scripts/testing/flowtest/scenarios/w4_repay_before_vs_after_eod.py"
