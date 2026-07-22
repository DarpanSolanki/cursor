#!/usr/bin/env bash
# Local Yugabyte hygiene — orphan pg_temp / pg_toast_temp schemas.
#
# Why: local scripts use CREATE TEMP TABLE (disburse reset, DPI purge, DCF patches).
# On Yugabyte, backends that exit mid-script often leave pg_temp_<uuid>_* schemas behind.
# They are not application data; safe to DROP on localhost only.
#
# Usage:
#   scripts/bin/db-local-hygiene.sh           # audit
#   scripts/bin/db-local-hygiene.sh --clean   # DROP orphan temp schemas
#   scripts/bin/db-local-hygiene.sh --clean --verbose
set -euo pipefail

PGHOST="127.0.0.1"
PGPORT="5433"
PGUSER="yugabyte"
PGPASSWORD="yugabyte"
PGDATABASE="yugabyte"
export PGPASSWORD

CLEAN=0
VERBOSE=0
for a in "$@"; do
  case "$a" in
    --clean|-c) CLEAN=1 ;;
    --verbose|-v) VERBOSE=1 ;;
    -h|--help)
      sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
  esac
done

psql_q() {
  psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -v ON_ERROR_STOP=1 -At -c "$1"
}

echo "=== local Yugabyte DB hygiene ==="

if ! psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -c 'SELECT 1' >/dev/null 2>&1; then
  echo "  · local Yugabyte not reachable on ${PGHOST}:${PGPORT} — skip"
  exit 0
fi

TEMP_NS=$(psql_q "SELECT count(*) FROM pg_namespace WHERE nspname LIKE 'pg_temp%' OR nspname LIKE 'pg_toast_temp%'")
TEMP_TBL=$(psql_q "
SELECT count(*) FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'r' AND n.nspname LIKE 'pg_temp%'
")

echo "  orphan temp schemas: ${TEMP_NS}"
echo "  orphan temp tables:  ${TEMP_TBL}"

if [[ "$VERBOSE" == 1 && "$TEMP_TBL" != "0" ]]; then
  psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -c "
SELECT n.nspname AS schema, c.relname AS table_name
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'r' AND n.nspname LIKE 'pg_temp%'
ORDER BY 1, 2
LIMIT 40;
"
fi

# Permanent table named temp_* — do NOT drop (schema inventory / staging)
if psql_q "SELECT to_regclass('mfi_accounting.temp_unique_gl_code_office_id') IS NOT NULL" | grep -qi t; then
  rows=$(psql_q "SELECT count(*) FROM mfi_accounting.temp_unique_gl_code_office_id")
  echo "  keep mfi_accounting.temp_unique_gl_code_office_id (app table, rows=${rows})"
fi

if [[ "$TEMP_NS" == "0" ]]; then
  echo "✓ No orphan temp schemas"
  exit 0
fi

if [[ "$CLEAN" != 1 ]]; then
  echo "-- Run: bash scripts/bin/db-local-hygiene.sh --clean"
  exit 0
fi

# Batch DROP in one session (much faster than per-schema psql). Local-only.
# Schemas still held by a live backend are skipped (EXCEPTION).
RESULT=$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -v ON_ERROR_STOP=1 -At -c "
DO \$\$
DECLARE
  r record;
  dropped int := 0;
  failed int := 0;
BEGIN
  FOR r IN
    SELECT nspname FROM pg_namespace
    WHERE nspname LIKE 'pg_temp%' OR nspname LIKE 'pg_toast_temp%'
    ORDER BY nspname
  LOOP
    BEGIN
      EXECUTE format('DROP SCHEMA IF EXISTS %I CASCADE', r.nspname);
      dropped := dropped + 1;
    EXCEPTION WHEN OTHERS THEN
      failed := failed + 1;
    END;
  END LOOP;
  RAISE NOTICE 'dropped=% failed=%', dropped, failed;
END
\$\$;
SELECT count(*) FROM pg_namespace WHERE nspname LIKE 'pg_temp%' OR nspname LIKE 'pg_toast_temp%';
" 2>&1)

echo "$RESULT" | grep -E 'NOTICE:|dropped=|^[0-9]+$' || true
AFTER=$(echo "$RESULT" | grep -E '^[0-9]+$' | tail -1)
AFTER="${AFTER:-?}"
echo "  remaining=${AFTER}"
if [[ "$AFTER" == "0" ]]; then
  echo "✓ Orphan temp schemas cleared"
else
  echo "  ⚠ ${AFTER} schema(s) remain (likely live session temps) — reconnect DBeaver/psql or re-run --clean"
fi
exit 0
