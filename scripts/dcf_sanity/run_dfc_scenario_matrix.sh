#!/usr/bin/env bash
# DCF full scenario matrix — drive real flows, then full schema audit.
# Does NOT patch product code. Failures are real evidence (or fixture/env blocks).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
OUT="$ROOT/scripts/scratch/dfc-full-matrix"
mkdir -p "$OUT"
NTEST="$ROOT/scripts/bin/ntest.sh"
AUDIT="python3 $ROOT/scripts/dcf_sanity/dcf_full_schema_audit.py"
SUMMARY="$OUT/matrix_summary.txt"
: >"$SUMMARY"

run_case() {
  local name="$1"
  shift
  echo "" | tee -a "$SUMMARY"
  echo "======== MATRIX CASE: $name ========" | tee -a "$SUMMARY"
  echo "cmd: $*" | tee -a "$SUMMARY"
  local log="$OUT/case_${name}.log"
  set +e
  "$@" >"$log" 2>&1
  local rc=$?
  set -e
  # Extract LANs from log if present
  local parent child1 child2
  parent=$(rg -o 'parent[= ][0-9]+|parent [0-9]{10}' "$log" | rg -o '[0-9]{10}' | tail -1 || true)
  # Fresh group prints account_number=
  if [[ -z "${parent:-}" ]]; then
    parent=$(rg -o 'lan=600[0-9]+' "$log" | head -1 | cut -d= -f2 || true)
  fi
  if [[ -z "${parent:-}" ]]; then
    parent=$(rg -o '600[0-9]{7}' "$log" | head -1 || true)
  fi
  # Prefer explicit parent-after / PASS lines
  parent=$(rg -n 'parent-after-child2|parent POS sync PASS: parent=' "$log" | rg -o '600[0-9]{7}' | tail -1 || echo "${parent:-}")
  child1=$(rg -n 'Vikram FC PASS: LOAN_PREPAYMENT child=|child [0-9]+ CLOSED|Issue B PASS: labd_id' "$log" | rg -o '600[0-9]{7}' | head -1 || true)
  # children from diag
  local kids
  kids=$(rg -o "lan': '600[0-9]+" "$log" | rg -o '600[0-9]{7}' | sort -u | tr '\n' ',' | sed 's/,$//')
  if [[ -n "${parent:-}" && -n "${kids:-}" ]]; then
    echo "schema audit parent=$parent children=$kids" | tee -a "$SUMMARY"
    set +e
    PARENT_LAN="$parent" CHILD_LANS="$kids" ACCEPTANCE_SCOPE=obs123 $AUDIT >>"$log" 2>&1
    local arc=$?
    set -e
    echo "flow_rc=$rc schema_rc=$arc" | tee -a "$SUMMARY"
    rg -n "PASS:|FAIL:|full money column|shape=|schema column audit" "$log" | tail -40 | tee -a "$SUMMARY" || true
    if [[ $rc -ne 0 || $arc -ne 0 ]]; then
      echo "RESULT $name: FAIL flow=$rc schema=$arc (see $log)" | tee -a "$SUMMARY"
      return 1
    fi
    echo "RESULT $name: PASS" | tee -a "$SUMMARY"
    return 0
  fi
  echo "RESULT $name: flow_rc=$rc (LAN extract incomplete — see $log)" | tee -a "$SUMMARY"
  return "$rc"
}

echo "DCF matrix start $(date -Is)" | tee -a "$SUMMARY"

# S-A: Vikram FC → RSTCRE → last DFC (QA4-shaped)
run_case S_A_vikram_fc "$NTEST" run dcf.vikram_fc_rstcre_dfc_e2e || true

# S-B: Fresh dual-DFC (non-last DFC then last DFC) — no Vikram FC
run_case S_B_dual_dfc \
  env DCF_FRESH_GROUP=1 VIKRAM_PATH=0 SEED_EXTRA=0 DCF_SEED_EMI_LABD=0 ACCEPTANCE_STRICT=1 ACCEPTANCE_SCOPE=obs123 DCF_E2E_NO_SNAPSHOT=1 \
  bash scripts/dcf_sanity/run_group_parent_last_child_dfc_e2e.sh || true

# S-C: Adversarial EXTRA + EMI labd (dirty)
run_case S_C_adversarial_extra \
  env DCF_FRESH_GROUP=1 VIKRAM_PATH=0 SEED_EXTRA=1 DCF_SEED_EMI_LABD=1 ACCEPTANCE_STRICT=1 ACCEPTANCE_SCOPE=obs123 DCF_E2E_NO_SNAPSHOT=1 \
  bash scripts/dcf_sanity/run_group_parent_last_child_dfc_e2e.sh || true

echo "" | tee -a "$SUMMARY"
echo "DCF matrix end $(date -Is)" | tee -a "$SUMMARY"
echo "Summary: $SUMMARY"
