#!/usr/bin/env bash
# Accounting flow proof — routes by detected domain (ALL flows, not money-only).
# Usage: accounting-flow-proof.sh [--domain disbursement|dpi|interest_accrual|...]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DOMAIN="${1:-}"
if [[ "$DOMAIN" == "--domain" ]]; then
  DOMAIN="${2:-}"
fi

run_json_proof() {
  python3 - <<'PY' "$ROOT" "$DOMAIN"
import json, subprocess, sys
from pathlib import Path
root = Path(sys.argv[1])
dom = sys.argv[2]
sys.path.insert(0, str(root / "scripts/lib"))
from accounting_flow_domains import load_domains
domains = load_domains()
if dom:
    todo = [dom] if dom in domains else []
else:
    todo = list(domains)
for did in todo:
    proof = (domains.get(did) or {}).get("proof")
    if proof:
        print(f">>> proof {did}: {proof}")
        subprocess.run(proof, shell=True, cwd=str(root), check=True)
PY
}

echo "=== accounting-flow-proof ==="
bash "$ROOT/scripts/bin/accounting-flow-coverage.sh" | head -25

if [[ -n "$DOMAIN" ]]; then
  run_json_proof
  exit 0
fi

# Default chain: health + read smoke + domain proofs that exist
bash "$ROOT/scripts/bin/ntest.sh" run health.accounting
bash "$ROOT/scripts/bin/ntest.sh" run accounting.read_smoke || true
run_json_proof
echo "=== accounting-flow-proof PASS ==="
