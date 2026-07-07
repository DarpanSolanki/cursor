#!/usr/bin/env bash
# SDCP-10199 parent last-child DFC — local test gate (3.4.2.1+).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "=== SDCP-10199 parent last-child DFC local test gate ==="
bash "$ROOT/scripts/bin/novopay-service.sh" ensure accounting ${COMPILE:+--compile}

echo "[1/3] Logic simulation (PRIN paid, INT-only waive)"
python3 "$ROOT/scripts/dcf_sanity/parent_last_child_dfc_simulation.py"

echo "[2/3] DCF principal split / writer-order simulation"
bash "$ROOT/scripts/dcf_sanity/run_dcf_principal_split_simulation.sh"

echo "[3/3] Accounting compile (writer on release train)"
cd "$ROOT/novopay-platform-accounting-v2"
./gradlew compileJava -x test -q

if [[ -n "${PARENT_LAN:-}" ]]; then
  echo "[optional] Post-approve DB assert for parent $PARENT_LAN"
  bash "$ROOT/scripts/dcf_sanity/run_parent_last_child_dfc_local.sh" "$PARENT_LAN"
fi

echo "=== SDCP-10199 parent last-child DFC local test gate PASS ==="
