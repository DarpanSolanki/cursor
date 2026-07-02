#!/usr/bin/env bash
# One-time / re-runnable local DB prep for DPIC dev testing (product 6367).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DPIC_SQL="$ROOT/scripts/dpic/sql"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/preflight.sh"

PG=(psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}")
export PGPASSWORD="${PGPASSWORD:-yugabyte}"

echo "=== DPIC local setup ==="
echo ""

if [[ "${SKIP_PREFLIGHT:-0}" != "1" ]]; then
  DPIC_SKIP_SERVICES=1 dpic_run_preflight || exit 1
  echo ""
fi

echo ">>> 1/4 Product-document accounting rules (DPI v1.3 xlsx)"
"${PG[@]}" -v ON_ERROR_STOP=1 -f "$DPIC_SQL/seed_accounting_rules_from_product_doc.sql"

echo ""
echo ">>> 2/4 Product 6367 / scheme 2655 — links, placeholders, EMI=ZERO fix"
"${PG[@]}" -v ON_ERROR_STOP=1 -f "$DPIC_SQL/setup_local_dev_product_6367.sql"

echo ""
echo ">>> 3/4 Verify prerequisites (DB gate)"
"${PG[@]}" -v ON_ERROR_STOP=1 -f "$DPIC_SQL/verify_prerequisites.sql"

echo ""
echo ">>> 4/4 Task service schema (transaction reversal INITIATE)"
"${PG[@]}" -v ON_ERROR_STOP=1 -f "$DPIC_SQL/setup_local_task_reversal_prereqs.sql"

echo ""
echo "=== Setup complete ==="
dpic_check_product_emi || true
dpic_print_next_steps
