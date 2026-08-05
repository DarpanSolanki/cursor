#!/usr/bin/env bash
# TDPQA-72 e2e: 3-member SHG group, foreclosed member by member.
#   members 1-2: same foreclosure date -> force-bill reference collision (134497 guard)
#   member 3:    last remaining member  -> parent closes instead of rescheduling (134203 guard)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/scripts/testing:${ROOT}/scripts/dcf_sanity:${PYTHONPATH:-}"
export DISBURSE_ENTRY="${DISBURSE_ENTRY:-http}"
export FIXTURE_STRICT="${FIXTURE_STRICT:-1}"
export ICF_USE_LOAN_PREPAYMENT=1
export ICF_OFFICE_ID="${ICF_OFFICE_ID:-2}"

echo "=== foreclosure.last_child_parent_closure ==="
bash "$ROOT/scripts/bin/assert-build-current.sh"

if [[ -z "${CHILD1_LAN:-}" ]]; then
  echo "--- building fresh aged 3-member SHG fixture (real disburse + EOD billing) ---"
  eval "$(DCF_FIXTURE_MEMBERS=3 python3 "$ROOT/scripts/dcf_sanity/create_fresh_dcf_group_fixture.py" \
    | grep -E '^(PARENT_LAN|CHILD1_LAN|CHILD2_LAN|CHILD3_LAN|DEATH_DATE)=')"
fi
: "${PARENT_LAN:?fixture did not yield PARENT_LAN}"
: "${CHILD3_LAN:?fixture did not yield CHILD3_LAN — this case needs 3 members}"
echo "  parent=$PARENT_LAN members=$CHILD1_LAN,$CHILD2_LAN,$CHILD3_LAN"

foreclose() {
  PARENT_LAN="$PARENT_LAN" CHILD_LAN="$1" DEATH_DATE="${DEATH_DATE:-2026-06-16}" python3 - <<'PY'
import os, sys
sys.path.insert(0, "scripts/dcf_sanity")
import group_parent_last_child_dfc_local_e2e as dcf
parent, child = os.environ["PARENT_LAN"], os.environ["CHILD_LAN"]
pid = int(dcf.psql(f"SELECT account_id FROM mfi_accounting.loan_account WHERE la_account_number='{parent}';"))
dcf.settle_parent_overdue_before_vikram_fc(parent, pid)
dcf.run_child_loan_prepayment_fc(child, os.environ["DEATH_DATE"])
PY
}

for lan in "$CHILD1_LAN" "$CHILD2_LAN"; do
  echo "--- non-last member $lan (same foreclosure date) ---"
  foreclose "$lan"
  python3 "$ROOT/scripts/testing/foreclosure/assert_child_fc_parent_rsch_gl.py" --child-lan "$lan"
  python3 "$ROOT/scripts/testing/foreclosure/assert_child_fc_parent_rsch_writes.py" --child-lan "$lan"
done

echo "--- last member $CHILD3_LAN (parent must close, not reschedule) ---"
foreclose "$CHILD3_LAN"
python3 "$ROOT/scripts/testing/foreclosure/assert_child_fc_parent_rsch_gl.py" --child-lan "$CHILD3_LAN"
python3 "$ROOT/scripts/testing/foreclosure/assert_last_child_parent_closure.py" --child-lan "$CHILD3_LAN"
