#!/usr/bin/env bash
# UD §5.4 — DPI billing: aggregated bill per anchor, due on next EMI, value_date aligned.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-8060160}"
ANCHOR_INSTALLMENT_ID="${ANCHOR_INSTALLMENT_ID:-}"
PG=(psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}")
export PGPASSWORD="${PGPASSWORD:-yugabyte}"

fail() { echo "FAIL: $*" >&2; exit 1; }

if [[ -z "$ANCHOR_INSTALLMENT_ID" ]]; then
  ANCHOR_INSTALLMENT_ID="$("${PG[@]}" -t -A -c \
    "SELECT installment_id FROM mfi_accounting.dpi_accrual_details
     WHERE loan_account_id = ${LOAN_ACCOUNT_ID} AND is_deleted = false
       AND billing_posting_date IS NOT NULL AND total_accrued_amount > 0
     ORDER BY end_date DESC, id DESC LIMIT 1;" 2>/dev/null || true)"
fi

if [[ -z "${ANCHOR_INSTALLMENT_ID:-}" || "${ANCHOR_INSTALLMENT_ID}" == "" ]]; then
  if [[ "${DPI_BILLING_UD_REQUIRED:-1}" == "1" ]]; then
    fail "no billed DPI anchor installment on loan $LOAN_ACCOUNT_ID (run EOD with billing first)"
  fi
  echo "SKIP: billing UD verify (no billed anchor, DPI_BILLING_UD_REQUIRED=0)"
  exit 0
fi

out="$("${PG[@]}" -v ON_ERROR_STOP=1 -t -A -F'|' \
  -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -v anchor_installment_id="$ANCHOR_INSTALLMENT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_billing_ud.sql" | tail -1)"

IFS='|' read -r billed_rows billing_txn_count billing_posting_days billed_amount \
  due_rows due_date due_installment_id due_amount next_emi_date next_installment_id \
  txn_value_date due_on_next_emi value_date_on_next_emi aggregated_billing <<<"$out"

echo "=== DPI billing UD verify (loan=$LOAN_ACCOUNT_ID anchor=$ANCHOR_INSTALLMENT_ID) ==="
echo "  billed_rows=$billed_rows txn_count=$billing_txn_count posting_days=$billing_posting_days amount=$billed_amount"
echo "  dpi_due_rows=$due_rows due_inst=$due_installment_id next_emi=$next_emi_date due_on_next_emi=$due_on_next_emi"

[[ "${billed_rows:-0}" -gt 0 ]] || fail "anchor has no billed accrual rows"
[[ "${aggregated_billing:-f}" == "t" ]] || fail "billing not aggregated (multiple txn refs or posting days)"
[[ "${due_rows:-0}" -gt 0 ]] || fail "no DPI loan_due_details after billing"
[[ "${due_on_next_emi:-f}" == "t" ]] || fail "DPI due not on next EMI installment (got $due_installment_id vs next $next_installment_id)"
if [[ -n "${txn_value_date:-}" && "${next_emi_date:-}" != "" ]]; then
  [[ "${value_date_on_next_emi:-f}" == "t" ]] || fail "billing txn value_date not on next EMI date"
fi

echo "PASS: DPI billing UD §5.4 OK"
