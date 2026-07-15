#!/usr/bin/env bash
# SDCP-10199 — SHG/JLG group parent last-child death foreclosure local e2e.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

export PARENT_LAN="${PARENT_LAN:-}"
export CHILD1_LAN="${CHILD1_LAN:-}"
export CHILD2_LAN="${CHILD2_LAN:-}"
export DEATH_DATE="${DEATH_DATE:-}"

echo "=== SDCP-10199 group parent last-child DFC e2e (A2 EXTRA + force-bill labd) ==="
if [[ -n "${PARENT_LAN}" ]]; then
  echo "parent=$PARENT_LAN child1=$CHILD1_LAN child2=$CHILD2_LAN death_date=$DEATH_DATE"
else
  echo "parent=<auto-discover fresh ACTIVE product-70 fixture>"
fi

bash "$ROOT/scripts/dcf_sanity/ensure_dcf_local_stack.sh"

# Empty env vars so Python discover_fresh_fixture() runs unless parent explicitly set
if [[ -z "${PARENT_LAN}" ]]; then
  unset PARENT_LAN CHILD1_LAN CHILD2_LAN DEATH_DATE
fi

python3 "$ROOT/scripts/dcf_sanity/group_parent_last_child_dfc_local_e2e.py"
echo "=== PASS: dcf.group_parent_last_child_e2e ==="
