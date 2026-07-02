#!/usr/bin/env bash
# Phase 2 — GET APIs: show new DPI keys in inquiry responses (~5s).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"
demo_load_state
demo_resolve_loan

export ACCOUNT_NUMBER="$LAN"
export JOB_TIME="$DEMO_ANCHOR_MS"
export FORECLOSURE_DATE="$DEMO_FORECLOSURE_MS"
demo_require_service

demo_banner "PHASE 2 — Inquiry APIs (new DPI response keys)"
demo_talking_points \
  "Overview amount_details — dpi_due / dpi_overdue / dpi_paid / dpi_waived." \
  "Summary dpi_details — accrued, overdue, paid, current_due." \
  "Basic details — unchanged shape (no DPI block)."

demo_show_dpi_api_keys

FAIL=0
if demo_on_or_after_anchor; then
  echo ""
  echo ">>> Assert: dpi_overdue_amount > 0 before repayment"
  demo_assert_api_field_gt getLoanAccountOverviewDetails \
    account_overview_list[0].amount_details.dpi_overdue_amount 0 || FAIL=1
fi

[[ "$FAIL" == "0" ]] || exit 1
echo ""
echo "=== PHASE 2 complete ==="
echo "Next: bash scripts/dpic/demo/run_demo.sh phase3"
demo_pause
