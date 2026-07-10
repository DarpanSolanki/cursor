#!/usr/bin/env bash
# Fast local disburseLoan — JLG minimal stage suite (flat payload, member_details null).
# Use for smoke after accounting changes; full matrix: scripts/run_disbursement_full_matrix.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PAYLOADS="$ROOT/scripts/disbursement/payloads/canonical"
REQUEST_FILE="${REQUEST_FILE:-$PAYLOADS/disburse_loan_sanity_request_4495972134234554346565.json}"
STAGE_SUITE="${STAGE_SUITE:-minimal}"
REPORT_JSON="${REPORT_JSON:-}"

echo "=== disburse-quick — ensure accounting ==="
bash "$ROOT/scripts/bin/agent-ops.sh" before-test disburseLoan

echo "=== disburse-quick — preflight ==="
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

ARGS=(
  --request-file "$REQUEST_FILE"
  --stage-suite "$STAGE_SUITE"
  --simulator-profile success
  --reset-before
  --reset-target-disb-status LAN_CREATED
  --http-timeout-s 30
  --wait-timeout-s 120
  --poll-s 2.0
)
[[ -n "$REPORT_JSON" ]] && ARGS+=(--report-json "$REPORT_JSON")

echo "=== disburse-quick — disburseLoan ($STAGE_SUITE) ==="
echo "Payload: $REQUEST_FILE"
exec python3 "$ROOT/scripts/disburse_loan_sanity.py" "${ARGS[@]}" "$@"
