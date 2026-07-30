#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/scripts/testing:${PYTHONPATH:-}"
echo "=== flowtest.w4_midmonth_repay_then_me ==="
python3 "$ROOT/scripts/testing/flowtest/scenarios/w4_midmonth_repay_then_me.py"
