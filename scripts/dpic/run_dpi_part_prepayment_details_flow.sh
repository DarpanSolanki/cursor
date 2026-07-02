#!/usr/bin/env bash
# getLoanAccountPartPrepaymentDetails — live bpd_amount from accruals for PENDING row.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"

NTEST="$ROOT/scripts/bin/ntest.sh"
fail() { echo "FAIL: $*" >&2; exit 1; }

echo "=== DPI getLoanAccountPartPrepaymentDetails (LAN=$ACCOUNT_NUMBER) ==="
dpi_ensure_accounting
dpi_ensure_masterdata
dpi_export_correlators
dpi_restore_api_state

RESCHED_MS="${RESCHEDULING_EFFECTIVE_MS:-$JOB_TIME}"
dpi_pg -v ON_ERROR_STOP=1 \
  -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -v rescheduling_effective_ms="$RESCHED_MS" \
  -f "$ROOT/scripts/dpic/sql/helpers/setup_part_prepayment_pending.sql" >/dev/null

export RESCHEDULING_EFFECTIVE_MS="$RESCHED_MS"
echo ">>> getLoanAccountPartPrepaymentDetails status=PENDING"
"$NTEST" run dpic.part_prepayment_details_api || fail "part_prepayment_details_api"

echo "=== DPI getLoanAccountPartPrepaymentDetails PASS ==="
