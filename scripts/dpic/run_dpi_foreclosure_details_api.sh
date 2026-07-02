#!/usr/bin/env bash
# getLoanForeclosureDetails — requires billed DPI on fixture (run after restore, before repayment).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"
dpi_ensure_accounting
dpi_ensure_masterdata
dpi_export_correlators
dpi_restore_api_state
exec bash "$ROOT/scripts/bin/ntest.sh" run dpic.foreclosure_details_api
