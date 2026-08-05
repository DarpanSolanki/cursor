#!/usr/bin/env bash
# SHG DPI full EOD chain: dpiAccrualCalculation (+ parent→child distribute) →
# dpiAccrualBooking → dpiBilling, with the DAD column audit re-run after every job.
# Parent DPI accrued must equal sum(children); each child's base_amount must be its OWN
# overdue admitted on/after the DPI cut-off, and children's bases must sum to the
# parent's per segment (TDPQA-234). Booking/billing must not disturb either invariant.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_fixture_constants.sh"
dpi_use_shg_parent_loan
: "${GO_LIVE_DDMM:=15-04-2025}"
GO_LIVE_ISO="$(date -d "$(echo "$GO_LIVE_DDMM" | awk -F- '{print $3"-"$2"-"$1}')" +%Y-%m-%d)"
# shellcheck source=lib/dpi_demo_fixture.sh
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"
dpi_use_shg_parent_loan
export JOB_TIME="$DPI_SHG_PARITY_JOB_TIME"
PG=(psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}")
export PGPASSWORD="${PGPASSWORD:-yugabyte}"
NTEST="$ROOT/scripts/bin/ntest.sh"
WAIT_BATCH="$ROOT/scripts/dpic/lib/wait_batch_job.sh"

fail() { echo "FAIL: $*" >&2; exit 1; }

echo "=== SHG parent/child DPI distribute parity ==="
echo "  parent_loan_account_id=$PARENT_LOAN_ACCOUNT_ID lan=$ACCOUNT_NUMBER job_time=$JOB_TIME"

bash "$ROOT/scripts/bin/novopay-service.sh" ensure accounting ${COMPILE:+--compile}

dpi_set_go_live_and_refresh "$GO_LIVE_DDMM" "SHGDL"

"${PG[@]}" -v ON_ERROR_STOP=1 \
  -v parent_loan_account_id="$PARENT_LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/setup_shg_dpi_parity_e2e.sql"

"${PG[@]}" -v ON_ERROR_STOP=1 \
  -v parent_loan_account_id="$PARENT_LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/quarantine_shg_dpd_portfolio.sql" >/dev/null

family_ids="$("${PG[@]}" -t -A -c "
SELECT account_id FROM mfi_accounting.loan_account
WHERE account_id = $PARENT_LOAN_ACCOUNT_ID OR parent_loan_account_id = $PARENT_LOAN_ACCOUNT_ID
ORDER BY account_id")"

while IFS= read -r aid; do
  [[ -n "$aid" ]] || continue
  "${PG[@]}" -v ON_ERROR_STOP=1 \
    -v loan_account_id="$aid" \
    -v business_date_ms="$JOB_TIME" \
    -f "$ROOT/scripts/dpic/sql/helpers/sync_demo_past_due.sql" >/dev/null
done <<<"$family_ids"

if [[ -f "$ROOT/scripts/dpic/sql/helpers/clear_batch_failure_audit.sql" ]]; then
  for aid in $family_ids; do
    LOAN_ACCOUNT_ID="$aid" JOB_TIME="$JOB_TIME" "${PG[@]}" -v ON_ERROR_STOP=1 \
      -v loan_account_id="$aid" \
      -f "$ROOT/scripts/dpic/sql/helpers/clear_batch_failure_audit.sql" >/dev/null 2>&1 || true
  done
fi

echo ">>> dpiAccrualCalculation (SHG family — parent calc + distribute)"
before="$(dpi_pg -t -A -c "
SELECT COALESCE(MAX(bje.job_execution_id), 0)
FROM mfi_batch.batch_job_execution bje
JOIN mfi_batch.batch_job_instance bji ON bji.job_instance_id = bje.job_instance_id
WHERE bji.job_name = 'dpiAccrualCalculation'")"
JOB_TIME="$JOB_TIME" "$NTEST" api accounting dpiAccrualCalculation --batch --job-time "$JOB_TIME" >/dev/null
BATCH_WAIT_ARG3=before bash "$WAIT_BATCH" dpiAccrualCalculation "$JOB_TIME" "$before"

verify_out=""
for _ in 1 2 3 4 5 6 7 8; do
  verify_out="$("${PG[@]}" -v ON_ERROR_STOP=1 -t -A -F'|' \
    -v parent_loan_account_id="$PARENT_LOAN_ACCOUNT_ID" \
    -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_shg_parent_child_parity.sql" | tail -1)"
  IFS='|' read -r parent_accrued children_sum parent_out child_out accrual_parity outstanding_parity <<<"$verify_out"
  if [[ "$accrual_parity" == "t" && "$outstanding_parity" == "t" && "${parent_accrued:-0}" != "0" ]]; then
    break
  fi
  sleep 1
done

IFS='|' read -r parent_accrued children_sum parent_out child_out accrual_parity outstanding_parity <<<"$verify_out"

[[ "$accrual_parity" == "t" ]] || fail "accrual_parity=$accrual_parity parent=$parent_accrued children=$children_sum"
[[ "$outstanding_parity" == "t" ]] || fail "outstanding_parity=$outstanding_parity parent=$parent_out children=$child_out"
[[ "${parent_accrued:-0}" != "0" && "${children_sum:-0}" != "0" ]] || fail "zero accrual — batch did not produce DPI rows (parent=$parent_accrued children=$children_sum)"

