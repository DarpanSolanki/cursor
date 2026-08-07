#!/usr/bin/env bash
# foreclosure.child_loan_foreclosure — parent group loanPrepayment APPROVE, FCL queue fan-out
# through childLoanEventProcessingBatchJob -> childLoanForeclosure -> individualChildLoanForeclosure,
# then a value-level assert on the per-component split written to child prepayment_details.
#
# Env:
#   PARENT_LAN=...              reuse an existing ACTIVE group parent instead of disbursing
#   WAIVE_BILLED_INTEREST=200   parent waiver amount fanned out to children (0 disables)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/scripts/testing:${ROOT}/scripts/dcf_sanity:${PYTHONPATH:-}"
export DCF_STACK_SKIP_ACCOUNTING_RESTART="${DCF_STACK_SKIP_ACCOUNTING_RESTART:-1}"

echo "=== foreclosure.child_loan_foreclosure ==="
bash "$ROOT/scripts/bin/agent-ops.sh" before-test loanPrepayment accounting
bash "$ROOT/scripts/bin/novopay-service.sh" ensure task
bash "$ROOT/scripts/bin/foreclosure-local-setup.sh" 2>&1 | tail -4 || true

if [[ -z "${PARENT_LAN:-}" ]]; then
  echo "--- building fresh SHG group (real disburse + real accrual/posting/billing) ---"
  eval "$(DCF_FIXTURE_MEMBERS="${DCF_FIXTURE_MEMBERS:-2}" \
    python3 "$ROOT/scripts/dcf_sanity/create_fresh_dcf_group_fixture.py" \
    | grep -E '^(PARENT_LAN|CHILD1_LAN|CHILD2_LAN)=')"
fi
: "${PARENT_LAN:?fixture did not yield PARENT_LAN}"
echo "  parent=$PARENT_LAN"

python3 "$ROOT/scripts/testing/foreclosure/child_fc_component_split_e2e.py" \
  --parent-lan "$PARENT_LAN" \
  --waive-billed-interest "${WAIVE_BILLED_INTEREST:-200}"
echo "=== PASS: foreclosure.child_loan_foreclosure (parent=$PARENT_LAN) ==="
