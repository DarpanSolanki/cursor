#!/usr/bin/env bash
# Pre-release gate — QA-shaped: fresh LAN + dual billing + schedule-driven date jumps + schema contract.
# Fixture LAN 8060160 is supplementary regression only, not the sole proof.
#
# Env:
#   RELEASE_GATE_SKIP_CERTIFY=1  — skip slow certify (fresh LAN per scenario)
#   RELEASE_GATE_SKIP_FRESH=1    — skip fresh disburse (fixture-only fast path)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_fixture_pin.sh"

QA_VERIFY="$ROOT/scripts/dpic/lib/run_dpi_qa_verify.sh"
fail() { echo "RELEASE_GATE_FAIL: $*" >&2; exit 1; }
phase() { echo ""; echo "=== release_gate: $* ==="; }

phase "static posting guards (code invariants)"
bash "$ROOT/scripts/bin/dpi-booking-posting-guard.sh" || fail "posting guards"

if [[ "${RELEASE_GATE_SKIP_FRESH:-0}" != "1" ]]; then
  phase "fresh disburse → schedule milestones → full column audit (canonical QA path)"
  bash "$ROOT/scripts/dpic/run_dpi_fresh_disburse_e2e.sh" || fail "fresh_disburse"
  if [[ -f "$ROOT/scripts/dpic/last_certified_fresh_lan.env" ]]; then
    # shellcheck disable=SC1091
    source "$ROOT/scripts/dpic/last_certified_fresh_lan.env"
    bash "$QA_VERIFY" "$LOAN_ACCOUNT_ID" "$END_DATE" || fail "fresh LAN QA verify"
    echo "  fresh LAN $ACCOUNT_NUMBER QA verify OK through $END_DATE"
  fi
else
  echo "  (skipped fresh disburse — RELEASE_GATE_SKIP_FRESH=1)"
fi

phase "dual billing (2 DPI due rows + 2 billing GL txns, date jumps from schedule)"
if [[ -f "$ROOT/scripts/dpic/last_certified_fresh_lan.env" && "${RELEASE_GATE_SKIP_FRESH:-0}" != "1" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/scripts/dpic/last_certified_fresh_lan.env"
  DUAL_BILLING_MODE=fresh LOAN_ACCOUNT_ID="$LOAN_ACCOUNT_ID" \
    bash "$ROOT/scripts/dpic/run_dpi_dual_billing_e2e.sh" || fail "dual_billing_fresh"
else
  DUAL_BILLING_MODE=fixture dpi_use_fixture_loan \
    bash "$ROOT/scripts/dpic/run_dpi_dual_billing_e2e.sh" || fail "dual_billing_fixture"
fi

phase "fixture regression — posting calendar + EOD txn + replay (8060160)"
dpi_use_fixture_loan
LOAN_ACCOUNT_ID=8060160 END_DATE=2026-07-19 \
  bash "$ROOT/scripts/dpic/run_dpi_posting_calendar_regression.sh" || fail "posting_calendar"
LOAN_ACCOUNT_ID=8060160 \
  bash "$ROOT/scripts/dpic/run_dpi_eod_txn_regression.sh" || fail "eod_txn"
LOAN_ACCOUNT_ID=8060160 \
  bash "$ROOT/scripts/dpic/run_dpi_cross_eod_replay_guard.sh" || fail "cross_eod"

phase "grace full pipeline (3 jobs after grace gate)"
dpi_use_fixture_loan
GRACE_FULL_PIPELINE=1 bash "$ROOT/scripts/dpic/run_grace_dpi_e2e.sh" || fail "grace_full"

if [[ "${RELEASE_GATE_SKIP_CERTIFY:-0}" != "1" ]]; then
  phase "certify — fresh LAN per scenario (single + multi overdue + pre_emi)"
  dpi_clear_fresh_env_leak
  CERT_MODE=shared DPI_UD_CERTIFY=1 \
    bash "$ROOT/scripts/dpic/certify_dpi_scenarios.sh" \
    --scenarios single_overdue,multi_overdue,pre_emi || fail "certify"
else
  echo "  (skipped certify — RELEASE_GATE_SKIP_CERTIFY=1)"
fi

bash "$ROOT/scripts/dpic/lib/dpi_local_db_teardown.sh" 2>/dev/null || true
echo ""
echo "=== DPI RELEASE GATE PASS (fresh LAN + dual billing + fixture + QA verify) ==="
