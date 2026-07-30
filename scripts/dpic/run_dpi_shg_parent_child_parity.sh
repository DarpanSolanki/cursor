#!/usr/bin/env bash
# SDCP-11012: after dpiAccrualCalculation + DpiGroupLoanAccrualAdjustTasklet,
# parent DPI accrued must equal sum(children).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_fixture_constants.sh"
dpi_use_shg_parent_loan
: "${GO_LIVE_DDMM:=15-04-2025}"
# shellcheck source=lib/dpi_demo_fixture.sh
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"
dpi_use_shg_parent_loan
export JOB_TIME="$DPI_SHG_PARITY_JOB_TIME"
PG=(psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}")
export PGPASSWORD="${PGPASSWORD:-yugabyte}"
NTEST="$ROOT/scripts/bin/ntest.sh"
WAIT_BATCH="$ROOT/scripts/dpic/lib/wait_batch_job.sh"

fail() { echo "FAIL: $*" >&2; exit 1; }

echo "=== SDCP-11012 SHG parent/child DPI parity ==="
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

echo ">>> dpiAccrualCalculation (SHG family)"
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

echo "PASS: SHG parent=$parent_accrued children_sum=$children_sum accrual_parity=$accrual_parity outstanding_parity=$outstanding_parity (LAN $ACCOUNT_NUMBER)"
