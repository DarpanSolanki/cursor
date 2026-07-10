#!/usr/bin/env bash
# Maximum local DPI job coverage — batch chain + APIs + DB assertions (QA-parity target).
# DEPRECATED — use DPI_REGRESSION_PROFILE=full scripts/dpic/run_dpi_full_regression.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_fixture_constants.sh"
export LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-$DPI_FIXTURE_LOAN_ID}"
export COMPILE="${COMPILE:-0}"

echo "=== DPI maximum local regression (loan=$LOAN_ACCOUNT_ID) ==="
echo "WARN: run_dpi_max_regression.sh is deprecated — prefer run_dpi_full_regression.sh"

bash "$ROOT/scripts/bin/novopay-service.sh" ensure accounting ${COMPILE:+--compile}

# 1) Product-specific accrual anchors (grace-chain LAN — scripts self-pin)
export MULTI_EMI_JOB_TIME="${MULTI_EMI_JOB_TIME:-$DPI_MULTI_EMI_JOB_TIME}"
JOB_TIME="$MULTI_EMI_JOB_TIME" bash "$ROOT/scripts/dpic/run_multi_emi_installment_e2e.sh"
echo ""

export GRACE_JOB_TIME="${GRACE_JOB_TIME:-$DPI_GRACE_JOB_TIME}"
JOB_TIME="$GRACE_JOB_TIME" bash "$ROOT/scripts/dpic/run_grace_dpi_e2e.sh"
echo ""

# 2) Full EOD chain + post-EOD DB checks (fixture LAN)
export JOB_TIME="${JOB_TIME:-$DPI_GRACE_OVERLAP_JOB_TIME}"
LOAN_ACCOUNT_ID="$DPI_FIXTURE_LOAN_ID" ACCOUNT_NUMBER="$DPI_FIXTURE_LAN" DEMO_LAN="$DPI_FIXTURE_LAN" \
  bash "$ROOT/scripts/dpic/run_eod_dpi_only.sh"
LOAN_ACCOUNT_ID="$DPI_FIXTURE_LOAN_ID" bash "$ROOT/scripts/dpic/run_dpi_post_eod_verify.sh"
echo ""

# 3) Read APIs (webapp / restructuring / foreclosure)
bash "$ROOT/scripts/dpic/run_restructuring_api_smoke.sh"
bash "$ROOT/scripts/bin/ntest.sh" run dpic.foreclosure_sim
echo ""

# 4) Idempotent re-run: EOD again same job_time (batch purge inside eod script path — add purge)
PG=(psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}")
export PGPASSWORD="${PGPASSWORD:-yugabyte}"
for j in dpiAccrualCalculation dpiAccrualBooking dpiBilling; do
  "${PG[@]}" -v ON_ERROR_STOP=1 -v job_name="$j" -v job_time="$JOB_TIME" \
    -f "$ROOT/scripts/dpic/sql/helpers/purge_batch_job_execution.sql" >/dev/null
done
echo ">>> idempotent EOD replay job_time=$JOB_TIME"
LOAN_ACCOUNT_ID="$DPI_FIXTURE_LOAN_ID" ACCOUNT_NUMBER="$DPI_FIXTURE_LAN" DEMO_LAN="$DPI_FIXTURE_LAN" \
  bash "$ROOT/scripts/dpic/run_eod_dpi_only.sh"
LOAN_ACCOUNT_ID="$DPI_FIXTURE_LOAN_ID" bash "$ROOT/scripts/dpic/run_dpi_post_eod_verify.sh"
echo ""

echo "=== DPI maximum local regression PASS ==="
