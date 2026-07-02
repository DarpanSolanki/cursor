#!/usr/bin/env bash
# Fast preflight before dpic.extended_regression — fail fast on DB/catalogue/fixture blockers.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_gl_verify.sh"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/preflight.sh"

export LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-8060160}"
export ACCOUNT_NUMBER="${ACCOUNT_NUMBER:-6004044425}"
fail() { echo "FAIL: $*" >&2; exit 1; }

echo "=== DPI regression preflight ==="

if ! python3 "$ROOT/scripts/testing/lib/validate_registry.py" >/dev/null 2>&1; then
  fail "registry.json invalid — run: python3 scripts/testing/lib/validate_registry.py"
fi
echo "OK: registry.json"

if ! bash "$ROOT/scripts/bin/kg-ensure-fresh.sh" --check-only --quiet 2>/dev/null; then
  echo "WARN: KG stale — run scripts/bin/kg-session-sync.sh (continuing regression)"
fi

dpic_run_preflight || fail "DPIC preflight blockers"

dpi_ensure_dpi_write_catalogues

read -r loan_st acct_st dpi_open cat_link <<<"$(dpi_fixture_health_line "$LOAN_ACCOUNT_ID")"
if [[ "$loan_st" != "ACTIVE" || "$acct_st" != "ACTIVE" ]]; then
  echo ">>> fixture not ACTIVE — will restore in phase 1"
fi
if [[ "${cat_link:-0}" -lt 2 ]]; then
  fail "product 6367 missing catalogue 10/11 link (seed failed)"
fi
echo "OK: fixture loan=$LOAN_ACCOUNT_ID ($loan_st/$acct_st) cat10+11=$cat_link"

echo "=== DPI regression preflight PASS ==="
