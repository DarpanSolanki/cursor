#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/scripts/testing:${PYTHONPATH:-}"
echo "=== flowtest.w5_quarantine_scale_census ==="
python3 "$ROOT/scripts/testing/flowtest/scenarios/w5_quarantine_scale_census.py"
