#!/usr/bin/env bash
# waiver.child_waive_loan_account_charges — parent waiveLoanAccountCharges APPROVE on a group
# parent, WAIVER queue fan-out through childLoanEventProcessingBatchJob, then a value-level
# assert that every child waiver audit row was actually applied to its loan_due_details row.
#
# Env:
#   PARENT_LAN=...  reuse an existing ACTIVE group parent instead of disbursing a fresh one
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/scripts/testing:${ROOT}/scripts/dcf_sanity:${PYTHONPATH:-}"
export DCF_STACK_SKIP_ACCOUNTING_RESTART="${DCF_STACK_SKIP_ACCOUNTING_RESTART:-1}"

echo "=== waiver.child_waive_loan_account_charges ==="
bash "$ROOT/scripts/bin/agent-ops.sh" before-test waiveLoanAccountCharges accounting
bash "$ROOT/scripts/bin/novopay-service.sh" ensure task

if [[ -z "${PARENT_LAN:-}" ]]; then
  echo "--- building fresh SHG group (real disburse + real accrual/posting/billing) ---"
  eval "$(DCF_FIXTURE_MEMBERS="${DCF_FIXTURE_MEMBERS:-2}" \
    python3 "$ROOT/scripts/dcf_sanity/create_fresh_dcf_group_fixture.py" \
    | grep -E '^(PARENT_LAN|CHILD1_LAN|CHILD2_LAN)=')"
fi
: "${PARENT_LAN:?fixture did not yield PARENT_LAN}"
echo "  parent=$PARENT_LAN"

python3 "$ROOT/scripts/testing/waiver/child_waiver_fanout_e2e.py" --parent-lan "$PARENT_LAN"
echo "=== PASS: waiver.child_waive_loan_account_charges (parent=$PARENT_LAN) ==="
