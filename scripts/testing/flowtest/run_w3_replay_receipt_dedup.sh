#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/scripts/testing:${PYTHONPATH:-}"
echo "=== flowtest.w3_replay_receipt_dedup ==="
python3 "$ROOT/scripts/testing/flowtest/scenarios/w3_replay_receipt_dedup.py"
