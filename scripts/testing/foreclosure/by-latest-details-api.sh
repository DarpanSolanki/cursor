#!/usr/bin/env bash
# TDPQA-207 — getLoanForeclosureDetails BY_LATEST
# 1) Prefer live non-REJECTED over live REJECTED with future created_on
# 2) Sole soft-deleted REJECTED (first-time reject) must still be returned
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

LAN="${ACCOUNT_NUMBER:-0000001440}"
API_URL="${ACCOUNTING_URL:-http://localhost:8002/accounting/api/v1/getLoanForeclosureDetails}"

echo "=== foreclosure.by_latest_details_api LAN=$LAN ==="

bash scripts/bin/agent-ops.sh before-test getLoanForeclosureDetails accounting >/dev/null 2>&1 || true

call_by_latest() {
  local stan="tdpqa207_$(date +%s%3N)_$RANDOM"
  curl -sS -m 60 -X POST "$API_URL" \
    -H 'Content-Type: application/json' \
    -d "{\"headers\":{\"tenant_code\":\"mfi\",\"user_id\":\"3\",\"client_code\":\"NOVOPAY\",\"channel_code\":\"WEB\",\"function_code\":\"DEFAULT\",\"function_sub_code\":\"BY_LATEST\",\"run_mode\":\"REAL\",\"stan\":\"${stan}\",\"transmission_datetime\":\"${stan}\"},\"request\":{\"account_number_list\":[\"${LAN}\"]}}"
}

assert_api_status() {
  local expect="$1"
  local raw="$2"
  python3 - "$expect" "$raw" <<'PY'
import json, sys
expect = (sys.argv[1] or "").upper()
raw = sys.argv[2] if len(sys.argv) > 2 else ""
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
if expect == "NON_REJECTED":
    if status in ("REJECTED", "REJECT"):
        print("FAIL: BY_LATEST returned REJECTED/REJECT — competing live rows regression")
        sys.exit(1)
    print("PASS: competing live rows — non-REJECTED preferred")
elif expect == "REJECTED":
    if status not in ("REJECTED", "REJECT"):
        print(f"FAIL: expected sole soft-deleted REJECTED, got {status!r}")
        sys.exit(1)
    print("PASS: sole soft-deleted REJECTED still returned")
else:
    print(f"FAIL: unknown expect={expect!r}")
    sys.exit(1)
PY
}

# --- Scenario A: live REJECTED with future created_on must lose to live non-REJECTED ---
bash scripts/bin/db-local-write.sh --sql "
UPDATE mfi_accounting.prepayment_details pd
SET is_deleted = false,
    updated_on = NOW()
FROM mfi_accounting.account a
WHERE a.id = pd.loan_account_id
  AND a.account_number = '${LAN}';

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

echo "fixture A: live REJECT* created_on=2030-06-01; non-rejected payment_mode ensured"

PICKED=$(bash scripts/db-local.sh --sql "
SELECT pd.task_status
FROM mfi_accounting.prepayment_details pd
JOIN mfi_accounting.account a ON a.id = pd.loan_account_id
WHERE a.account_number = '${LAN}'
ORDER BY CASE WHEN pd.is_deleted THEN 1 ELSE 0 END,
         CASE WHEN pd.is_deleted THEN 0
              WHEN pd.task_status IN ('REJECTED','REJECT') THEN 1 ELSE 0 END,
         pd.created_on DESC, pd.id DESC
LIMIT 1;
" | awk 'NR==3 {print $1}')
echo "SQL latest task_status=${PICKED:-<null/blank>}"
case "${PICKED^^}" in
  REJECTED|REJECT)
    echo "FAIL: SQL ORDER BY still picks REJECTED/REJECT when live non-REJECTED exists"
    exit 1
    ;;
esac
echo "SQL pick OK (non-REJECTED preferred)"

RESP=$(call_by_latest)
assert_api_status NON_REJECTED "$RESP"

