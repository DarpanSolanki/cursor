#!/usr/bin/env bash
# Local SDCP-10199 parent last-child DFC verify (post insurance job).
# Usage: bash scripts/dcf_sanity/run_parent_last_child_dfc_local.sh <parent_lan>
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PARENT_LAN="${1:?parent LAN required}"
DB_HOST="${YB_HOST:-localhost}"
DB_PORT="${YB_PORT:-5433}"
DB_USER="${YB_USER:-yugabyte}"
DB_NAME="${YB_DB:-yugabyte}"
export PGPASSWORD="${PGPASSWORD:-yugabyte}"

echo "[parent-last-child-dfc] verify parent=$PARENT_LAN"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 \
  -v parent_lan="$PARENT_LAN" \
  -f "$ROOT/scripts/dcf_sanity/parent_last_child_dfc_verify.sql"

python3 "$ROOT/scripts/dcf_sanity/parent_last_child_dfc_assert.py" --parent-lan "$PARENT_LAN"
