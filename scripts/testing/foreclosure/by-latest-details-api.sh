#!/usr/bin/env bash
# TDPQA-207 — real getLoanForeclosureDetails BY_LATEST must NOT prefer REJECTED/REJECT
# when a non-rejected row exists but REJECTED has a higher business created_on.
#
# Seeds local fixture on LAN (default 0000000680), calls accounting API, asserts
# loan_foreclosure_details.task_status is not REJECTED/REJECT.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

# Prefer a LAN with payment_mode populated (masterdata lookup). 0680 often has blank mode → 333.
LAN="${ACCOUNT_NUMBER:-0000001440}"
API_URL="${ACCOUNTING_URL:-http://localhost:8002/accounting/api/v1/getLoanForeclosureDetails}"

echo "=== foreclosure.by_latest_details_api LAN=$LAN ==="

# Ensure accounting is on the branch under test and answering
bash scripts/bin/agent-ops.sh before-test getLoanForeclosureDetails accounting >/dev/null 2>&1 || true

# Fixture: REJECT/REJECTED rows get a future business created_on so MAX(created_on)
# would wrongly win without the TDPQA-207 ORDER BY CASE fix.
# Also ensure a non-rejected row exists with valid payment_mode for masterdata.
bash scripts/bin/db-local-write.sh --sql "
UPDATE mfi_accounting.prepayment_details pd
SET created_on = TIMESTAMP '2030-06-01 12:00:00',
    updated_on = NOW()
FROM mfi_accounting.account a
WHERE a.id = pd.loan_account_id
  AND a.account_number = '${LAN}'
  AND pd.is_deleted = false
  AND pd.task_status IN ('REJECTED','REJECT');

UPDATE mfi_accounting.prepayment_details pd
SET payment_mode = COALESCE(NULLIF(TRIM(pd.payment_mode), ''), 'CASH')
FROM mfi_accounting.account a
WHERE a.id = pd.loan_account_id
  AND a.account_number = '${LAN}'
  AND pd.is_deleted = false
  AND COALESCE(pd.task_status, '') NOT IN ('REJECTED','REJECT');
" >/dev/null

echo "fixture: REJECT*/REJECT rows for $LAN set created_on=2030-06-01; non-rejected payment_mode ensured"

# SQL proof — same ORDER BY as PrepaymentDetailsRepository (fail closed on QA mode)
PICKED=$(bash scripts/db-local.sh --sql "
SELECT pd.task_status
FROM mfi_accounting.prepayment_details pd
JOIN mfi_accounting.account a ON a.id = pd.loan_account_id
WHERE a.account_number = '${LAN}' AND pd.is_deleted = false
ORDER BY CASE WHEN pd.task_status IN ('REJECTED','REJECT') THEN 1 ELSE 0 END,
         pd.created_on DESC, pd.id DESC
LIMIT 1;
" | awk 'NR==3 {print $1}')
echo "SQL latest task_status=${PICKED:-<null/blank>}"
case "${PICKED^^}" in
  REJECTED|REJECT)
    echo "FAIL: SQL ORDER BY still picks REJECTED/REJECT"
    exit 1
    ;;
esac
echo "SQL pick OK (non-REJECTED preferred)"

STAN="tdpqa207_$(date +%s%3N)"
RESP=$(curl -sS -m 60 -X POST "$API_URL" \
  -H 'Content-Type: application/json' \
  -d "{\"headers\":{\"tenant_code\":\"mfi\",\"user_id\":\"3\",\"client_code\":\"NOVOPAY\",\"channel_code\":\"WEB\",\"function_code\":\"DEFAULT\",\"function_sub_code\":\"BY_LATEST\",\"run_mode\":\"REAL\",\"stan\":\"${STAN}\",\"transmission_datetime\":\"${STAN}\"},\"request\":{\"account_number_list\":[\"${LAN}\"]}}")

python3 - "$RESP" <<'PY'
import json, sys
raw = sys.argv[1] if len(sys.argv) > 1 else ""
try:
    obj = json.loads(raw)
except Exception as e:
    print(f"FAIL: invalid JSON ({e}): {raw[:400]!r}")
    sys.exit(1)
rs = obj.get("response_status") or {}
print(f"response_status: {rs.get('code')}/{rs.get('status')}")
if str(rs.get("status") or "").upper() != "SUCCESS":
    print("FAIL: expected SUCCESS")
    print(raw[:800])
    sys.exit(1)
lst = obj.get("loan_foreclosure_details_list") or []
if not lst:
    print("FAIL: empty loan_foreclosure_details_list")
    sys.exit(1)
det = (lst[0] or {}).get("loan_foreclosure_details") or {}
status = str(det.get("task_status") or "").upper()
print(f"BY_LATEST task_status={status!r} closure_type={det.get('closure_type')!r} created_on={det.get('created_on')!r}")
if status in ("REJECTED", "REJECT"):
    print("FAIL: BY_LATEST returned REJECTED/REJECT — TDPQA-207 regression (created_on business-date ordering)")
    sys.exit(1)
print("PASS: BY_LATEST did not return REJECTED/REJECT")
PY
