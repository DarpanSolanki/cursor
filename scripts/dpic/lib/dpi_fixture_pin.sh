#!/usr/bin/env bash
# Pin fixture LAN for regression scripts — do not inherit last_certified_fresh_lan.env.
# Usage: source .../dpi_fixture_pin.sh && dpi_use_fixture_loan
set -euo pipefail

_DPI_PIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_DPI_PIN_DIR/dpi_fixture_constants.sh"

# Drop env vars that leak from fresh-disburse / last_certified_fresh_lan.env into fixture tests.
dpi_clear_fresh_env_leak() {
  unset END_DATE EXT_REF CERTIFIED_AT 2>/dev/null || true
}

dpi_use_fixture_loan() {
  dpi_clear_fresh_env_leak
  export LOAN_ACCOUNT_ID="$DPI_FIXTURE_LOAN_ID"
  export ACCOUNT_NUMBER="$DPI_FIXTURE_LAN"
  export DEMO_LAN="$DPI_FIXTURE_LAN"
}

dpi_is_fixture_loan() {
  [[ "${LOAN_ACCOUNT_ID:-}" == "$DPI_FIXTURE_LOAN_ID" ]]
}

# true when loan is not the demo fixture (fresh disburse / certify LAN).
dpi_is_fresh_loan() {
  [[ -n "${LOAN_ACCOUNT_ID:-}" ]] && ! dpi_is_fixture_loan
}

dpi_use_grace_chain_loan() {
  dpi_clear_fresh_env_leak
  export LOAN_ACCOUNT_ID="$DPI_GRACE_CHAIN_LOAN_ID"
  export ACCOUNT_NUMBER="$DPI_GRACE_CHAIN_LAN"
  export DEMO_LAN="$DPI_GRACE_CHAIN_LAN"
}
