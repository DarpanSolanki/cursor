#!/usr/bin/env bash
# individualChildLoanForeclosure local E2E — simulation-built APPROVE payload (DPI-capable LAN).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"

export ICF_LAN="${ICF_LAN:-6004044425}"
export ICF_FORECLOSURE_DATE="${ICF_FORECLOSURE_DATE:-1784500000000}"
export ICF_USER_ID="${ICF_USER_ID:-103}"
export ICF_OFFICE_ID="${ICF_OFFICE_ID:-6}"
export PGPASSWORD="${PGPASSWORD:-yugabyte}"
PSQL=(psql -h localhost -p 5433 -U yugabyte -d yugabyte -v ON_ERROR_STOP=1)

echo "=== individualChildLoanForeclosure E2E setup ==="
bash "$ROOT/scripts/bin/foreclosure-local-setup.sh" 2>&1 | tail -6
bash "$ROOT/scripts/bin/agent-ops.sh" before-test individualChildLoanForeclosure accounting
sleep 3

echo "=== idempotent replay reset for $ICF_LAN ==="
"${PSQL[@]}" <<EOSQL
UPDATE mfi_accounting.loan_account la SET loan_status = 'ACTIVE', updated_on = NOW(), updated_by = 'LOCAL_ICF'
FROM mfi_accounting.account a
WHERE a.id = la.account_id AND a.account_number = '$ICF_LAN' AND la.loan_status = 'CLOSED';
UPDATE mfi_accounting.account SET status = 'ACTIVE', updated_on = NOW(), updated_by = 'LOCAL_ICF'
WHERE account_number = '$ICF_LAN' AND status = 'CLOSED';
DELETE FROM mfi_accounting.prepayment_details pd
USING mfi_accounting.loan_account la, mfi_accounting.account a
WHERE a.id = la.account_id AND la.account_id = pd.loan_account_id
  AND a.account_number = '$ICF_LAN' AND pd.prepayment_status = 'PENDING';
EOSQL

# Template must exist for ntest auto / JTF parse
test -f "$ROOT/trustt-platform-accounting/deploy/application/templates/request/product/individualChildLoanForeclosure_requestTemplate.json"

python3 "$ROOT/scripts/testing/foreclosure/individual_child_foreclosure_ntest.py"
