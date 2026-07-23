#!/usr/bin/env bash
# Capture generic test/flow knowledge for future ntest runs (self-learning).
#
# Usage:
#   test-learn.sh --api disburseLoan --kind gotcha --text "client_reference_number must be numeric"
#   test-learn.sh --api dpiAccrualBooking --kind correlator --key JOB_TIME --value "EOD epoch ms"
#   test-learn.sh --api fetchLoanForeclosureSimulationDetails --kind canned_sql --canned 11-accruals-by-lan --text "check DPI accruals before sim"
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export SLIPROD_WORKSPACE="$ROOT"
cd "$ROOT"
exec python3 - "$@" <<'PY'
import argparse, json, os, sys
from pathlib import Path

ROOT = Path(os.environ["SLIPROD_WORKSPACE"])
sys.path.insert(0, str(ROOT / "scripts/testing"))
from lib.test_learnings import append_learning, LEARNINGS

p = argparse.ArgumentParser()
p.add_argument("--api", default="*")
p.add_argument("--kind", required=True, choices=["correlator", "gotcha", "expect", "canned_sql", "error_code", "setup", "batch"])
p.add_argument("--text", required=True)
p.add_argument("--error-code")
p.add_argument("--key", dest="correlator")
p.add_argument("--value")
p.add_argument("--canned")
args = p.parse_args()
rec = append_learning(
    api=args.api,
    kind=args.kind,
    text=args.text,
    error_code=args.error_code or "",
    correlator=args.correlator or "",
    value=args.value or "",
    canned=args.canned or "",
)
print(f"[test-learn] → {LEARNINGS}")
print(json.dumps({"ok": True, **rec}, indent=2))
PY
