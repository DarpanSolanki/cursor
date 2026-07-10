#!/usr/bin/env bash
# Fast local DPI EOD: quarantine → sync past_due → real calc/booking/billing (ntest + wait_batch_job).
# SEED_CALC_WINDOW=1 is a documented bypass only — default off; jobs must produce accrual rows.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"

JOB_TIME="${JOB_TIME:-1781267400000}"
LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-}"
SEED_CALC_WINDOW="${SEED_CALC_WINDOW:-0}"
SYNC_PAST_DUE="${SYNC_PAST_DUE:-1}"
QUARANTINE_PORTFOLIO="${QUARANTINE_PORTFOLIO:-1}"
chmod +x "$ROOT/scripts/dpic/lib/wait_batch_job.sh" 2>/dev/null || true

if [[ -n "$LOAN_ACCOUNT_ID" && "$QUARANTINE_PORTFOLIO" == "1" ]]; then
  echo ">>> Quarantine DPD portfolio (only loan $LOAN_ACCOUNT_ID eligible)"
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -f "$ROOT/scripts/dpic/sql/helpers/quarantine_dpd_portfolio.sql"
fi

if [[ -n "$LOAN_ACCOUNT_ID" && "$SYNC_PAST_DUE" == "1" ]]; then
  echo ">>> Sync past_due_days loan_account_id=$LOAN_ACCOUNT_ID"
  dpi_pg -v ON_ERROR_STOP=1 \
    -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -v business_date_ms="$JOB_TIME" \
    -f "$ROOT/scripts/dpic/sql/helpers/sync_demo_past_due.sql"
fi

if [[ -n "$LOAN_ACCOUNT_ID" && "$SEED_CALC_WINDOW" == "1" ]]; then
  echo ">>> BYPASS: seed_calc_window.sql (documented workaround — prefer jobs; see sql/helpers/seed_calc_window.sql)"
  dpi_pg -v ON_ERROR_STOP=1 \
    -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -v business_date_ms="$JOB_TIME" \
    -f "$ROOT/scripts/dpic/sql/helpers/seed_calc_window.sql"
fi

dpi_call_eod_chain "$JOB_TIME"

echo "Done (${LOAN_ACCOUNT_ID:-all loans})."
