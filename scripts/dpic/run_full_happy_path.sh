#!/usr/bin/env bash
# Full DPIC local path: setup → disburse → DPD → DPI calc (→ booking/billing).
# Business date default: 12-Jun-2026 18:00 IST. Disburse backdated to 12-Feb-2026.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
EXT_REF="${EXT_REF:-DPIC_MFT_6367_10002233_001}"
JOB_TIME="${JOB_TIME:-1781267400000}"
SKIP_SETUP="${SKIP_SETUP:-0}"
SEED_CALC_WINDOW="${SEED_CALC_WINDOW:-0}"

echo "=== DPIC full happy path ==="
echo "ext_ref prefix: $EXT_REF"
echo "EOD job_time:   $JOB_TIME"

if [[ "$SKIP_SETUP" != "1" ]]; then
  bash "$ROOT/scripts/dpic/run_setup.sh"
else
  echo ">>> SKIP_SETUP=1 — assuming DB already prepared"
fi

bash "$ROOT/scripts/dpic/run_disburse.sh"

echo ""
echo ">>> Resolve disbursed loan ..."
read -r LOAN_ACCOUNT_ID LAN LOAN_STATUS DISB_STATUS PAST_DUE <<<"$(
  PGPASSWORD="${PGPASSWORD:-yugabyte}" psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" \
    -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}" -t -A -F' ' -v ON_ERROR_STOP=1 <<SQL
SELECT la.account_id, a.account_number, la.loan_status, la.disbursement_status, la.past_due_days
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.account a ON a.id = la.account_id
WHERE la.external_ref_number LIKE '${EXT_REF}%'
  AND la.is_deleted = false
ORDER BY la.account_id DESC
LIMIT 1;
SQL
)"

if [[ -z "${LOAN_ACCOUNT_ID:-}" ]]; then
  echo "FAIL: no loan for ext_ref prefix $EXT_REF" >&2
  exit 1
fi

echo "Loan: account_id=$LOAN_ACCOUNT_ID LAN=$LAN status=$LOAN_STATUS past_due_days=$PAST_DUE"

LOAN_ACCOUNT_ID="$LOAN_ACCOUNT_ID" JOB_TIME="$JOB_TIME" SEED_CALC_WINDOW="$SEED_CALC_WINDOW" \
  bash "$ROOT/scripts/dpic/run_eod.sh"

echo ""
echo ">>> Verification SQL hints:"
echo "  SELECT * FROM mfi_accounting.dpi_accrual_details WHERE loan_account_id=$LOAN_ACCOUNT_ID AND is_deleted=false;"
echo "  SELECT component_type, due_amount, paid_amount FROM mfi_accounting.loan_due_details WHERE loan_account_id=$LOAN_ACCOUNT_ID AND component_type='DPI' AND is_deleted=false;"
