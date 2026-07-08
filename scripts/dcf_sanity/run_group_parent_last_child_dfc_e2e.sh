#!/usr/bin/env bash
# SDCP-10199 — SHG/JLG group parent last-child death foreclosure local e2e.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

export PARENT_LAN="${PARENT_LAN:-6000137433}"
export CHILD1_LAN="${CHILD1_LAN:-6000137440}"
export CHILD2_LAN="${CHILD2_LAN:-6000137441}"
export DEATH_DATE="${DEATH_DATE:-2025-11-02}"

echo "=== SDCP-10199 group parent last-child DFC e2e ==="
echo "parent=$PARENT_LAN child1=$CHILD1_LAN child2=$CHILD2_LAN death_date=$DEATH_DATE"

bash "$ROOT/scripts/dcf_sanity/ensure_dcf_local_stack.sh"

python3 "$ROOT/scripts/dcf_sanity/group_parent_last_child_dfc_local_e2e.py"
echo "=== PASS: dcf.group_parent_last_child_e2e ==="
