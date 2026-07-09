#!/usr/bin/env bash
# One-shot local setup for foreclosure E2E (accounting + payments schema + service endpoints).
# Safe to re-run (idempotent SQL). Does not start services unless --restart.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PSQL=(psql -h localhost -p 5433 -U yugabyte -d yugabyte -v ON_ERROR_STOP=1)
export PGPASSWORD="${PGPASSWORD:-yugabyte}"

RESTART=0
[[ "${1:-}" == "--restart" ]] && RESTART=1

run_sql() {
  echo ">> $1"
  "${PSQL[@]}" -f "$ROOT/scripts/sql/setup/$1"
}

run_sql local_setup_loan_prepayment_dpi_ptc_placeholders.sql
run_sql local_setup_loan_prepayment_ptc_clone_6367.sql
run_sql local_setup_loan_product_asset_criteria_liquidation_order.sql
run_sql local_setup_payments_collection_schema_align.sql
run_sql local_setup_platform_master_service_endpoints.sql

echo ">> services ensure"
bash "$ROOT/scripts/dcf_sanity/local_payments_stub.sh" ensure
if [[ "$RESTART" -eq 1 ]]; then
  bash "$ROOT/scripts/bin/novopay-service.sh" restart accounting
else
  bash "$ROOT/scripts/bin/novopay-service.sh" ensure accounting
fi

echo "=== foreclosure local setup complete ==="
