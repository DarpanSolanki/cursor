#!/usr/bin/env bash
# SQL assertions after dpiAccrualCalculation → booking → billing.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-8060160}"
PG=(psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}")
export PGPASSWORD="${PGPASSWORD:-yugabyte}"

fail() { echo "FAIL: $*" >&2; exit 1; }

out="$("${PG[@]}" -v ON_ERROR_STOP=1 -t -A -F'|' \
  -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_post_eod.sql" | tail -1)"

IFS='|' read -r accrual_rows distinct_inst booked_rows billed_rows total_accrued \
  dpi_due_rows dpi_outstanding latest_inst <<<"$out"

echo "=== post-EOD DPI DB verify (loan=$LOAN_ACCOUNT_ID) ==="
echo "  accrual_rows=$accrual_rows distinct_installments=$distinct_inst booked=$booked_rows billed=$billed_rows"
echo "  total_accrued=$total_accrued dpi_due_rows=$dpi_due_rows dpi_outstanding=$dpi_outstanding latest_inst=$latest_inst"

[[ "${accrual_rows:-0}" -gt 0 ]] || fail "no accrual rows with amount > 0"
[[ "${distinct_inst:-0}" -ge 1 ]] || fail "no distinct installment_id on accruals"
[[ "${booked_rows:-0}" -gt 0 ]] || fail "no booked accrual rows (accrual_posting_date null)"
[[ "${billed_rows:-0}" -gt 0 ]] || fail "no billed accrual rows (billing_posting_date null)"
[[ "${dpi_due_rows:-0}" -gt 0 ]] || fail "no DPI loan_due_details row after billing"
[[ "${dpi_outstanding:-0}" != "0" && "${dpi_outstanding:-0}" != "0.000000" ]] || fail "DPI due outstanding is zero after billing"

echo "PASS: post-EOD DPI DB state OK"
