#!/usr/bin/env bash
# DPI batch sanity: ensure accounting is up, then grace E2E + EOD chain.
# Grace runs first (isolated calc window); EOD chain second (full calc→booking→billing).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPILE_FLAG=""
[[ "${COMPILE:-1}" == "1" ]] && COMPILE_FLAG="--compile"

echo "=== DPI sanity — ensure accounting ==="
bash "$ROOT/scripts/bin/novopay-service.sh" ensure accounting $COMPILE_FLAG

JOB_TIME="${JOB_TIME:-1781699400000}"
LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-8060160}"
GRACE_JOB_TIME="${GRACE_JOB_TIME:-1779712200000}"

echo ""
echo "=== DPI sanity — multi-EMI installment_id E2E (full overdue window) ==="
MULTI_EMI_JOB_TIME="${MULTI_EMI_JOB_TIME:-1782563400000}"
JOB_TIME="$MULTI_EMI_JOB_TIME" LOAN_ACCOUNT_ID="$LOAN_ACCOUNT_ID" bash "$ROOT/scripts/dpic/run_multi_emi_installment_e2e.sh"

echo ""
echo "=== DPI sanity — grace E2E (isolated accrual window) ==="
JOB_TIME="$GRACE_JOB_TIME" LOAN_ACCOUNT_ID="$LOAN_ACCOUNT_ID" bash "$ROOT/scripts/dpic/run_grace_dpi_e2e.sh"

echo ""
echo "=== DPI sanity — EOD chain (calc → booking → billing) ==="
JOB_TIME="$JOB_TIME" LOAN_ACCOUNT_ID="$LOAN_ACCOUNT_ID" bash "$ROOT/scripts/dpic/run_eod_dpi_only.sh"

echo ""
echo "=== DPI sanity PASS ==="
