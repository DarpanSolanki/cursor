#!/usr/bin/env bash
# Read-only local Yugabyte (default: localhost:5433, db yugabyte, schema mfi_accounting).
#
# Usage:
#   scripts/db-local.sh --sql "SELECT version();"
#   scripts/db-local.sh --canned 01-loan-status-by-lan --param account_number=LAN0001234
#   scripts/db-local.sh --file path/to/query.sql
#
# Writes (INSERT/UPDATE/DELETE/DDL) are refused. Use scripts/*.sql via psql for local resets.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CANNED_DIR="$SCRIPT_DIR/db/canned"

PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5433}"
PGUSER="${PGUSER:-yugabyte}"
PGPASSWORD="${PGPASSWORD:-yugabyte}"
PGDATABASE="${PGDATABASE:-yugabyte}"

# If shell profile points at QA/UAT, still use local Yugabyte for investigations.
case "$PGHOST" in
  127.0.0.1|localhost|::1) ;;
  *)
    PGHOST=127.0.0.1
    PGUSER=yugabyte
    PGPASSWORD=yugabyte
    PGDATABASE=yugabyte
    PGPORT=5433
    ;;
esac
export PGPASSWORD

SQL=""
FILE=""
CANNED=""
declare -A PARAMS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --sql)    SQL="$2"; shift ;;
    --file)   FILE="$2"; shift ;;
    --canned) CANNED="$2"; shift ;;
    --param)  k="${2%%=*}"; v="${2#*=}"; PARAMS["$k"]="$v"; shift ;;
    -h|--help)
      sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
  shift
done

if [[ -n "$CANNED" ]]; then
  FILE="$CANNED_DIR/${CANNED}.sql"
  [[ -f "$FILE" ]] || { echo "No canned query: $FILE" >&2; ls "$CANNED_DIR" >&2; exit 1; }
fi

if [[ -n "$FILE" ]]; then
  [[ -f "$FILE" ]] || { echo "File not found: $FILE" >&2; exit 1; }
  SQL="$(cat "$FILE")"
fi

if [[ -z "$SQL" ]]; then
  echo "Usage: $0 (--sql 'SELECT ...' | --file path.sql | --canned <name>) [--param k=v ...]" >&2
  exit 1
fi

for k in "${!PARAMS[@]}"; do
  v="${PARAMS[$k]}"
  SQL="${SQL//:$k/'$v'}"
done

if echo "$SQL" | grep -qiE '^\s*(INSERT|UPDATE|DELETE|TRUNCATE|DROP|ALTER|CREATE|GRANT|REVOKE)'; then
  echo "Refused: write/DDL SQL. Use scripts/local_reset_*.sql via psql for local DB changes." >&2
  exit 1
fi

psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -v ON_ERROR_STOP=1 -P pager=off -c "$SQL"
