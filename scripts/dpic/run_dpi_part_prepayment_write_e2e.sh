#!/usr/bin/env bash
# loanAccountPartPrepayment TRIAL write — postTransaction + DPI GL leg SQL assert.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/demo/lib/common.sh"

# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpic_harness_lib.sh"
NET="${PART_PREP_NET:-5000}"
fail() { echo "FAIL: $*" >&2; exit 1; }

echo "=== DPI loanAccountPartPrepayment TRIAL write (LAN=$ACCOUNT_NUMBER) ==="
dpi_ensure_accounting
dpi_ensure_masterdata
dpi_ensure_actor
dpi_export_correlators
dpi_restore_api_state
dpic_harness_preflight || fail "harness preflight"

dpi_pg -v ON_ERROR_STOP=1 -f "$ROOT/scripts/dpic/sql/helpers/seed_part_prepayment_dpi_catalogue_6367.sql" >/dev/null

dpic_repayment_timestamps
RESCHED_MS="$REPAY_MS"
export RESCHED_MS

read -r OVERDUE DPI_OPEN <<<"$(
  dpi_pg -v ON_ERROR_STOP=1 -t -A -F' ' \
    -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -f "$ROOT/scripts/dpic/sql/helpers/compute_part_prep_trial_amounts.sql" | tr -d '[:space:]' | tr '|' ' '
)"
# psql -F' ' outputs space-separated; handle single-line two columns
read -r OVERDUE DPI_OPEN <<<"$(dpi_pg -v ON_ERROR_STOP=1 -t -A \
  -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/compute_part_prep_trial_amounts.sql" | head -1 | tr '|' ' ')"

python3 - "$OVERDUE" "$DPI_OPEN" <<'PY'
import sys
overdue, dpi = sys.argv[1:3]
if float(overdue or 0) <= 0:
    raise SystemExit("FAIL: no overdue amount on fixture — run verify-dpi / restore first")
if float(dpi or 0) <= 0:
    raise SystemExit("FAIL: no open billed DPI overdue — part-prep DPI leg test needs billed DPI due")
print(f"OK: overdue={overdue} dpi_overdue={dpi}")
PY

BPD="$(
  curl -s -m 60 -X POST "http://127.0.0.1:8002/accounting/api/v1/getPartPrepaymentBPIAmount" \
    -H 'Content-Type: application/json' \
    -d "{\"headers\":{\"tenant_code\":\"mfi\",\"user_id\":\"3\",\"stan\":\"pp_bpd\",\"client_code\":\"NOVOPAY\",\"channel_code\":\"WEB\",\"function_code\":\"DEFAULT\",\"function_sub_code\":\"DEFAULT\",\"run_mode\":\"REAL\"},\"request\":{\"loan_account_number\":\"$ACCOUNT_NUMBER\",\"rescheduling_effective_date\":\"$RESCHED_MS\"}}" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('bpd_amount') or '0')"
)"

GROSS="$(python3 - "$OVERDUE" "$NET" "$BPD" <<'PY'
import sys
from decimal import Decimal
o, n, b = (Decimal(x or 0) for x in sys.argv[1:4])
print(o + n + b)
PY
)"

export PART_PREP_OVERDUE="$OVERDUE"
export PART_PREP_NET="$NET"
export PART_PREP_BPD="$BPD"
export PART_PREP_GROSS="$GROSS"
export PART_PREP_STAN="pp_write_$(date +%s)"

echo ">>> loanAccountPartPrepayment TRIAL resched=$RESCHED_MS gross=$GROSS bpd=$BPD"
python3 "$ROOT/scripts/dpic/part_prepayment_trial_ntest.py" || fail "part_prepayment TRIAL API"

read -r LEG_COUNT MAX_AMT <<<"$(dpi_pg -v ON_ERROR_STOP=1 -t -A \
  -v lan="$ACCOUNT_NUMBER" -v stan="$PART_PREP_STAN" \
  -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_part_prepayment_posting.sql" | head -1 | tr '|' ' ')"

[[ "${LEG_COUNT:-0}" != "0" ]] || fail "no BILLED_DPI / ADV_BILLED_DPI partition legs in transaction_partition_details (stan=$PART_PREP_STAN)"
echo "OK: part_prep DPI GL legs count=$LEG_COUNT max_amount=$MAX_AMT"

echo "=== DPI loanAccountPartPrepayment TRIAL write PASS ==="
