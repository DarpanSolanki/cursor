#!/usr/bin/env bash
# Phase 3 — Foreclosure simulation API (frontend DPI fields).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"
demo_load_state
demo_resolve_loan

export ACCOUNT_NUMBER="$LAN"
export FORECLOSURE_DATE="$DEMO_FORECLOSURE_MS"

demo_banner "PHASE 3 — Foreclosure simulation ($DEMO_ANCHOR_DATE)"
demo_talking_points \
  "fetchLoanForeclosureSimulationDetails — billed_dpi + bpd_amount (DPI till foreclosure date)." \
  "Shows how foreclosure total includes DPI component."

"$NTEST" run dpic.foreclosure_sim
echo "=== Phase 3: PASS ==="
demo_pause
