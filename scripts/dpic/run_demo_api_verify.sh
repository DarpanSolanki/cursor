#!/usr/bin/env bash
# Verify DPI-impacted inquiry APIs for the demo LAN (after disburse + EOD).
# Sources scripts/scratch/dpic_demo_state.env when present, or uses env vars.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STATE="${STATE_FILE:-$ROOT/scripts/scratch/dpic_demo_state.env}"
NTEST="$ROOT/scripts/bin/ntest.sh"

if [[ -f "$STATE" ]]; then
  # shellcheck disable=SC1090
  set -a && source "$STATE" && set +a
  echo ">>> Loaded demo state: $STATE"
fi

: "${ACCOUNT_NUMBER:?Set ACCOUNT_NUMBER or run run_qa_demo.sh first}"
export ACCOUNT_NUMBER
export LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-}"
export JOB_TIME="${JOB_TIME:-1781267400000}"
export FORECLOSURE_DATE="${FORECLOSURE_DATE:-$JOB_TIME}"

echo "=== DPIC demo API verify ==="
echo "LAN=$ACCOUNT_NUMBER  loan_account_id=${LOAN_ACCOUNT_ID:-?}  foreclosure_date=$FORECLOSURE_DATE"
echo ""

FAIL=0
run_case() {
  local id="$1"
  if ! "$NTEST" run "$id"; then
    FAIL=1
  fi
  echo ""
}

run_case accounting.loan_basic
run_case dpic.overview_api
run_case dpic.foreclosure_sim

if [[ "$FAIL" != "0" ]]; then
  echo "FAIL: one or more demo API cases failed" >&2
  exit 1
fi

echo "=== Demo API verify: ALL PASS ==="
echo "Foreclosure DPI fields (frontend): billed_dpi + bpd_amount in fetchLoanForeclosureSimulationDetails"
echo "Overview DPI fields: dpi_due_amount / dpi_overdue_amount / dpi_paid_amount in getLoanAccountOverviewDetails"
