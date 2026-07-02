#!/usr/bin/env bash
# DPIC live demo — run ONE phase at a time during presentation.
#
#   bash scripts/dpic/demo/run_demo.sh phase1   # fresh LAN + fast EOD (~25s)
#   bash scripts/dpic/demo/run_demo.sh phase2   # GET APIs — DPI keys (~5s)
#   bash scripts/dpic/demo/run_demo.sh phase3   # loanRepayment (~3s)
#   bash scripts/dpic/demo/run_demo.sh phase4   # reverse last repayment (~5s)
#   bash scripts/dpic/demo/run_demo.sh status   # LAN + which phase is ready
#
# Automation only (not for live demo):
#   bash scripts/dpic/demo/run_demo.sh all
#
# First-time DB: SKIP_SETUP=0 bash scripts/dpic/demo/run_demo.sh phase1
# Pause after each phase: INTERACTIVE=1 bash scripts/dpic/demo/run_demo.sh phase2
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
DEMO_DIR="$(cd "$(dirname "$0")" && pwd)"
PHASE="${1:-}"

usage() {
  cat <<EOF
Usage: bash scripts/dpic/demo/run_demo.sh <phase>

Live demo (run one at a time):
  phase1 | 1   Disburse fresh LAN + fast EOD through demo day (~25s)
  phase2 | 2   GET APIs — show DPI keys in responses (~5s)
  phase3 | 3   loanRepayment — settle overdue + billed DPI (~3s)
  phase4 | 4   loanAccountTransactionReversal INITIATE + APPROVE (~5s)
  status       Show LAN from state + which phases are ready

Automation (CI / regression — not for presentation):
  all          phase1 → phase2 → phase3 → phase4

Accounting :8002 (mfi). Task :8019 (mfi_integration_v3.3.1.1). Yugabyte :5433.
State: scripts/scratch/dpic_demo_state.env (written in phase1).
EOF
}

case "${PHASE,,}" in
  1|phase1|p1)
    exec bash "$DEMO_DIR/phase_01_disburse_and_jobs.sh"
    ;;
  2|phase2|p2)
    exec bash "$DEMO_DIR/phase_02_show_apis.sh"
    ;;
  3|phase3|p3)
    exec bash "$DEMO_DIR/phase_03_loan_repayment.sh"
    ;;
  4|phase4|p4)
    exec bash "$DEMO_DIR/phase_04_transaction_reversal.sh"
    ;;
  status|st)
    # shellcheck disable=SC1091
    source "$DEMO_DIR/lib/common.sh"
    demo_banner "DPIC demo status"
    demo_show_status
    ;;
  all)
    echo ">>> Automation: running all phases (use phase1..4 individually for live demo)" >&2
    bash "$DEMO_DIR/phase_01_disburse_and_jobs.sh"
    bash "$DEMO_DIR/phase_02_show_apis.sh"
    bash "$DEMO_DIR/phase_03_loan_repayment.sh"
    bash "$DEMO_DIR/phase_04_transaction_reversal.sh"
    ;;
  -h|--help|help|"")
    usage
    [[ -n "$PHASE" ]] && exit 0 || exit 1
    ;;
  *)
    echo "Unknown phase: $PHASE" >&2
    usage
    exit 1
    ;;
esac
