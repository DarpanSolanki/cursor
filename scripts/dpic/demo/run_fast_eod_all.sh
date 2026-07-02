#!/usr/bin/env bash
# One-shot fast forward: all DPI EOD milestones for demo loan (~60-90s total vs 10+ min).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"
demo_load_state
demo_resolve_loan 2>/dev/null || true

: "${LOAN_ACCOUNT_ID:?Set LOAN_ACCOUNT_ID or run step_01_disburse.sh first}"

demo_banner "FAST EOD — all milestones for loan $LOAN_ACCOUNT_ID (${ACCOUNT_NUMBER:-LAN})"

PG=(psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}")
export PGPASSWORD="${PGPASSWORD:-yugabyte}"

echo ">>> Quarantine portfolio (only this loan in DPI calc reader)"
"${PG[@]}" -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/quarantine_dpd_portfolio.sql"

run_milestone() {
  local jt="$1" label="$2" desc="$3" seed="${4:-0}"
  echo ""
  echo ">>> [$desc] $label"
  SEED_CALC_WINDOW="$seed" SYNC_PAST_DUE=1 QUARANTINE_PORTFOLIO=0 \
    JOB_TIME="$jt" LOAN_ACCOUNT_ID="$LOAN_ACCOUNT_ID" \
    bash "$ROOT/scripts/dpic/run_eod_dpi_only.sh"
}

started="$(date +%s)"
run_milestone "$DEMO_FIRST_EMI_PLUS1_MS" "$DEMO_FIRST_EMI_PLUS1_DATE" "accrual starts" 1
run_milestone "$DEMO_MONTH_END_MS" "$DEMO_MONTH_END_DATE" "month-end GL posting" 0
run_milestone "$DEMO_SECOND_EMI_MS" "$DEMO_SECOND_EMI_DATE" "customer billing" 0
run_milestone "$DEMO_ANCHOR_MS" "$DEMO_ANCHOR_DATE" "demo day roll" 0

elapsed=$(( $(date +%s) - started ))
demo_show_dpi_status
echo "FAST EOD complete in ${elapsed}s — loan ${ACCOUNT_NUMBER:-$LOAN_ACCOUNT_ID}"
echo "Optional restore other loans: psql ... -f scripts/dpic/sql/helpers/restore_dpd_portfolio.sql"
