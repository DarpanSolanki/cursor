#!/usr/bin/env bash
# getPartPrepaymentBPIAmount — broken-period DPI (bpd_amount) for rescheduling date.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"

NTEST="$ROOT/scripts/bin/ntest.sh"
fail() { echo "FAIL: $*" >&2; exit 1; }

echo "=== DPI getPartPrepaymentBPIAmount (LAN=$ACCOUNT_NUMBER) ==="
dpi_ensure_accounting
dpi_ensure_masterdata
dpi_export_correlators
dpi_restore_api_state

RESCHED_MS="${RESCHEDULING_EFFECTIVE_MS:-$JOB_TIME}"
export RESCHEDULING_EFFECTIVE_MS="$RESCHED_MS"

echo ">>> getPartPrepaymentBPIAmount rescheduling_effective_date=$RESCHED_MS"
"$NTEST" run dpic.part_prepayment_bpi_api || fail "part_prepayment_bpi_api"

echo "=== DPI getPartPrepaymentBPIAmount PASS ==="
