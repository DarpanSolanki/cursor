#!/usr/bin/env bash
# Phase 1 — Fresh LAN disburse + fast DPI EOD jobs through demo day (~60–90s).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"

export DEMO_QUIET="${DEMO_QUIET:-1}"
SKIP_SETUP="${SKIP_SETUP:-1}"
started="$(date +%s)"

demo_banner "PHASE 1 — Disburse + DPI jobs (demo day $DEMO_ANCHOR_DATE)"

if [[ "$SKIP_SETUP" != "1" ]]; then
  bash "$ROOT/scripts/dpic/demo/step_00_setup.sh"
fi

TS="$(date +%s%3N)"
EXT_REF="${EXT_REF:-DPIC_DEMO_${DEMO_ANCHOR_DATE//-/}_${TS}}"
REQUEST_SCRATCH="$ROOT/scripts/scratch/dpic_demo_disburse_${TS}.json"

echo ">>> Disburse (fast path) ext_ref=$EXT_REF"
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
PY

python3 "$SCRIPT_DIR/lib/validate_disburse_dates.py" "$DEMO_DISBURSE_MS" "$DEMO_FIRST_EMI_MS"
demo_require_service
REQUEST_FILE="$REQUEST_SCRATCH" bash "$ROOT/scripts/dpic/run_disburse_demo.sh"

demo_resolve_loan
mkdir -p "$(dirname "$STATE_FILE")"
cat >"$STATE_FILE" <<EOF
# DPIC presentation — phase 1 $(date -Iseconds)
DEMO_ANCHOR_DATE=$DEMO_ANCHOR_DATE
EXT_REF=$EXT_REF
ACCOUNT_NUMBER=$LAN
LOAN_ACCOUNT_ID=$LOAN_ACCOUNT_ID
CUSTOMER_ID=$DEMO_CUSTOMER_ID
JOB_TIME=$DEMO_ANCHOR_MS
FORECLOSURE_DATE=$DEMO_FORECLOSURE_MS
DEMO_DISBURSE_DATE=$DEMO_DISBURSE_DATE
DEMO_FIRST_EMI_DATE=$DEMO_FIRST_EMI_DATE
DEMO_SECOND_EMI_DATE=$DEMO_SECOND_EMI_DATE
EOF
export STATE_FILE
demo_sync_registry_correlators

echo ""
echo ">>> Fast EOD (May15 → May31 → Jun14 → Jun15) ..."
eod_start="$(date +%s)"
export DEMO_QUIET=1
bash "$SCRIPT_DIR/run_fast_eod_all.sh" 2>&1 | grep -E '^(>>>|FAST EOD|=== DPI| eligible_loans|FAST EOD complete)' || true
eod_elapsed=$(( $(date +%s) - eod_start ))

elapsed=$(( $(date +%s) - started ))
echo ""
echo "=== PHASE 1 complete in ${elapsed}s (EOD ${eod_elapsed}s) ==="
echo "  LAN:              $LAN"
echo "  loan_account_id:  $LOAN_ACCOUNT_ID"
echo "  state:            $STATE_FILE"
echo ""
echo "Next: bash scripts/dpic/demo/run_demo.sh phase2"
demo_pause
