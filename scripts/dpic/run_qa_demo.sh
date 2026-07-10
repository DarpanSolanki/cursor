#!/usr/bin/env bash
# Monday QA demo: fresh LAN (new ext_ref) → disburse → EOD batches → DPI API verify.
#
# Usage:
#   bash scripts/dpic/run_qa_demo.sh
#   SKIP_SETUP=1 bash scripts/dpic/run_qa_demo.sh          # DB already seeded
#   SKIP_DISBURSE=1 EXT_REF=DPIC_QA_... bash ...         # re-run EOD + verify only
#
# Writes: scripts/scratch/dpic_demo_state.env (ACCOUNT_NUMBER, LOAN_ACCOUNT_ID, EXT_REF, …)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
JOB_TIME="${JOB_TIME:-1781267400000}"
SKIP_SETUP="${SKIP_SETUP:-0}"
SKIP_DISBURSE="${SKIP_DISBURSE:-0}"
SEED_CALC_WINDOW="${SEED_CALC_WINDOW:-0}"
STATE_FILE="${STATE_FILE:-$ROOT/scripts/scratch/dpic_demo_state.env}"
TS="$(date +%s%3N)"
EXT_REF="${EXT_REF:-DPIC_QA_6367_10002233_${TS}}"
REQUEST_SCRATCH="$ROOT/scripts/scratch/dpic_qa_disburse_${TS}.json"

echo "=== DPIC QA demo (Monday) ==="
echo "ext_ref:    $EXT_REF"
echo "EOD date:   $JOB_TIME ($(date -d "@$((JOB_TIME / 1000))" '+%d-%b-%Y %H:%M %Z' 2>/dev/null || echo ms epoch))"
echo "state file: $STATE_FILE"
echo ""

if [[ "$SKIP_SETUP" != "1" ]]; then
  bash "$ROOT/scripts/dpic/run_setup.sh"
else
  echo ">>> SKIP_SETUP=1"
fi

if [[ "$SKIP_DISBURSE" != "1" ]]; then
  python3 - "$ROOT/scripts/dpic/payload/disburse_mft_6367.json" "$REQUEST_SCRATCH" "$EXT_REF" <<'PY'
import json, sys, time
from pathlib import Path

src, out, ext_ref = sys.argv[1:4]
crn = str(int(time.time() * 1000))
data = json.loads(Path(src).read_text(encoding="utf-8"))
data["request"]["disbursement_details"]["external_ref_number"] = ext_ref
data["request"]["disbursement_details"]["client_reference_number"] = crn
data["headers"]["stan"] = crn
data["headers"]["transmission_datetime"] = crn
Path(out).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print(f"Payload: {out}  client_reference_number={crn}")
PY
  REQUEST_FILE="$REQUEST_SCRATCH" bash "$ROOT/scripts/dpic/run_disburse.sh"
else
  echo ">>> SKIP_DISBURSE=1 — using existing loan for ext_ref prefix $EXT_REF"
fi

echo ""
echo ">>> Resolve disbursed loan ..."
read -r LOAN_ACCOUNT_ID LAN LOAN_STATUS DISB_STATUS PAST_DUE <<<"$(
  PGPASSWORD="${PGPASSWORD:-yugabyte}" psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" \
    -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}" -t -A -F' ' -v ON_ERROR_STOP=1 <<SQL
SELECT la.account_id, a.account_number, la.loan_status, la.disbursement_status, la.past_due_days
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.account a ON a.id = la.account_id
WHERE la.external_ref_number LIKE '${EXT_REF}%'
  AND la.is_deleted = false
ORDER BY la.account_id DESC
LIMIT 1;
SQL
)"

if [[ -z "${LOAN_ACCOUNT_ID:-}" || -z "${LAN:-}" ]]; then
  echo "FAIL: no loan for ext_ref prefix $EXT_REF" >&2
  exit 1
fi

echo "Loan: account_id=$LOAN_ACCOUNT_ID LAN=$LAN status=$LOAN_STATUS past_due_days=$PAST_DUE"

LOAN_ACCOUNT_ID="$LOAN_ACCOUNT_ID" JOB_TIME="$JOB_TIME" SEED_CALC_WINDOW="$SEED_CALC_WINDOW" \
  bash "$ROOT/scripts/dpic/run_eod.sh"

mkdir -p "$(dirname "$STATE_FILE")"
cat >"$STATE_FILE" <<EOF
# DPIC QA demo — generated $(date -Iseconds)
EXT_REF=$EXT_REF
ACCOUNT_NUMBER=$LAN
LOAN_ACCOUNT_ID=$LOAN_ACCOUNT_ID
CUSTOMER_ID=10002233
JOB_TIME=$JOB_TIME
FORECLOSURE_DATE=$JOB_TIME
EOF
echo ""
echo ">>> Wrote $STATE_FILE"

bash "$ROOT/scripts/dpic/run_demo_api_verify.sh"

echo ""
echo ">>> QA demo complete. Share with QA:"
echo "  LAN: $LAN"
echo "  ext_ref: ${EXT_REF}*"
echo "  Re-verify APIs only: bash scripts/dpic/run_demo_api_verify.sh"
