#!/usr/bin/env bash
# Local Yugabyte writes only (127.0.0.1:5433). Agents use this instead of raw psql to remote envs.
#
# Usage:
#   scripts/bin/db-local-write.sh --file scripts/dpic/sql/helpers/purge_local_dpi_all.sql
#   scripts/bin/db-local-write.sh --sql "UPDATE ..."
#   scripts/bin/db-local-write.sh --file foo.sql --var loan_account_id=8060160
set -euo pipefail

PGHOST="127.0.0.1"
PGPORT="5433"
PGUSER="yugabyte"
PGPASSWORD="yugabyte"
PGDATABASE="yugabyte"
export PGPASSWORD

# Ignore inherited QA/prod PGHOST from shell profile — local writes are always localhost.

SQL=""
FILE=""
declare -a PSQL_VARS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --sql) SQL="$2"; shift ;;
    --file) FILE="$2"; shift ;;
    --var) PSQL_VARS+=(-v "${2%%=*}=${2#*=}"); shift ;;
    -h|--help)
      sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
  shift
done

if [[ -n "$FILE" ]]; then
  [[ -f "$FILE" ]] || { echo "File not found: $FILE" >&2; exit 1; }
  exec psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" \
    -v ON_ERROR_STOP=1 "${PSQL_VARS[@]}" -f "$FILE"
fi

if [[ -n "$SQL" ]]; then
  exec psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" \
    -v ON_ERROR_STOP=1 "${PSQL_VARS[@]}" -c "$SQL"
fi

echo "Usage: $0 (--file path.sql | --sql '...') [--var k=v ...]" >&2
exit 1
