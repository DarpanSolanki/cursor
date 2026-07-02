#!/usr/bin/env bash
# Fresh disburse → milestone EOD → full DPI column audit (no fixture LAN reuse).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DPIC="$ROOT/scripts/dpic"
# shellcheck disable=SC1091
source "$DPIC/lib/dpi_demo_fixture.sh"

NTEST="$ROOT/scripts/bin/ntest.sh"
WAIT_BATCH="$DPIC/lib/wait_batch_job.sh"
COMPUTE_DATES="$DPIC/demo/lib/compute_dates.py"
VALIDATE_DATES="$DPIC/demo/lib/validate_disburse_dates.py"
ANCHOR_DATE="${ANCHOR_DATE:-$(date +%Y-%m-%d)}"
GRACE_DAYS="${GRACE_DAYS:-3}"
CUSTOMER_ID="${CUSTOMER_ID:-10002233}"
GO_LIVE_DDMM="${GO_LIVE_DDMM:-15-03-2026}"

fail() { echo "FAIL: $*" >&2; exit 1; }

eval "$(python3 "$COMPUTE_DATES" --anchor "$ANCHOR_DATE")"
export CERT_DISBURSE_MS="$DEMO_DISBURSE_MS" CERT_FIRST_EMI_MS="$DEMO_FIRST_EMI_MS"

echo "=== Step 1: compile + ensure accounting ==="
dpi_ensure_accounting --compile
dpi_ensure_masterdata

echo "=== Step 2: fresh disburse (product 6367 DPI) ==="
ts="$(date +%s%3N)"
ext_ref="DPIC_FRESH_${ts}"
req="$ROOT/scripts/scratch/dpic_fresh_${ts}.json"
mkdir -p "$ROOT/scripts/scratch"
python3 - "$DPIC/payload/disburse_mft_6367.json" "$req" "$ext_ref" "$CUSTOMER_ID" \
  "$CERT_DISBURSE_MS" "$CERT_FIRST_EMI_MS" <<'PY'
import json, sys, time
from pathlib import Path
src, out, ext_ref, cust, disb_ms, first_emi_ms = sys.argv[1:7]
crn = str(int(time.time() * 1000))
data = json.loads(Path(src).read_text(encoding="utf-8"))
req = data["request"]
req["disbursement_details"]["external_ref_number"] = ext_ref
req["disbursement_details"]["expected_disbursement_date"] = disb_ms
req["disbursement_details"]["client_reference_number"] = crn
req["repayment_details"]["first_repayment_date"] = first_emi_ms
req["loan_details"]["sanction_date"] = disb_ms
req["loan_details"]["customer_id"] = cust
data["headers"]["stan"] = crn
data["headers"]["transmission_datetime"] = disb_ms
Path(out).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
python3 "$VALIDATE_DATES" "$CERT_DISBURSE_MS" "$CERT_FIRST_EMI_MS"
DISBURSE_WAIT_TIMEOUT_S="${DISBURSE_WAIT_TIMEOUT_S:-120}" \
DISBURSE_NO_LOAN_FAILFAST_S="${DISBURSE_NO_LOAN_FAILFAST_S:-60}" \
REQUEST_FILE="$req" bash "$DPIC/run_disburse_demo.sh"

read -r LOAN_ACCOUNT_ID ACCOUNT_NUMBER <<<"$(
  dpi_pg -t -A -F' ' -v ON_ERROR_STOP=1 -v ext_ref="$ext_ref" <<'SQL'
SELECT la.account_id, a.account_number
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.account a ON a.id = la.account_id
WHERE la.external_ref_number LIKE :'ext_ref' || '%' AND la.is_deleted = false
ORDER BY la.account_id DESC LIMIT 1;
SQL
)"
[[ -n "${LOAN_ACCOUNT_ID:-}" ]] || fail "disburse did not create loan for $ext_ref"
echo "DISBURSED lan=$ACCOUNT_NUMBER loan_account_id=$LOAN_ACCOUNT_ID ext_ref=$ext_ref"

echo "=== Step 3: DPI go-live + quarantine portfolio noise ==="
read -r product_code <<<"$(
  dpi_pg -t -A -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" <<'SQL'
SELECT COALESCE(p.code, 'JLGDL')
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.loan_product lp ON lp.id = la.loan_product_id
LEFT JOIN mfi_accounting.product p ON p.id = lp.product_id AND p.is_deleted = false
WHERE la.account_id = :loan_account_id::bigint;
SQL
)"
dpi_pg -v ON_ERROR_STOP=1 -v go_live_value="$GO_LIVE_DDMM" -v go_live_sub_type="$product_code" \
  -f "$DPIC/sql/helpers/upsert_dpi_go_live.sql" >/dev/null
dpi_evict_go_live_cache "$product_code"
dpi_restart_masterdata
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$DPIC/sql/helpers/quarantine_dpd_portfolio.sql" >/dev/null

echo "=== Step 4: milestone EOD from real schedule ==="
eval "$(LOAN_ACCOUNT_ID="$LOAN_ACCOUNT_ID" GRACE_DAYS="$GRACE_DAYS" DPI_CERT=1 python3 "$DPIC/demo/lib/eod_milestones_from_loan.py")"
export ROOT NTEST LOAN_ACCOUNT_ID GO_LIVE_ISO="$GO_LIVE_DDMM"
# Run through second EMI + grace (multi-overdue window) — real schedule, no SQL installment rewrite.
END_MS="$MULTI_OVERDUE_JOB_MS"
GO_LIVE_ISO="$(python3 - <<PY
from datetime import datetime
print(datetime.strptime("$GO_LIVE_DDMM", "%d-%m-%Y").strftime("%Y-%m-%d"))
PY
)"
export GO_LIVE_ISO
chmod +x "$DPIC/lib/dpi_run_milestone_eod.sh"
bash "$DPIC/lib/dpi_run_milestone_eod.sh" milestones "$GO_LIVE_ISO" "$(python3 - <<PY
import os
from datetime import datetime, timezone, timedelta
ms = int(os.environ["END_MS"])
d = datetime.fromtimestamp(ms/1000, tz=timezone(timedelta(hours=5, minutes=30)))
print(d.strftime("%Y-%m-%d"))
PY
)"

END_DATE="$(python3 - <<PY
import os
from datetime import datetime, timezone, timedelta
ms = int(os.environ["END_MS"])
d = datetime.fromtimestamp(ms/1000, tz=timezone(timedelta(hours=5, minutes=30)))
print(d.strftime("%Y-%m-%d"))
PY
)"

echo ""
echo "=== VERIFY fresh LAN $ACCOUNT_NUMBER through $END_DATE ==="
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v business_date="$END_DATE" \
  -f "$DPIC/sql/helpers/verify_dpi_full_pipeline.sql"

read -r viol rules <<<"$(
  dpi_pg -t -A -F' ' -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v business_date="$END_DATE" \
    -f "$DPIC/sql/helpers/verify_dpi_full_pipeline.sql" | head -1
)"
[[ "${viol:-1}" == "0" ]] || fail "full pipeline violations=$viol detail=${rules:-?}"

dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$DPIC/sql/helpers/verify_dpi_amount_parity.sql"

echo ""
echo "PASS: fresh disburse DPI E2E lan=$ACCOUNT_NUMBER loan_account_id=$LOAN_ACCOUNT_ID end=$END_DATE"
bash "$DPIC/lib/dpi_local_db_teardown.sh"