run_column_audit() {
  local stage="$1"
  echo ">>> dad_column_audit after $stage"
  ROOT="$ROOT" ACCOUNT_NUMBER="$ACCOUNT_NUMBER" GO_LIVE_ISO="$GO_LIVE_ISO" AUDIT_STAGE="$stage" python3 - <<'PY'
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ["ROOT"])
sys.path.insert(0, str(ROOT / "scripts/testing"))

def query_rows(sql: str):
    r = subprocess.run(
        ["psql", "-h", "127.0.0.1", "-p", "5433", "-U", "yugabyte", "-d", "yugabyte",
         "-v", "ON_ERROR_STOP=1", "-t", "-A", "-F", "|", "-c", sql],
        env={**os.environ, "PGPASSWORD": os.environ.get("PGPASSWORD", "yugabyte")},
        capture_output=True, text=True, check=True,
    )
    return [tuple(ln.split("|")) for ln in r.stdout.splitlines() if ln.strip()]

from flowtest.dad_column_audit import (
    assert_audit,
    audit_shg_child_dad_distribute,
    audit_shg_child_dad_all_rows,
)

lan = os.environ["ACCOUNT_NUMBER"]
tip = audit_shg_child_dad_distribute(parent_lan=lan, query_rows=query_rows)
assert_audit(tip)
full = audit_shg_child_dad_all_rows(
    parent_lan=lan, query_rows=query_rows, go_live=os.environ["GO_LIVE_ISO"]
)
print(f"  rows audited: {full.evidence.get('rows_audited')}")
assert_audit(full)
PY
}

family_sql() { "${PG[@]}" -v ON_ERROR_STOP=1 -t -A -F'|' -c "$1"; }

run_column_audit dpiAccrualCalculation


# ---- Job 2/3: dpiAccrualBooking -------------------------------------------------
# Booking posts the accrued amount. It must not disturb base_amount, and parent/child
# accrued parity must survive posting.
echo ">>> dpiAccrualBooking (SHG family)"
dpi_call_batch dpiAccrualBooking "$JOB_TIME"

booking_row="$(family_sql "
SELECT COUNT(*) FILTER (WHERE d.accrual_posting_date IS NOT NULL),
       COUNT(*),
       COUNT(*) FILTER (WHERE d.accrual_posting_date IS NOT NULL
                          AND COALESCE(d.accrual_transaction_ref_number,'') = '')
FROM mfi_accounting.dpi_accrual_details d
JOIN mfi_accounting.loan_account la ON la.account_id = d.loan_account_id
WHERE (la.account_id = $PARENT_LOAN_ACCOUNT_ID OR la.parent_loan_account_id = $PARENT_LOAN_ACCOUNT_ID)
  AND COALESCE(d.is_deleted,false) = false" | tail -1)"
IFS='|' read -r posted_rows total_rows ref_missing <<<"$booking_row"
[[ "${posted_rows:-0}" -gt 0 ]] || fail "dpiAccrualBooking posted nothing (rows=$total_rows)"
[[ "${ref_missing:-0}" -eq 0 ]] || fail "posted rows without accrual_transaction_ref_number: $ref_missing"
echo "  booking: posted=$posted_rows/$total_rows rows, all carry a txn ref"
run_column_audit dpiAccrualBooking

# ---- Job 3/3: dpiBilling -------------------------------------------------------
# Billing must not rewrite base_amount either; the family invariants still hold after it.
echo ">>> dpiBilling (SHG family)"
dpi_call_batch dpiBilling "$JOB_TIME"

billing_row="$(family_sql "
SELECT COUNT(*) FILTER (WHERE d.billing_posting_date IS NOT NULL),
       (SELECT COUNT(*) FROM mfi_accounting.loan_due_details ldd
         JOIN mfi_accounting.loan_account la2 ON la2.account_id = ldd.loan_account_id
        WHERE ldd.component_type = 'DPI'
          AND COALESCE(ldd.is_deleted,false) = false
          AND (la2.account_id = $PARENT_LOAN_ACCOUNT_ID
               OR la2.parent_loan_account_id = $PARENT_LOAN_ACCOUNT_ID))
FROM mfi_accounting.dpi_accrual_details d
JOIN mfi_accounting.loan_account la ON la.account_id = d.loan_account_id
WHERE (la.account_id = $PARENT_LOAN_ACCOUNT_ID OR la.parent_loan_account_id = $PARENT_LOAN_ACCOUNT_ID)
  AND COALESCE(d.is_deleted,false) = false" | tail -1)"
IFS='|' read -r billed_rows dpi_due_rows <<<"$billing_row"
echo "  billing: billed_rows=$billed_rows dpi_due_rows=$dpi_due_rows"
run_column_audit dpiBilling

echo "PASS: SHG 3-job chain (calc→booking→billing) parent=$parent_accrued children_sum=$children_sum accrual_parity=$accrual_parity billed=$billed_rows column_audit OK (LAN $ACCOUNT_NUMBER)"
