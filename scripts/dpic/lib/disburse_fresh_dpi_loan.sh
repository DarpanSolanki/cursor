#!/usr/bin/env bash
# Disburse one fresh LAN on DPI product 6367 — unique ext_ref + customer_id (no LAN patching).
set -euo pipefail

_DISBURSE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
TAG="${1:?scenario tag required e.g. pre_emi}"
ANCHOR_DATE="${ANCHOR_DATE:-$(date +%Y-%m-%d)}"

# shellcheck disable=SC1091
source "$_DISBURSE_ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"

eval "$(python3 "$_DISBURSE_ROOT/scripts/dpic/demo/lib/compute_dates.py" --anchor "$ANCHOR_DATE")"

TS="$(date +%s%3N)"
EXT_REF="DPIC_CERT_${TAG}_${ANCHOR_DATE//-/}_${TS}"
CUSTOMER_ID="${CUSTOMER_ID:-10002233}"
REQUEST_SCRATCH="$_DISBURSE_ROOT/scripts/scratch/dpic_cert_${TAG}_${TS}.json"

python3 - "$_DISBURSE_ROOT/scripts/dpic/payload/disburse_mft_6367.json" "$REQUEST_SCRATCH" "$EXT_REF" \
  "$CUSTOMER_ID" "$DEMO_DISBURSE_MS" "$DEMO_FIRST_EMI_MS" "$DEMO_DISBURSE_MS" <<'PY'
import json, sys, time
from pathlib import Path

src, out, ext_ref, cust, disb_ms, first_emi_ms, tx_ms = sys.argv[1:8]
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
data["headers"]["transmission_datetime"] = tx_ms
Path(out).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print(f"payload={out} customer_id={cust} ext_ref={ext_ref}")
PY

python3 "$_DISBURSE_ROOT/scripts/dpic/demo/lib/validate_disburse_dates.py" "$DEMO_DISBURSE_MS" "$DEMO_FIRST_EMI_MS"

dpi_ensure_actor
bash "$_DISBURSE_ROOT/scripts/bin/novopay-service.sh" ensure accounting ${COMPILE:+--compile}
REQUEST_FILE="$REQUEST_SCRATCH" DISBURSE_DPI_CERTIFY=1 bash "$_DISBURSE_ROOT/scripts/dpic/run_disburse_demo.sh"

export PGPASSWORD="${PGPASSWORD:-yugabyte}"
PG=(psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}")
read -r LOAN_ACCOUNT_ID LAN <<<"$(
  "${PG[@]}" -t -A -F' ' -v ON_ERROR_STOP=1 -v ext_ref="$EXT_REF" <<'SQL'
SELECT la.account_id, a.account_number
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.account a ON a.id = la.account_id
WHERE la.external_ref_number LIKE :'ext_ref' || '%' AND la.is_deleted = false
ORDER BY la.account_id DESC LIMIT 1;
SQL
)"
[[ -n "${LOAN_ACCOUNT_ID:-}" ]] || { echo "FAIL: disburse did not create loan for $EXT_REF" >&2; exit 1; }

neg="$("${PG[@]}" -t -A -c \
  "SELECT count(*) FROM mfi_accounting.loan_due_details WHERE loan_account_id=$LOAN_ACCOUNT_ID AND is_deleted=false AND due_amount<0" || echo 1)"
[[ "${neg:-1}" == "0" ]] || { echo "FAIL: negative schedule on $LAN — run scripts/dpic/run_setup.sh" >&2; exit 1; }

export EXT_REF LOAN_ACCOUNT_ID LAN CUSTOMER_ID ANCHOR_DATE
echo "DISBURSED tag=$TAG lan=$LAN loan_account_id=$LOAN_ACCOUNT_ID customer_id=$CUSTOMER_ID ext_ref=$EXT_REF"
