#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/scripts/testing:${PYTHONPATH:-}"
echo "=== flowtest.w5_skip_poison_among_healthy ==="
python3 "$ROOT/scripts/testing/flowtest/scenarios/w5_skip_poison_among_healthy.py"
