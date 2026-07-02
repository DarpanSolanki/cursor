#!/usr/bin/env bash
# loanAccountAssetCriteriaJob DEFAULT — REGULAR_TO_NPA DPI movement (DpiNpaMovementService).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"
# shellcheck disable=SC1091
source "$ROOT/scripts/lib/novopay-service-lib.sh"

TARGET_DPD="${TARGET_PAST_DUE_DAYS:-65}"
fail() { echo "FAIL: $*" >&2; exit 1; }

echo "=== DPI NPA movement E2E (LAN=$ACCOUNT_NUMBER dpd=$TARGET_DPD) ==="
dpi_ensure_accounting
dpi_ensure_actor
dpi_export_correlators
dpi_restore_api_state

dpi_pg -v ON_ERROR_STOP=1 -f "$ROOT/scripts/dpic/sql/helpers/seed_npa_dpi_catalogue_6367.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 \
  -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -v target_past_due_days="$TARGET_DPD" \
  -f "$ROOT/scripts/dpic/sql/helpers/setup_npa_dpi_trigger.sql" >/dev/null

BILLED_DPI="$(dpi_pg -t -A -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_npa_movement.sql" | sed -n '2p')"
python3 - "$BILLED_DPI" <<'PY'
import sys
if float(sys.argv[1] or 0) <= 0:
    raise SystemExit("FAIL: no billed DPI open before NPA movement")
print(f"OK: billed DPI open={sys.argv[1]}")
PY

STAN="npa_dpi_$(date +%s)"
BODY="$(python3 - "$ACCOUNT_NUMBER" "$JOB_TIME" "$STAN" <<'PY'
import json, sys
lan, job_time, stan = sys.argv[1:4]
print(json.dumps({
  "headers": {
    "tenant_code": "mfi", "user_id": "3", "stan": stan,
    "client_code": "NOVOPAY", "channel_code": "WEB", "operation_mode": "SELF",
    "function_code": "DEFAULT", "function_sub_code": "DEFAULT", "run_mode": "REAL"
  },
  "request": {
    "job_time": str(job_time),
    "account_number_list": [lan]
  }
}))
PY
)"

echo ">>> loanAccountAssetCriteriaJob DEFAULT"
RESP="$(curl -s -m 120 -X POST "http://localhost:8002/accounting/api/v1/loanAccountAssetCriteriaJob" \
  -H 'Content-Type: application/json' -d "$BODY")"
python3 - "$RESP" <<'PY'
import json, sys
d = json.loads(sys.argv[1])
code = d.get("response_status", {}).get("code", "")
if code not in ("000",):
    raise SystemExit(f"FAIL: loanAccountAssetCriteriaJob code={code} body={sys.argv[1][:500]}")
print("OK: loanAccountAssetCriteriaJob SUCCESS")
PY

read -r txn_count billed_after <<<"$(
  dpi_pg -v ON_ERROR_STOP=1 -t -A -F' ' \
    -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -v lan="$ACCOUNT_NUMBER" \
    -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_npa_movement.sql" | tail -2 | tr '\n' ' '
)"
[[ "${txn_count:-0}" != "0" ]] || fail "no REGULAR_TO_NPA DPI txn in transaction_master (check seed_npa_dpi_catalogue_6367.sql)"

SLAB="$(dpi_pg -t -A -v ON_ERROR_STOP=1 -c \
  "SELECT asset_criteria_slabs_id FROM mfi_accounting.loan_account WHERE account_id=$LOAN_ACCOUNT_ID")"
[[ "$SLAB" == "2" ]] || fail "expected asset_criteria_slabs_id=2 after NPA forward, got $SLAB"

echo "OK: dpi_npa_txn_count=$txn_count slab=$SLAB billed_dpi_after=$billed_after"

if [[ "${RESTORE_AFTER:-1}" == "1" ]]; then
  echo ">>> restore parent DPI API state after NPA test"
  LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-8060160}" JOB_TIME="$JOB_TIME" dpi_restore_api_state
fi

echo "=== DPI NPA movement E2E PASS ==="
