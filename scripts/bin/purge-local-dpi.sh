#!/usr/bin/env bash
# Wipe all local DPI accruals/dues/GL txns + drop agent backup tables. Local only.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WRITE="$ROOT/scripts/bin/db-local-write.sh"

echo "=== purge-local-dpi: wipe DPI accruals / dues / GL txns (local) ==="
"$WRITE" --file "$ROOT/scripts/dpic/sql/helpers/purge_local_dpi_all.sql"

if [[ -f "$ROOT/scripts/dpic/sql/helpers/drop_local_dpi_backup_tables.sql" ]]; then
  echo "=== purge-local-dpi: drop backup tables ==="
  "$WRITE" --file "$ROOT/scripts/dpic/sql/helpers/drop_local_dpi_backup_tables.sql"
fi

echo "=== purge-local-dpi: done ==="
psql -h 127.0.0.1 -p 5433 -U yugabyte -d yugabyte -v ON_ERROR_STOP=1 -P pager=off -c "
SELECT COUNT(*) AS dpi_accrual_rows FROM mfi_accounting.dpi_accrual_details;
SELECT COUNT(*) AS dpi_due_rows
FROM mfi_accounting.loan_due_details
WHERE component_type = 'DPI' AND is_deleted = false;
"
