#!/usr/bin/env bash
# Step 1 — Disburse fresh loan (DPI-applicable product), dates aligned to 15-Jun-2026 demo.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"

TS="$(date +%s%3N)"
EXT_REF="${EXT_REF:-DPIC_DEMO_${DEMO_ANCHOR_DATE//-/}_${TS}}"
REQUEST_SCRATCH="$ROOT/scripts/scratch/dpic_demo_disburse_${TS}.json"

demo_banner "STEP 1 — Disburse (ext_ref prefix: $EXT_REF)"
echo "Disburse date:     $DEMO_DISBURSE_DATE"
echo "First EMI:         $DEMO_FIRST_EMI_DATE"
echo "Demo day (anchor): $DEMO_ANCHOR_DATE"
echo ""

python3 - "$ROOT/scripts/dpic/payload/disburse_mft_6367.json" "$REQUEST_SCRATCH" "$EXT_REF" \
  "$DEMO_DISBURSE_MS" "$DEMO_FIRST_EMI_MS" "$DEMO_ANCHOR_MS" <<'PY'
import json, sys, time
from pathlib import Path

src, out, ext_ref, disb_ms, first_emi_ms, anchor_ms = sys.argv[1:7]
crn = str(int(time.time() * 1000))
data = json.loads(Path(src).read_text(encoding="utf-8"))
req = data["request"]
req["disbursement_details"]["external_ref_number"] = ext_ref
req["disbursement_details"]["expected_disbursement_date"] = disb_ms
req["disbursement_details"]["client_reference_number"] = crn
req["repayment_details"]["first_repayment_date"] = first_emi_ms
req["loan_details"]["sanction_date"] = disb_ms
data["headers"]["stan"] = crn
data["headers"]["transmission_datetime"] = anchor_ms
Path(out).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print(f"Payload: {out}")
PY

demo_require_service
REQUEST_FILE="$REQUEST_SCRATCH" bash "$ROOT/scripts/dpic/run_disburse.sh"

demo_resolve_loan
mkdir -p "$(dirname "$STATE_FILE")"
cat >"$STATE_FILE" <<EOF
# DPIC presentation — generated $(date -Iseconds)
DEMO_ANCHOR_DATE=$DEMO_ANCHOR_DATE
EXT_REF=$EXT_REF
ACCOUNT_NUMBER=$LAN
LOAN_ACCOUNT_ID=$LOAN_ACCOUNT_ID
CUSTOMER_ID=$DEMO_CUSTOMER_ID
DEMO_DISBURSE_DATE=$DEMO_DISBURSE_DATE
DEMO_FIRST_EMI_DATE=$DEMO_FIRST_EMI_DATE
DEMO_SECOND_EMI_DATE=$DEMO_SECOND_EMI_DATE
EOF

demo_show_dpi_status
demo_talking_points \
  "Fresh loan disbursed on product with DPI Applicable = Yes." \
  "First EMI is $DEMO_FIRST_EMI_DATE — no DPI yet (not overdue)." \
  "LAN for rest of demo: $LAN"
demo_pause
