#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/scripts/testing:${PYTHONPATH:-}"
echo "=== flowtest.w3_batch_billing_overlap ==="
python3 "$ROOT/scripts/testing/flowtest/scenarios/w3_batch_billing_overlap.py"
