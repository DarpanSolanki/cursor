#!/usr/bin/env bash
# Canonical DPI regression entrypoint — QA-shaped order, profile-scoped runtime.
#
#   DPI_REGRESSION_PROFILE=quick|standard|full|maturity  (default: standard)
#
# Pre-step: reset_dpi_fixtures.sh (skip with SKIP_DPI_FIXTURE_RESET=1).
# Quick profile starts with run_dpi_three_job_verify.sh (ntest batch APIs on 8060160).
#
# Profiles:
#   quick     — reset + three_job (sealed→posted→billed) + booking guard + milestone two_emi
#               + grace + overlap + booking_anchor + shg (~12–18 min)
#   standard  — + posting_calendar + eod_txn + go_live_ud + cross_eod (~30 min)
#   full      — + billing_ud + integration_smoke + ud_compliance
#   maturity  — + post_maturity + post_maturity_catchup + fixture restore
#
# Fixture loan 8060160 for standard+ blocks; grace-chain 8057160 for grace/overlap/two_emi/shg.
# Quick uses DPI_CALENDAR_MODE=milestones on two_emi (not daily May→Jul).
# Maturity teardown: restore_demo_installments_after_post_maturity_e2e.sql after post-maturity block.
#
# Exit non-zero when any step fails; prints PASS/FAIL summary table at end.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DPIC="$ROOT/scripts/dpic"
# shellcheck disable=SC1091
source "$DPIC/lib/dpi_fixture_pin.sh"

PROFILE="${DPI_REGRESSION_PROFILE:-standard}"
PROFILE="${PROFILE,,}"

declare -a _REG_NAMES=()
declare -a _REG_STATUS=()
_REG_FAILED=0

fail_msg() { echo "DPI_FULL_REGRESSION_FAIL: $*" >&2; }

run_step() {
  local name="$1"
  shift
  echo ""
  echo "========== [$PROFILE] $name =========="
  if "$@"; then
    _REG_NAMES+=("$name")
    _REG_STATUS+=("PASS")
    echo ">>> $name PASS"
  else
    _REG_NAMES+=("$name")
    _REG_STATUS+=("FAIL")
    _REG_FAILED=1
    fail_msg "$name"
    echo ">>> $name FAIL (continuing)"
  fi
}

profile_ge() {
  local want="$1"
  case "$PROFILE" in
    quick) [[ "$want" == "quick" ]] ;;
    standard) [[ "$want" == "quick" || "$want" == "standard" ]] ;;
    full) [[ "$want" == "quick" || "$want" == "standard" || "$want" == "full" ]] ;;
    maturity)
      [[ "$want" == "quick" || "$want" == "standard" || "$want" == "full" || "$want" == "maturity" ]]
      ;;
    *)
      fail_msg "unknown DPI_REGRESSION_PROFILE=$PROFILE (use quick|standard|full|maturity)"
      exit 2
      ;;
  esac
}

restore_maturity_fixture() {
  dpi_use_fixture_loan
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -f "$DPIC/sql/helpers/restore_demo_installments_after_post_maturity_e2e.sql" >/dev/null 2>&1 || true
  echo ">>> maturity fixture restore OK (loan=$LOAN_ACCOUNT_ID)"
}

echo "=== DPI full regression profile=$PROFILE ==="
bash "$ROOT/scripts/bin/agent-ops.sh" ensure accounting --compile 2>/dev/null || true

if [[ "${SKIP_DPI_FIXTURE_RESET:-0}" != "1" ]]; then
  run_step fixture_reset bash "$DPIC/reset_dpi_fixtures.sh"
fi

if profile_ge quick; then
  run_step three_job_verify bash "$DPIC/run_dpi_three_job_verify.sh"
  run_step posting_guards bash "$ROOT/scripts/bin/dpi-booking-posting-guard.sh"
  # two_emi purges global DPI state — run before grace-chain scenarios on same LAN
  # milestones: EMI due + month-end hops (keeps quick under ~20 min vs daily May→Jul)
  run_step two_emi_full_chain \
    env DPI_CALENDAR_MODE=milestones END_DATE=2026-07-01 GO_LIVE_ISO=2026-05-01 \
    bash "$DPIC/run_dpi_two_emi_full_chain.sh"
  run_step grace_e2e bash "$DPIC/run_grace_dpi_e2e.sh"
  run_step grace_overlap_e2e bash "$DPIC/run_grace_overlap_dpi_e2e.sh"
  run_step booking_anchor_next_due bash "$DPIC/run_dpi_booking_anchor_e2e.sh"
  run_step shg_parent_child_parity bash "$DPIC/run_dpi_shg_parent_child_parity.sh"
fi

if profile_ge standard; then
  dpi_use_fixture_loan
  run_step posting_calendar_regression bash "$DPIC/run_dpi_posting_calendar_regression.sh"
  run_step eod_txn_regression bash "$DPIC/run_dpi_eod_txn_regression.sh"
  run_step go_live_ud bash "$DPIC/run_dpi_go_live_ud_e2e.sh"
  run_step cross_eod_replay bash "$DPIC/run_dpi_cross_eod_replay_guard.sh"
fi

if profile_ge full; then
  dpi_use_fixture_loan
  run_step billing_ud_next_emi bash "$DPIC/run_dpi_billing_ud_e2e.sh"
  run_step integration_smoke bash "$DPIC/run_dpi_integration_smoke.sh"
  run_step ud_compliance bash "$DPIC/run_dpi_ud_compliance.sh"
fi

if profile_ge maturity; then
  dpi_use_fixture_loan
  run_step post_maturity_billing bash "$DPIC/run_dpi_post_maturity_billing_e2e.sh"
  run_step post_maturity_billing_catchup bash "$DPIC/run_dpi_post_maturity_billing_catchup_e2e.sh"
  restore_maturity_fixture
fi

echo ""
echo "=== DPI regression summary (profile=$PROFILE) ==="
printf "%-36s %s\n" "STEP" "RESULT"
printf "%-36s %s\n" "----" "------"
for i in "${!_REG_NAMES[@]}"; do
  printf "%-36s %s\n" "${_REG_NAMES[$i]}" "${_REG_STATUS[$i]}"
done

if [[ "$_REG_FAILED" -ne 0 ]]; then
  echo ""
  fail_msg "one or more steps failed (profile=$PROFILE)"
  exit 1
fi

echo ""
echo "=== DPI FULL REGRESSION PASS (profile=$PROFILE) ==="
