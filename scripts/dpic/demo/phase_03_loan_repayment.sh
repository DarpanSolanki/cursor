#!/usr/bin/env bash
# Phase 3 — Direct loanRepayment: overdue EMI + billed DPI settled (~3s).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export REPAY_MS="${REPAY_MS:-}"
export REPAY_DATE="${REPAY_DATE:-}"
exec bash "$SCRIPT_DIR/step_07_loan_repayment.sh"
