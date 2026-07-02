#!/usr/bin/env bash
# Restore LAN 6004044425 (8060160) DPI API test state after destructive grace/EOD scripts.
# Re-runs EOD chain so overview/summary APIs have billed + accrued DPI fields.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-8060160}"
export JOB_TIME="${JOB_TIME:-1781699400000}"
export COMPILE="${COMPILE:-0}"
bash "$ROOT/scripts/dpic/run_eod_dpi_only.sh"
echo "=== DPI API state restored (loan $LOAN_ACCOUNT_ID) ==="
