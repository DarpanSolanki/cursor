#!/usr/bin/env bash
# DCF GL split + SDCP-10494 outstanding scenario simulation (no live approve required).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "=== DCF principal split simulation (writer order model) ==="
python3 scripts/dcf_sanity/dcf_principal_split_simulation.py

if [[ "${DCF_SIM_QA3:-}" == "1" ]]; then
  echo ""
  echo "=== QA3 read-only schedule fixture (LAN 6005077725) ==="
  bash scripts/db-qa3.sh --sql "
SELECT 'future_billed_gross' AS bucket, SUM(ldd.due_amount)::numeric(12,0) AS amt
FROM mfi_accounting.loan_due_details ldd
WHERE ldd.loan_account_id = 8774460 AND ldd.component_type = 'PRIN' AND ldd.is_deleted = false
  AND ldd.due_date > '2026-09-07'
  AND EXISTS (SELECT 1 FROM mfi_accounting.loan_account_billing_details bd
    WHERE bd.loan_installment_details_id = ldd.loan_installment_details_id AND bd.reversed = false)
UNION ALL
SELECT 'future_unbilled_gross', SUM(ldd.due_amount)::numeric(12,0)
FROM mfi_accounting.loan_due_details ldd
WHERE ldd.loan_account_id = 8774460 AND ldd.component_type = 'PRIN' AND ldd.is_deleted = false
  AND ldd.due_date > '2026-09-07'
  AND NOT EXISTS (SELECT 1 FROM mfi_accounting.loan_account_billing_details bd
    WHERE bd.loan_installment_details_id = ldd.loan_installment_details_id AND bd.reversed = false);
"
fi

echo ""
echo "=== PASS: dcf principal split simulation ==="
