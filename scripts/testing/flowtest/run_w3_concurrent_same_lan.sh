#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/scripts/testing:${PYTHONPATH:-}"
echo "=== flowtest.w3_concurrent_same_lan ==="
python3 "$ROOT/scripts/testing/flowtest/scenarios/w3_concurrent_same_lan.py"
