#!/usr/bin/env bash
# Step 3 — EOD on month-end: aggregate DPI accrual GL posting (UD-aligned).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"
demo_load_state
demo_resolve_loan

demo_banner "STEP 3 — Month-end accrual GL posting (EOD $DEMO_MONTH_END_DATE)"
demo_talking_points \
  "dpiAccrualCalculation catches up daily accrual through month-end." \
  "dpiAccrualBooking posts ONE accrual GL on month-end (not daily)." \
  "Customer still not billed — billing is on next EMI ($DEMO_SECOND_EMI_DATE)."

demo_run_eod "$DEMO_MONTH_END_MS" "Calendar month-end"
demo_show_dpi_status
demo_pause
