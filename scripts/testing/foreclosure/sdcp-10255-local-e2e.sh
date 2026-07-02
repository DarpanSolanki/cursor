#!/usr/bin/env bash
# Foreclosure local E2E — SDCP-10255 pattern on proxy LAN 6000000262.
# duplicate PENDING → 333 → data fix → loanPrepayment REAL → verify CLOSED + payments sync.
#
# Prereq: bash scripts/bin/foreclosure-local-setup.sh [--restart]
# Run:    bash scripts/testing/foreclosure/sdcp-10255-local-e2e.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
GW="${FORECLOSURE_GW:-http://localhost:8001/api-gateway/api/v1/loanPrepayment}"
LAN="${FORECLOSURE_LAN:-6000000262}"
RCPT="${FORECLOSURE_RECEIPT:-412700000001537}"
AMT="${FORECLOSURE_AMOUNT:-5324.00}"
FD="${FORECLOSURE_DATE:-1725148800000}"
OFF="${FORECLOSURE_OFFICE_ID:-2}"
UID_H="${FORECLOSURE_USER_ID:-103}"
PD_ID="${FORECLOSURE_PREPAYMENT_ID:-22057}"
PSQL=(psql -h localhost -p 5433 -U yugabyte -d yugabyte -v ON_ERROR_STOP=1)

export PGPASSWORD="${PGPASSWORD:-yugabyte}"

call_prepay() {
  local mode="$1" stan="$2"
  local td
  td=$(date +%s000)
  curl -sk -X POST "$GW" -H "Content-Type: application/json" -d "{
    \"headers\": {
      \"tenant_code\": \"mfi\", \"client_code\": \"NOVOPAY\", \"channel_code\": \"WEB\",
      \"end_channel_code\": \"NOVOPAY\", \"function_code\": \"APPROVE\", \"function_sub_code\": \"DEFAULT\",
      \"run_mode\": \"$mode\", \"operation_mode\": \"SELF\", \"locale\": \"en-in\",
      \"stan\": \"$stan\", \"transmission_datetime\": \"$td\",
      \"user_id\": \"$UID_H\", \"actor_type\": \"EMPLOYEE\", \"user_handle_value\": \"$UID_H\", \"office_id\": \"$OFF\"
    },
    \"request\": {
      \"loan_foreclosure_details\": {
        \"account_number\": \"$LAN\",
        \"total_foreclosure_amount\": \"$AMT\",
        \"foreclosure_date\": \"$FD\",
        \"receipt_number\": \"$RCPT\"
      }
    }
  }"
}

echo "=== 0) Foreclosure local setup (schema + services) ==="
bash "$ROOT/scripts/bin/foreclosure-local-setup.sh" --restart 2>&1 | tail -8

echo "=== 0b) Reset proxy foreclosure collection to OPEN (idempotent replay) ==="
"${PSQL[@]}" <<EOSQL
UPDATE mfi_accounting.prepayment_details SET prepayment_status = 'PENDING', updated_on = NOW(), updated_by = 'LOCAL_SIM'
WHERE id = $PD_ID AND prepayment_status <> 'PENDING';

UPDATE mfi_accounting.loan_account la SET loan_status = 'FORECLOSURE_FREEZE', updated_on = NOW(), updated_by = 'LOCAL_SIM'
FROM mfi_accounting.account a
WHERE a.id = la.account_id AND a.account_number = '$LAN' AND la.loan_status = 'CLOSED';

UPDATE mfi_accounting.account SET status = 'ACTIVE', updated_on = NOW(), updated_by = 'LOCAL_SIM'
WHERE account_number = '$LAN' AND status = 'CLOSED';

UPDATE mfi_payments.collection_reference_details
SET partner_sync_status = 'UNSYNCED', updated_on = NOW(), updated_by = 'LOCAL_SIM'
WHERE receipt_number = '$RCPT' AND is_deleted = false;

UPDATE mfi_payments.collection c
SET collection_status = 'OPEN', partner_sync_status = 'UNSYNCED', loan_account_status = 'ACTIVE',
    updated_on = NOW(), updated_by = 'LOCAL_SIM'
FROM mfi_payments.collection_reference_details crd
WHERE crd.collection_id = c.id AND crd.receipt_number = '$RCPT'
  AND c.loan_account_number = '$LAN';
EOSQL

echo "=== 0c) Normalize prepayment nulls ==="
"${PSQL[@]}" -c "
UPDATE mfi_accounting.prepayment_details SET
  billed_principal_waived_amount = COALESCE(billed_principal_waived_amount, 0),
  billed_interest_waived_amount = COALESCE(billed_interest_waived_amount, 0),
  billed_dpi_waived_amount = COALESCE(billed_dpi_waived_amount, 0),
  bpi_waived_amount = COALESCE(bpi_waived_amount, 0),
  billed_interest_amount_to_be_paid = COALESCE(billed_interest_amount_to_be_paid, 0),
  billed_principal_amount_to_be_paid = COALESCE(billed_principal_amount_to_be_paid, 0),
  billed_dpi_amount_to_be_paid = COALESCE(billed_dpi_amount_to_be_paid, 0),
  billed_interest_amount = COALESCE(billed_interest_amount, 0),
  billed_principal_amount = COALESCE(billed_principal_amount, 0),
  updated_on = NOW(), updated_by = 'LOCAL_SIM'
