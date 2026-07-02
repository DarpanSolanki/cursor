#!/usr/bin/env bash
# individualChildLoanForeclosure APPROVE write — SQL assert on posted DPI GL legs.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"

export ICF_LAN="${ICF_LAN:-$ACCOUNT_NUMBER}"
export ICF_FORECLOSURE_DATE="${ICF_FORECLOSURE_DATE:-$FORECLOSURE_DATE}"
export LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-8060160}"
export ACCOUNT_NUMBER="${ACCOUNT_NUMBER:-6004044425}"
export PGPASSWORD="${PGPASSWORD:-yugabyte}"

fail() { echo "FAIL: $*" >&2; exit 1; }

echo "=== DPI individualChildLoanForeclosure write (LAN=$ICF_LAN) ==="
dpi_ensure_accounting
dpi_ensure_actor
dpi_export_correlators
dpi_restore_api_state

# Ensure billed DPI exists before foreclosure posts DPI legs
DPI_OPEN="$(dpi_pg -t -A -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/compute_part_prep_trial_amounts.sql" | head -1 | cut -d'|' -f2 | tr -d '[:space:]')"
python3 - "$DPI_OPEN" <<'PY'
import sys
if float(sys.argv[1] or 0) <= 0:
    raise SystemExit("FAIL: no open billed DPI on fixture before ICF write")
print(f"OK: dpi_overdue_open={sys.argv[1]}")
PY

export ICF_STAN="icf_write_$(date +%s)"
export ICF_EXPECT_CODE="${ICF_EXPECT_CODE:-30267}"

bash "$ROOT/scripts/testing/foreclosure/individual-child-foreclosure-e2e.sh" || fail "individualChildLoanForeclosure E2E"

read -r LEG_COUNT MAX_AMT <<<"$(dpi_pg -v ON_ERROR_STOP=1 -t -A \
  -v lan="$ICF_LAN" -v stan="" \
  -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_foreclosure_posting.sql" | head -1 | tr '|' ' ')"

[[ "${LEG_COUNT:-0}" != "0" ]] || fail "no DPI GL legs on latest LOAN_PREPAYMENT txn (BILLED_DPI / ADV_BILLED_DPI / WAIVED)"
echo "OK: foreclosure DPI GL legs count=$LEG_COUNT max_amount=$MAX_AMT"

if [[ "${RESTORE_AFTER:-1}" == "1" ]]; then
  echo ">>> restore parent DPI API state after ICF write"
  LOAN_ACCOUNT_ID="$LOAN_ACCOUNT_ID" JOB_TIME="${JOB_TIME:-1782563400000}" dpi_restore_api_state
fi

echo "=== DPI individualChildLoanForeclosure write PASS ==="
