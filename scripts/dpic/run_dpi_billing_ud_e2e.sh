#!/usr/bin/env bash
# E2E: DPI calc+booking+billing then UD §5.4 billing assertions.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"

export LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-8060160}"
export JOB_TIME="${JOB_TIME:-1784464200000}"
export GO_LIVE_ISO="${GO_LIVE_ISO:-2026-04-15}"
export END_DATE="${END_DATE:-2026-07-19}"
export GO_LIVE_DDMM="${GO_LIVE_DDMM:-15-04-2026}"
export QUARANTINE_PORTFOLIO="${QUARANTINE_PORTFOLIO:-1}"
export SYNC_PAST_DUE="${SYNC_PAST_DUE:-1}"

dpi_ensure_accounting
dpi_set_go_live_and_refresh "$GO_LIVE_DDMM" "7676"

dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/restore_demo_installments_after_post_maturity_e2e.sql" >/dev/null

dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v grace_days="${GRACE_DAYS:-3}" \
  -f "$ROOT/scripts/dpic/sql/helpers/setup_grace_dpi_e2e.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/setup_multi_emi_dpi_e2e.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/quarantine_dpd_portfolio.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/purge_dpi_accruals_for_loan.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/reset_dpi_booking_replay.sql" >/dev/null

export ROOT NTEST="$ROOT/scripts/bin/ntest.sh"
chmod +x "$ROOT/scripts/dpic/lib/dpi_run_milestone_eod.sh"
bash "$ROOT/scripts/dpic/lib/dpi_run_milestone_eod.sh" milestones "$GO_LIVE_ISO" "$END_DATE"
bash "$ROOT/scripts/dpic/run_dpi_billing_ud_verify.sh"

echo "=== DPI billing UD next-EMI e2e PASS ==="