WHERE id = $PD_ID;"

echo "=== 1) Baseline: one PENDING prepayment ==="
"$ROOT/scripts/db-local.sh" --sql "
SELECT COUNT(*) AS pending_active FROM mfi_accounting.prepayment_details pd
JOIN mfi_accounting.account a ON a.id = pd.loan_account_id
WHERE a.account_number = '$LAN' AND pd.prepayment_status = 'PENDING' AND pd.is_deleted = false;"

echo "=== 2) Insert duplicate PENDING (prod failure pattern) ==="
DUP_ID=$("${PSQL[@]}" -tA -c "
INSERT INTO mfi_accounting.prepayment_details (
  loan_account_id, prepayment_status, task_status, is_deleted, created_by, updated_by, created_on, updated_on,
  pending_installment_amount_to_be_paid, balance_principal_amount_to_be_paid, bpi_amount_to_be_paid,
  billed_interest_amount_to_be_paid, billed_principal_amount_to_be_paid,
  foreclosure_date, round_off_amount, excess_amount, receipt_number, payment_mode, closure_reason, notes,
  balance_principal_is_fully_waived, balance_principal_is_waived, billed_interest_is_fully_waived, billed_interest_is_waived
)
SELECT loan_account_id, 'PENDING', task_status, false, 'LOCAL_SIM_DUP', 'LOCAL_SIM_DUP', NOW(), NOW(),
  pending_installment_amount_to_be_paid, balance_principal_amount_to_be_paid, bpi_amount_to_be_paid,
  billed_interest_amount_to_be_paid, billed_principal_amount_to_be_paid,
  foreclosure_date, round_off_amount, excess_amount, receipt_number, payment_mode, closure_reason, notes,
  COALESCE(balance_principal_is_fully_waived, false), COALESCE(balance_principal_is_waived, false),
  COALESCE(billed_interest_is_fully_waived, false), COALESCE(billed_interest_is_waived, false)
FROM mfi_accounting.prepayment_details WHERE id = $PD_ID RETURNING id;" | head -1 | tr -d '[:space:]')
echo "duplicate prepayment id=$DUP_ID"

echo "=== 3) APPROVE with 2 pending rows (expect 333) ==="
RESP_DUP=$(call_prepay TRIAL "sim_dup_$(date +%s)")
echo "$RESP_DUP" | python3 -m json.tool
echo "$RESP_DUP" | python3 -c "import sys,json; c=json.load(sys.stdin)['response_status']['code']; sys.exit(0 if c=='333' else 1)" \
  || { echo "FAIL: expected 333 with duplicate pending rows"; exit 1; }

echo "=== 4) Data fix: expire duplicate ==="
"${PSQL[@]}" -c "
UPDATE mfi_accounting.prepayment_details SET prepayment_status = 'EXPIRED', updated_by = 'LOCAL_SIM_FIX', updated_on = NOW()
WHERE id = $DUP_ID;"

echo "=== 5) loanPrepayment REAL ==="
RESP_REAL=$(call_prepay REAL "sim_real_$(date +%s)")
echo "$RESP_REAL" | python3 -m json.tool
echo "$RESP_REAL" | python3 -c "import sys,json; s=json.load(sys.stdin)['response_status']; assert s['status']=='SUCCESS', s; print('REAL SUCCESS')"

echo "=== 6) Verify accounting closed ==="
"$ROOT/scripts/db-local.sh" --sql "
SELECT a.account_number, la.loan_status, pd.prepayment_status,
       (SELECT COUNT(*) FROM mfi_accounting.transaction_master tm WHERE tm.client_reference_number = '$RCPT') AS tm_rows
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.account a ON a.id = la.account_id
JOIN mfi_accounting.prepayment_details pd ON pd.id = $PD_ID
WHERE a.account_number = '$LAN';" | tee /tmp/foreclosure_verify.txt
grep -q CLOSED /tmp/foreclosure_verify.txt
grep -q APPROVED /tmp/foreclosure_verify.txt

echo "=== 7) Payments sync SQL ==="
"${PSQL[@]}" <<EOSQL
UPDATE mfi_payments.collection_reference_details crd
SET partner_sync_status = 'SYNCED', partner_sync_amount = amount_collected, updated_on = NOW(), updated_by = '3'
WHERE receipt_number = '$RCPT' AND is_deleted = false;

UPDATE mfi_payments.collection c
SET collection_status = 'CLOSED', partner_sync_status = 'SYNCED', loan_account_status = 'CLOSED',
    updated_on = NOW(), updated_by = '3'
FROM mfi_payments.collection_reference_details crd
WHERE crd.collection_id = c.id AND crd.receipt_number = '$RCPT'
  AND c.loan_account_number = '$LAN' AND UPPER(c.collection_type) = 'FORECLOSURE';
EOSQL

"$ROOT/scripts/db-local.sh" --sql "
SELECT c.collection_status, c.partner_sync_status, c.loan_account_status
FROM mfi_payments.collection c
JOIN mfi_payments.collection_reference_details crd ON crd.collection_id = c.id
WHERE crd.receipt_number = '$RCPT' AND crd.is_deleted = false;"

echo "=== E2E PASS ==="
