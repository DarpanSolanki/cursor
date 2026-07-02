#!/usr/bin/env bash
# Step 2 — EOD on first EMI + 1 day: DPD + DPI accrual calc starts (rows unposted).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"
demo_load_state
demo_resolve_loan

demo_banner "STEP 2 — Accrual starts (EOD $DEMO_FIRST_EMI_PLUS1_DATE)"
demo_talking_points \
  "First EMI ($DEMO_FIRST_EMI_DATE) was missed — loan is overdue." \
  "dpiAccrualCalculation creates daily accrual rows; accrual_posting_date is still NULL." \
  "No customer billing yet."

demo_run_eod "$DEMO_FIRST_EMI_PLUS1_MS" "First EMI + 1 day"
demo_show_dpi_status
demo_pause
