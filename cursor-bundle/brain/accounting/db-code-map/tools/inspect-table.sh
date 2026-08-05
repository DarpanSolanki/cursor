#!/usr/bin/env bash
# inspect-table.sh — for a given mfi_accounting table, dump:
#   1. Live schema from mfi_qa3 (column name, type, nullable, default)
#   2. Row count
#   3. JPA entity class(es) in accounting source
#   4. DAO + Repository classes
#   5. Processor classes that reference the entity
#   6. Orchestration Requests that wire those processors
#
# Usage: inspect-table.sh <table_name>
#   e.g.  inspect-table.sh loan_account

set -euo pipefail
TABLE="${1:-}"
[[ -z "$TABLE" ]] && { echo "Usage: $0 <table_name>"; exit 1; }

# Workspace root = …/sliProd (this file lives under cursor-bundle/brain/.../tools/)
WS="$(cd "$(dirname "$0")/../../../../.." && pwd)"
DB_QA3="$WS/scripts/db-qa3.sh"
ACC_SRC="$WS/trustt-platform-accounting/src/main/java"
ACC_ORC="$WS/trustt-platform-accounting/deploy/application/orchestration"

dbq() { bash "$DB_QA3" --sql "$1"; }

echo "============================================================"
echo "TABLE  : mfi_accounting.$TABLE"
echo "============================================================"
echo
echo "--- SCHEMA (live from mfi_qa3) ---"
dbq "
SELECT column_name, data_type,
       CASE WHEN is_nullable='YES' THEN 'null' ELSE 'NOT NULL' END AS nullable,
       COALESCE(column_default, '') AS default_val
  FROM information_schema.columns
 WHERE table_schema = 'mfi_accounting' AND table_name = '$TABLE'
 ORDER BY ordinal_position;"

echo
echo "--- ROW COUNT (mfi_qa3) ---"
dbq "SELECT COUNT(*) AS rows FROM mfi_accounting.$TABLE;" 2>/dev/null || echo "(count failed)"

echo
echo "--- INDEXES (mfi_qa3) ---"
dbq "
SELECT indexname, indexdef
  FROM pg_indexes
 WHERE schemaname = 'mfi_accounting' AND tablename = '$TABLE';" 2>/dev/null || echo "(indexes query failed)"

echo
echo "--- JPA ENTITY (annotated @Table(name=\"$TABLE\")) ---"
grep -rln "@Table(name *= *\"$TABLE\")" "$ACC_SRC" 2>/dev/null | head -5 || echo "(none found)"

echo
echo "--- ENTITY CLASSES referencing the table name as string ---"
grep -rln "\"$TABLE\"" "$ACC_SRC" 2>/dev/null | head -10 || echo "(none)"

echo
echo "--- DAO + REPOSITORY classes near these entities ---"
ENT=$(grep -rln "@Table(name *= *\"$TABLE\")" "$ACC_SRC" 2>/dev/null | head -1)
if [[ -n "$ENT" ]]; then
  ENT_DIR=$(dirname "$ENT")
  PKG_PARENT=$(dirname "$ENT_DIR")
  echo "Entity dir : $ENT_DIR"
  echo "Looking in : $PKG_PARENT"
  ls "$PKG_PARENT"/dao/ 2>/dev/null | sed 's/^/  dao\//' || true
  ls "$PKG_PARENT"/repository/ 2>/dev/null | sed 's/^/  repository\//' || true
  ls "$PKG_PARENT"/daoservice/ 2>/dev/null | sed 's/^/  daoservice\//' || true
  ls "$PKG_PARENT"/processor/ 2>/dev/null | sed 's/^/  processor\//' | head -20 || true
fi

echo
echo "--- PROCESSORS referencing the entity class ---"
if [[ -n "$ENT" ]]; then
  ENT_CLASS=$(basename "$ENT" .java)
  echo "Entity class: $ENT_CLASS"
  grep -rln "import .*$ENT_CLASS" "$ACC_SRC" --include='*Processor*.java' 2>/dev/null | head -20 || echo "(none)"
fi

echo
echo "--- ORCHESTRATION REQUESTS containing those processors (heuristic) ---"
if [[ -n "$ENT" ]]; then
  PROCS=$(grep -rln "import .*$(basename "$ENT" .java)" "$ACC_SRC" --include='*Processor*.java' 2>/dev/null | xargs -I{} basename {} .java)
  for proc in $PROCS; do
    # Spring bean name = camelCase of class name (first letter lowercase)
    bean=$(echo "$proc" | awk '{print tolower(substr($0,1,1)) substr($0,2)}')
    matches=$(grep -l "bean=\"$bean\"" "$ACC_ORC"/*.xml 2>/dev/null || true)
    if [[ -n "$matches" ]]; then
      for f in $matches; do
        echo "  $proc → bean=$bean → in $(basename $f)"
        grep -B2 "bean=\"$bean\"" "$f" 2>/dev/null | grep "<Request name" | head -3 | sed 's/^/      /'
      done
    fi
  done | head -40
fi

echo
echo "============================================================"
echo "END inspect: $TABLE"
echo "============================================================"