# --- Scenario B: sole soft-deleted REJECTED (first-time reject) must still show ---
HAVE_REJ=$(bash scripts/db-local.sh --sql "
SELECT COUNT(*)
FROM mfi_accounting.prepayment_details pd
JOIN mfi_accounting.account a ON a.id = pd.loan_account_id
WHERE a.account_number = '${LAN}'
  AND pd.task_status IN ('REJECTED','REJECT');
" | awk 'NR==3 {print $1}')
if [[ "${HAVE_REJ:-0}" -lt 1 ]]; then
  echo "SKIP scenario B: no REJECTED row on LAN=$LAN"
  echo "PASS: scenario A only"
  exit 0
fi

bash scripts/bin/db-local-write.sh --sql "
-- Soft-delete ALL rows (reject path). Make chosen REJECTED the newest soft-deleted
-- attempt so BY_LATEST falls back to it when no live row exists.
UPDATE mfi_accounting.prepayment_details pd
SET is_deleted = true,
    updated_on = NOW()
FROM mfi_accounting.account a
WHERE a.id = pd.loan_account_id
  AND a.account_number = '${LAN}';

UPDATE mfi_accounting.prepayment_details pd
SET created_on = TIMESTAMP '2020-01-01 00:00:00',
    updated_on = NOW()
FROM mfi_accounting.account a
WHERE a.id = pd.loan_account_id
  AND a.account_number = '${LAN}'
  AND COALESCE(pd.task_status, '') NOT IN ('REJECTED','REJECT');

UPDATE mfi_accounting.prepayment_details pd
SET created_on = TIMESTAMP '2030-07-01 12:00:00',
    payment_mode = COALESCE(NULLIF(TRIM(pd.payment_mode), ''), 'CASH'),
    updated_on = NOW()
FROM mfi_accounting.account a
WHERE a.id = pd.loan_account_id
  AND a.account_number = '${LAN}'
  AND pd.id = (
    SELECT pd2.id FROM mfi_accounting.prepayment_details pd2
    JOIN mfi_accounting.account a2 ON a2.id = pd2.loan_account_id
    WHERE a2.account_number = '${LAN}'
      AND pd2.task_status IN ('REJECTED','REJECT')
    ORDER BY pd2.id DESC
    LIMIT 1
  );
" >/dev/null

echo "fixture B: all soft-deleted; REJECTED newest for display fallback"

PICKED_B=$(bash scripts/db-local.sh --sql "
SELECT pd.task_status || '|' || pd.is_deleted::text
FROM mfi_accounting.prepayment_details pd
JOIN mfi_accounting.account a ON a.id = pd.loan_account_id
WHERE a.account_number = '${LAN}'
ORDER BY CASE WHEN pd.is_deleted THEN 1 ELSE 0 END,
         CASE WHEN pd.is_deleted THEN 0
              WHEN pd.task_status IN ('REJECTED','REJECT') THEN 1 ELSE 0 END,
         pd.created_on DESC, pd.id DESC
LIMIT 1;
" | awk 'NR==3 {print $1}')
echo "SQL sole pick=${PICKED_B:-<null>}"
case "${PICKED_B^^}" in
  REJECTED\|T|REJECT\|T|REJECTED\|TRUE|REJECT\|TRUE)
    ;;
  *)
    echo "FAIL: expected soft-deleted REJECTED as sole pick, got ${PICKED_B}"
    exit 1
    ;;
esac

RESP_B=$(call_by_latest)
assert_api_status REJECTED "$RESP_B"

# Restore live flags so LAN is not left fully soft-deleted for later tests
bash scripts/bin/db-local-write.sh --sql "
UPDATE mfi_accounting.prepayment_details pd
SET is_deleted = false,
    updated_on = NOW()
FROM mfi_accounting.account a
WHERE a.id = pd.loan_account_id
  AND a.account_number = '${LAN}'
  AND COALESCE(pd.task_status, '') NOT IN ('REJECTED','REJECT');
" >/dev/null

echo "PASS: both BY_LATEST scenarios"
