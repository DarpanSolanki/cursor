#!/usr/bin/env bash
# Canonical local DPI fixture LANs / loan_ids — update here after purge + fresh disburse.
#
# Roles:
#   DPI_FIXTURE_*     — standard regression (posting calendar, EOD txn, billing UD, APIs)
#   DPI_GRACE_CHAIN_* — grace / overlap / two-EMI / booking-anchor (SHARED LAN — serialize;
#                       each script must dpi_isolate_loan_for_case before setup)
#   DPI_SHG_*         — SDCP-11012 parent=sum(children) parity
#   DPI_CHILD_JLG_*   — childLoanRepayment billed DPI appropriation
[[ -n "${_DPI_FIXTURE_CONSTANTS_LOADED:-}" ]] && return 0
_DPI_FIXTURE_CONSTANTS_LOADED=1
set -euo pipefail

readonly DPI_FIXTURE_LOAN_ID=8060160
readonly DPI_FIXTURE_LAN=6004044425

readonly DPI_GRACE_CHAIN_LOAN_ID=8057160
readonly DPI_GRACE_CHAIN_LAN=6004041325

readonly DPI_SHG_PARENT_LOAN_ID=116360
readonly DPI_SHG_PARENT_LAN=6000001074

readonly DPI_CHILD_JLG_LOAN_ID=8048470
readonly DPI_CHILD_JLG_LAN=6004029335

# 18:00 IST job_time anchors
readonly DPI_GRACE_JOB_TIME=1779280200000          # 2026-05-20 — day after EMI1 grace gate
readonly DPI_GRACE_OVERLAP_JOB_TIME=1781699400000  # 2026-06-17 — EMI2 in grace, EMI1 accrues
readonly DPI_MULTI_EMI_JOB_TIME=1782563400000      # 2026-06-27 — multi-EMI installment stamp
readonly DPI_FIXTURE_JOB_TIME=1782563400000        # demo fixture EOD / API restore default
readonly DPI_SHG_PARITY_JOB_TIME=1749990600000      # 2025-06-15 18:00 IST

dpi_use_fixture_loan() {
  export LOAN_ACCOUNT_ID="$DPI_FIXTURE_LOAN_ID"
  export ACCOUNT_NUMBER="$DPI_FIXTURE_LAN"
  export DEMO_LAN="$DPI_FIXTURE_LAN"
}

dpi_use_grace_chain_loan() {
  export LOAN_ACCOUNT_ID="$DPI_GRACE_CHAIN_LOAN_ID"
  export ACCOUNT_NUMBER="$DPI_GRACE_CHAIN_LAN"
  export DEMO_LAN="$DPI_GRACE_CHAIN_LAN"
}

dpi_use_shg_parent_loan() {
  export PARENT_LOAN_ACCOUNT_ID="$DPI_SHG_PARENT_LOAN_ID"
  export LOAN_ACCOUNT_ID="$DPI_SHG_PARENT_LOAN_ID"
  export ACCOUNT_NUMBER="$DPI_SHG_PARENT_LAN"
}
