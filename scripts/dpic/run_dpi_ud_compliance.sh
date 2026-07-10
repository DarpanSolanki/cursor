#!/usr/bin/env bash
# UD §5.4 DPI batch compliance — profile-scoped (ship-loop runs subsets; full = manual/CI).
#
# DPI_UD_PROFILE (comma-separated, or "full"):
#   grace | multi | go-live | certify | full
# Examples:
#   DPI_UD_PROFILE=go-live,grace  — only those slices on demo LAN 8060160
#   DPI_UD_PROFILE=full           — all slices + optional certify (DPI_UD_CERTIFY=1)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_fixture_constants.sh"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"
export LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-8060160}"
export GRACE_JOB_TIME="${GRACE_JOB_TIME:-$DPI_GRACE_JOB_TIME}"
export MULTI_EMI_JOB_TIME="${MULTI_EMI_JOB_TIME:-$DPI_MULTI_EMI_JOB_TIME}"
export JOB_TIME="${JOB_TIME:-$MULTI_EMI_JOB_TIME}"
export DPI_UD_PROFILE="${DPI_UD_PROFILE:-full}"

fail() { echo "FAIL: $*" >&2; exit 1; }

profile_wants() {
  local key="$1"
  [[ "$DPI_UD_PROFILE" == "full" ]] && return 0
  [[ ",${DPI_UD_PROFILE}," == *",${key},"* ]]
}

echo "=== DPI UD compliance (loan=$LOAN_ACCOUNT_ID profile=$DPI_UD_PROFILE) ==="

dpi_ensure_accounting
dpi_ensure_masterdata

if profile_wants grace || profile_wants multi || profile_wants go-live; then
  dpi_set_go_live_and_refresh "15-04-2025" "7676"
fi

if profile_wants grace; then
  JOB_TIME="$GRACE_JOB_TIME" bash "$ROOT/scripts/dpic/run_grace_dpi_e2e.sh" || fail "grace_e2e"
fi

if profile_wants multi; then
  JOB_TIME="$MULTI_EMI_JOB_TIME" bash "$ROOT/scripts/dpic/run_multi_emi_installment_e2e.sh" || fail "multi_emi"
fi

if profile_wants go-live; then
  bash "$ROOT/scripts/dpic/run_dpi_go_live_ud_e2e.sh" || fail "go_live_ud"
fi

if profile_wants certify && [[ "${DPI_UD_CERTIFY:-1}" == "1" ]]; then
  echo "=== certify overdue scenarios (demo LAN $DEMO_LAN) ==="
  CERT_MODE=fixture SKIP_SETUP=1 \
    bash "$ROOT/scripts/dpic/certify_dpi_scenarios.sh" --scenarios single_overdue,multi_overdue \
    || fail "certify_overdue"

  _pre_emi_certified=0
  if [[ -f "$ROOT/scripts/dpic/certified_fixtures.json" ]]; then
    if python3 - <<'PY'
import json
from pathlib import Path
p = Path("scripts/dpic/certified_fixtures.json")
for s in json.loads(p.read_text()).get("scenarios", []):
    if s.get("id") == "pre_emi" and s.get("loan_account_id"):
        raise SystemExit(0)
raise SystemExit(1)
PY
    then
      _pre_emi_certified=1
    fi
  fi

  if [[ "$_pre_emi_certified" == "1" ]]; then
    CERT_MODE=fixture SKIP_SETUP=1 \
      bash "$ROOT/scripts/dpic/certify_dpi_scenarios.sh" --verify-only --scenarios pre_emi \
      || fail "certify_pre_emi_verify"
  else
    echo ">>> certify pre_emi (fresh LAN — one-time disburse)"
    CERT_MODE=fixture SKIP_SETUP=1 \
      bash "$ROOT/scripts/dpic/certify_dpi_scenarios.sh" --scenarios pre_emi \
      || fail "certify_pre_emi"
  fi
fi

echo "=== DPI UD compliance PASS (profile=$DPI_UD_PROFILE) ==="
