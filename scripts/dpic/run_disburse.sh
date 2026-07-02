#!/usr/bin/env bash
# LMS-only disburseLoan for DPIC MFT product 6367 (no LOS/Kafka).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REQUEST_FILE="${REQUEST_FILE:-$ROOT/scripts/dpic/payload/disburse_mft_6367.json}"
REPORT_JSON="${REPORT_JSON:-/tmp/dpic_disburse_report.json}"

echo "=== DPIC disburse (disburse_loan_sanity.py) ==="
echo "Payload: $REQUEST_FILE"

rm -f /tmp/disburse_loan_sanity.lock
python3 "$ROOT/scripts/disburse_loan_sanity.py" \
  --request-file "$REQUEST_FILE" \
  --stage-suite default_clean \
  --simulator-profile none \
  --bank-outcome-source script \
  --http-timeout-s 60 \
  --wait-timeout-s 180 \
  --poll-s 2.0 \
  --report-json "$REPORT_JSON"

echo "Report: $REPORT_JSON"
