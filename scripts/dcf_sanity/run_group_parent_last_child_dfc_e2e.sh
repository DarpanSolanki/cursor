#!/usr/bin/env bash
# SDCP-10199 — SHG/JLG group parent last-child death foreclosure local e2e.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

export DCF_FRESH_GROUP="${DCF_FRESH_GROUP:-0}"
export PARENT_LAN="${PARENT_LAN:-}"
export CHILD1_LAN="${CHILD1_LAN:-}"
export CHILD2_LAN="${CHILD2_LAN:-}"
export DEATH_DATE="${DEATH_DATE:-}"
export SEED_EXTRA="${SEED_EXTRA:-1}"
export DCF_SEED_EMI_LABD="${DCF_SEED_EMI_LABD:-1}"
export ACCEPTANCE_STRICT="${ACCEPTANCE_STRICT:-1}"
export ACCEPTANCE_SCOPE="${ACCEPTANCE_SCOPE:-obs123}"

echo "=== SDCP-10199 group parent last-child DFC e2e (A2 EXTRA + force-bill labd) ==="
echo "acceptance_scope=$ACCEPTANCE_SCOPE acceptance_strict=$ACCEPTANCE_STRICT seed_extra=$SEED_EXTRA"
if [[ "${DCF_FRESH_GROUP}" == "1" ]]; then
  echo "mode=fresh_group (disburse new SHG parent+2 children per run)"
elif [[ -n "${PARENT_LAN}" ]]; then
  echo "parent=$PARENT_LAN child1=$CHILD1_LAN child2=$CHILD2_LAN death_date=$DEATH_DATE"
else
  echo "parent=<auto-discover ACTIVE product-70; blocklist=${DCF_FIXTURE_BLOCKLIST:-6003896527,6003973025}>"
fi

# ensure_dcf_local_stack runs inside Python after snapshot restore (avoids YB conflict on restore).
if [[ "${DCF_FRESH_GROUP}" == "1" ]]; then
  unset PARENT_LAN CHILD1_LAN CHILD2_LAN DEATH_DATE
  export DCF_E2E_NO_SNAPSHOT=1
elif [[ -z "${PARENT_LAN}" ]]; then
  unset PARENT_LAN CHILD1_LAN CHILD2_LAN DEATH_DATE
fi

python3 "$ROOT/scripts/dcf_sanity/group_parent_last_child_dfc_local_e2e.py"
rc=$?
if [[ $rc -ne 0 ]]; then
  exit $rc
fi
echo "=== PASS: dcf.group_parent_last_child_e2e ==="
