#!/usr/bin/env bash
# Phase 2 — GET APIs for frontend (new DPI fields).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"
demo_load_state
demo_resolve_loan

export ACCOUNT_NUMBER="$LAN"
export JOB_TIME="$DEMO_ANCHOR_MS"
export FORECLOSURE_DATE="$DEMO_FORECLOSURE_MS"

demo_banner "PHASE 2 — Inquiry APIs (demo day $DEMO_ANCHOR_DATE)"
demo_talking_points \
  "getLoanAccountOverviewDetails — dpi_due / overdue / paid in amount_details." \
  "getLoanAccountSummaryDetails — dpi_details block (accrued, overdue, paid)." \
  "getLoanAccountBasicDetails — baseline loan info (no DPI block)."

FAIL=0
for id in accounting.loan_basic dpic.overview_api dpic.summary_api; do
  echo ">>> ntest run $id"
  if ! "$NTEST" run "$id"; then FAIL=1; fi
  echo ""
done

[[ "$FAIL" == "0" ]] || exit 1
echo "=== Phase 2 APIs: PASS ==="
demo_pause
