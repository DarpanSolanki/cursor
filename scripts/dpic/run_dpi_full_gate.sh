#!/usr/bin/env bash
# Mandatory DPI completion gate — QA-shaped order: fresh proof first, fixture regression second.
# Agents must PASS this before claiming DPI verified.
#
# Env:
#   DPI_FULL_GATE_SKIP_CERTIFY=1 — skip certify phase (faster)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DPIC="$ROOT/scripts/dpic"
EVIDENCE="$DPIC/last_certified_fresh_lan.env"
# shellcheck disable=SC1091
source "$DPIC/lib/dpi_demo_fixture.sh"
# shellcheck disable=SC1091
source "$DPIC/lib/dpi_fixture_pin.sh"

QA_VERIFY="$DPIC/lib/run_dpi_qa_verify.sh"
export DPI_UD_PROFILE="${DPI_UD_PROFILE:-full}"
export DPI_UD_CERTIFY="${DPI_UD_CERTIFY:-1}"

fail() { echo "DPI_FULL_GATE FAIL: $*" >&2; exit 1; }
phase() { echo ""; echo "========== $* =========="; }

phase "static guards"
bash "$ROOT/scripts/bin/dpi-booking-posting-guard.sh" || fail "posting guards"

phase "fresh disburse → milestone EOD → QA verify (canonical)"
bash "$DPIC/run_dpi_fresh_disburse_e2e.sh" || fail "fresh_disburse_e2e"
if [[ -f "$EVIDENCE" ]]; then
  # shellcheck disable=SC1090
  source "$EVIDENCE"
  bash "$QA_VERIFY" "$LOAN_ACCOUNT_ID" "$END_DATE" || fail "fresh QA verify"
fi

phase "dual billing on fresh LAN (natural schedule, two billing events)"
if [[ -f "$EVIDENCE" ]]; then
  # shellcheck disable=SC1090
  source "$EVIDENCE"
  DUAL_BILLING_MODE=fresh LOAN_ACCOUNT_ID="$LOAN_ACCOUNT_ID" \
    bash "$DPIC/run_dpi_dual_billing_e2e.sh" || fail "dual_billing_fresh"
else
  fail "missing $EVIDENCE after fresh disburse"
fi

phase "fixture regression (8060160 — supplementary)"
dpi_use_fixture_loan
bash "$DPIC/run_dpi_posting_calendar_regression.sh" || fail "posting_calendar"
bash "$DPIC/run_dpi_emi_first_anchor_regression.sh" || fail "emi_first_anchor"
bash "$DPIC/run_dpi_eod_txn_regression.sh" || fail "eod_txn"
bash "$ROOT/scripts/bin/agent-ops.sh" ensure accounting --compile 2>/dev/null || true
bash "$DPIC/run_dpi_ud_compliance.sh" || fail "ud_compliance"
DUAL_BILLING_MODE=fixture bash "$DPIC/run_dpi_dual_billing_e2e.sh" || fail "dual_billing_fixture"

if [[ -f "$EVIDENCE" ]]; then
  # shellcheck disable=SC1090
  source "$EVIDENCE"
  phase "replay QA verify on recorded fresh LAN ${ACCOUNT_NUMBER:-?}"
  bash "$QA_VERIFY" "$LOAN_ACCOUNT_ID" "$END_DATE" || fail "replay QA verify"
  echo "CERTIFIED_LAN=$ACCOUNT_NUMBER LOAN_ACCOUNT_ID=$LOAN_ACCOUNT_ID END_DATE=$END_DATE"
fi

if [[ "${DPI_FULL_GATE_SKIP_CERTIFY:-0}" != "1" ]]; then
  phase "certify scenarios (shared fresh LANs)"
  dpi_clear_fresh_env_leak
  CERT_MODE=shared DPI_UD_CERTIFY=1 \
    bash "$DPIC/certify_dpi_scenarios.sh" \
    --scenarios single_overdue,multi_overdue,pre_emi || fail "certify"
fi

phase "DPI FULL GATE PASS"
