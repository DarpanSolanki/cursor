#!/usr/bin/env bash
# Step 4b — EOD on presentation anchor: advance business date to demo day.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"
demo_load_state
demo_resolve_loan

demo_banner "STEP 4b — Demo day business date (EOD $DEMO_ANCHOR_DATE)"
demo_talking_points \
  "Rolls system business date to presentation day so DPI overdue and foreclosure sim match QA narrative." \
  "On 15-Jun: DPI billed on 14-Jun shows as overdue; foreclosure_date can equal business date (no Future LPP NPE)."

demo_run_eod "$DEMO_ANCHOR_MS" "Presentation anchor date"
demo_show_dpi_status
demo_pause
