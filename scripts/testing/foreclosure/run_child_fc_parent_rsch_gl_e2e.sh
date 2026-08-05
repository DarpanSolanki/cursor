#!/usr/bin/env bash
# TDPQA-72 e2e: fresh aged SHG group -> real child foreclosure via loanPrepayment -> parent RSCH GL.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/scripts/testing:${ROOT}/scripts/dcf_sanity:${PYTHONPATH:-}"
export DISBURSE_ENTRY="${DISBURSE_ENTRY:-http}"
export FIXTURE_STRICT="${FIXTURE_STRICT:-1}"
export ICF_USE_LOAN_PREPAYMENT=1
export ICF_OFFICE_ID="${ICF_OFFICE_ID:-2}"

echo "=== foreclosure.child_fc_parent_rsch_gl ==="

if [[ -z "${CHILD1_LAN:-}" ]]; then
  echo "--- building fresh aged SHG fixture (real disburse + EOD billing) ---"
  eval "$(python3 "$ROOT/scripts/dcf_sanity/create_fresh_dcf_group_fixture.py" | grep -E '^(PARENT_LAN|CHILD1_LAN|CHILD2_LAN|DEATH_DATE)=')"
fi
: "${PARENT_LAN:?fixture did not yield PARENT_LAN}"
: "${CHILD1_LAN:?fixture did not yield CHILD1_LAN}"
echo "  parent=$PARENT_LAN child1=$CHILD1_LAN"

echo "--- settle parent overdue + foreclose child via loanPrepayment (prod path) ---"
PARENT_LAN="$PARENT_LAN" CHILD1_LAN="$CHILD1_LAN" python3 - <<'PY'
import os, sys
sys.path.insert(0, "scripts/dcf_sanity")
import group_parent_last_child_dfc_local_e2e as dcf
parent, child = os.environ["PARENT_LAN"], os.environ["CHILD1_LAN"]
pid = int(dcf.psql(f"SELECT account_id FROM mfi_accounting.loan_account WHERE la_account_number='{parent}';"))
dcf.settle_parent_overdue_before_vikram_fc(parent, pid)
dcf.run_child_loan_prepayment_fc(child, os.environ.get("DEATH_DATE", "2026-06-16"))
PY

echo "--- assert parent RSCH GL mirrors child foreclosure GL ---"
python3 "$ROOT/scripts/testing/foreclosure/assert_child_fc_parent_rsch_gl.py" --child-lan "$CHILD1_LAN"

echo "--- assert non-GL writes (status, dues, installments, payments, closure, part-prepayment) ---"
python3 "$ROOT/scripts/testing/foreclosure/assert_child_fc_parent_rsch_writes.py" --child-lan "$CHILD1_LAN"
