#!/usr/bin/env bash
# Fast local SHG disburseLoan — minimal stage suite (parent + member_details[] / CLMT path).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PAYLOADS="$ROOT/scripts/disbursement/payloads/canonical"
REQUEST_FILE="${REQUEST_FILE:-$PAYLOADS/disburse_loan_sanity_request_shg_41333333.json}"
STAGE_SUITE="${STAGE_SUITE:-minimal}"

echo "=== disburse-shg-quick — ensure accounting ==="
bash "$ROOT/scripts/bin/agent-ops.sh" before-test disburseLoan

echo "=== disburse-shg-quick — preflight ==="
PYTHONPATH="$ROOT/scripts/disbursement" python3 - <<'PY'
from disbursement_suite.preflight import run
r = run(
    accounting_base_url="http://localhost:8002",
    accounting_context_path="/accounting",
    simulator_host="localhost",
    simulator_port=8018,
)
for d in r.details or []:
    mark = "OK" if d.get("ok") else "WARN"
    print(f"  [{mark}] {d.get('check')}: {d.get('actual')}")
if not r.ok:
    raise SystemExit(f"preflight blocked: {r.blocker}")
PY

rm -f /tmp/disburse_loan_sanity.lock

echo "=== disburse-shg-quick — disburseLoan SHG ($STAGE_SUITE) ==="
echo "Payload: $REQUEST_FILE"
exec python3 "$ROOT/scripts/disburse_loan_sanity.py" \
  --request-file "$REQUEST_FILE" \
  --stage-suite "$STAGE_SUITE" \
  --simulator-profile success \
  --reset-before \
  --reset-target-disb-status LAN_CREATED \
  --http-timeout-s 30 \
  --wait-timeout-s 180 \
  --poll-s 2.0 \
  "$@"
