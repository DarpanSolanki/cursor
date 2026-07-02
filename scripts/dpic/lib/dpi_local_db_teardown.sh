#!/usr/bin/env bash
# Drop mfi_accounting._* agent backup tables after DPI local runs.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"
dpi_pg -v ON_ERROR_STOP=1 -f "$ROOT/scripts/dpic/sql/helpers/drop_local_dpi_backup_tables.sql"
