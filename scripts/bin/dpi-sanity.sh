#!/usr/bin/env bash
# DPI batch sanity: grace-chain E2E + multi-EMI + fixture EOD chain.
# DEPRECATED for full coverage — prefer: DPI_REGRESSION_PROFILE=quick scripts/dpic/run_dpi_full_regression.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_fixture_constants.sh"
COMPILE_FLAG=""
[[ "${COMPILE:-1}" == "1" ]] && COMPILE_FLAG="--compile"

echo "=== DPI sanity — ensure accounting ==="
bash "$ROOT/scripts/bin/novopay-service.sh" ensure accounting $COMPILE_FLAG

echo ""
echo "=== DPI sanity — multi-EMI installment_id E2E (grace-chain LAN $DPI_GRACE_CHAIN_LAN) ==="
JOB_TIME="${MULTI_EMI_JOB_TIME:-$DPI_MULTI_EMI_JOB_TIME}" \
  bash "$ROOT/scripts/dpic/run_multi_emi_installment_e2e.sh"

echo ""
echo "=== DPI sanity — grace E2E (grace-chain LAN $DPI_GRACE_CHAIN_LAN) ==="
JOB_TIME="${GRACE_JOB_TIME:-$DPI_GRACE_JOB_TIME}" \
  bash "$ROOT/scripts/dpic/run_grace_dpi_e2e.sh"

echo ""
echo "=== DPI sanity — EOD chain on fixture LAN $DPI_FIXTURE_LAN ==="
JOB_TIME="${JOB_TIME:-$DPI_GRACE_OVERLAP_JOB_TIME}" \
  LOAN_ACCOUNT_ID="$DPI_FIXTURE_LOAN_ID" ACCOUNT_NUMBER="$DPI_FIXTURE_LAN" DEMO_LAN="$DPI_FIXTURE_LAN" \
  bash "$ROOT/scripts/dpic/run_eod_dpi_only.sh"

echo ""
echo "=== DPI sanity PASS ==="
