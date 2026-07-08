#!/usr/bin/env bash
# Fast disburse for QA presentation — single DEFAULT call, short DB poll, no replay suite.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REQUEST_FILE="${REQUEST_FILE:?REQUEST_FILE required}"
REPORT_JSON="${REPORT_JSON:-/tmp/dpic_disburse_demo_report.json}"

# Demo: fail in ~20s if loan never appears (async validation errors e.g. 134233).
WAIT_TIMEOUT_S="${DISBURSE_WAIT_TIMEOUT_S:-45}"
POLL_S="${DISBURSE_POLL_S:-1.0}"
NO_LOAN_FAILFAST_S="${DISBURSE_NO_LOAN_FAILFAST_S:-20}"

echo "=== DPIC demo disburse (fast) ==="
echo "Payload: $REQUEST_FILE"
echo "poll: wait=${WAIT_TIMEOUT_S}s failfast=${NO_LOAN_FAILFAST_S}s interval=${POLL_S}s"
echo ""

rm -f /tmp/disburse_loan_sanity.lock
python3 "$ROOT/scripts/disburse_loan_sanity.py" \
  --request-file "$REQUEST_FILE" \
  --stage-suite minimal \
  --simulator-profile success \
  --reset-before \
  --reset-target-disb-status LAN_CREATED \
  --http-timeout-s 30 \
  --wait-timeout-s "$WAIT_TIMEOUT_S" \
  --poll-s "$POLL_S" \
  --report-json "$REPORT_JSON" \
  --fail-fast

echo "Report: $REPORT_JSON"
