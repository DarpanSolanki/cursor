#!/usr/bin/env bash
# Step 4 — EOD on 2nd EMI date: DPI billed to customer (loan_due_details).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"
demo_load_state
demo_resolve_loan

demo_banner "STEP 4 — Customer billing on next EMI (EOD $DEMO_SECOND_EMI_DATE)"
demo_talking_points \
  "DPI for missed May EMI is billed on June EMI date (UD §5.7)." \
  "dpiBilling creates DPI component in loan_due_details + billing GL." \
  "This is what production does before collections / SI presentation."

demo_run_eod "$DEMO_SECOND_EMI_MS" "Next installment due date"
demo_show_dpi_status
demo_pause
