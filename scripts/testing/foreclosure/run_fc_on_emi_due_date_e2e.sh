#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/scripts/testing:${ROOT}/scripts/dcf_sanity:${PYTHONPATH:-}"
export ICF_OFFICE_ID="${ICF_OFFICE_ID:-2}"
export DISBURSE_ENTRY="${DISBURSE_ENTRY:-http}"

echo "=== foreclosure.fc_on_emi_due_date ==="
python3 "$ROOT/scripts/testing/foreclosure/fc_on_emi_due_date_e2e.py" "$@"
