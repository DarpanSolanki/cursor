#!/usr/bin/env bash
# DPIC demo runtime helpers — API calls, SQL asserts, reversal harness (no product code).
set -euo pipefail

# Canonical platform-date + safe-repay intelligence (see feedback_dpic_harness_gotchas.md).
_DEMO_RT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_DEMO_RT_DIR/../../lib/dpic_harness_lib.sh"

_DEMO_ACCT_URL="${ACCOUNTING_BASE_URL:-http://localhost:8002}/accounting/api/v1"
_DEMO_REVERSAL_USER_ID="${DEMO_REVERSAL_USER_ID:-53}"

_demo_post_accounting() {
  local api="$1" stan="$2" fc="$3" fsc="$4" req_json="$5"
  python3 - "$_DEMO_ACCT_URL" "$api" "$stan" "$fc" "$fsc" "$_DEMO_REVERSAL_USER_ID" "$req_json" <<'PY'
import json, sys, urllib.request, urllib.error
base, api, stan, fc, fsc, uid, req_s = sys.argv[1:8]
req = json.loads(req_s)
body = {
    "headers": {
        "tenant_code": "mfi",
        "client_code": "NOVOPAY",
        "channel_code": "WEB",
        "end_channel_code": "NOVOPAY",
        "function_code": fc,
        "function_sub_code": fsc,
        "run_mode": "REAL",
        "operation_mode": "SELF",
        "locale": "en-in",
        "stan": stan,
        "transmission_datetime": str(int(__import__("time").time() * 1000)),
        "user_id": uid,
        "actor_type": "EMPLOYEE",
        "user_handle_value": uid,
        "office_id": __import__("os").environ.get("DEMO_OFFICE_ID", "2"),
    },
    "request": req,
}
data = json.dumps(body).encode()
url = f"{base}/{api}"
try:
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST"), timeout=120) as resp:
        out = json.loads(resp.read())
except urllib.error.HTTPError as e:
    out = json.loads(e.read())
print(json.dumps(out))
st = out.get("response_status") or {}
code, status = st.get("code"), st.get("status")
if status not in ("SUCCESS", None) and code not in ("000", "30265", "30273", "30375", "30376", "MOSL-000", "130009"):
    hint = ""
    if code in ("132280", "134243", "130241", "134207"):
        hint = f" [HARNESS hint: see feedback_dpic_harness_gotchas.md code {code}]"
    raise SystemExit(f"FAIL: {api} {fc}/{fsc} -> {code}/{status} {st.get('message','')[:200]}{hint}")
PY
}

_demo_api_get_path() {
  local api="$1" path="$2" account="${3:-${ACCOUNT_NUMBER:-${LAN:-}}}"
  local stan="DEMOGET$(date +%s%N | tail -c 8)"
  local req_json
  case "$api" in
    getLoanAccountOverviewDetails)
      req_json="$(python3 -c "import json; print(json.dumps({'account_number_list':['$account']}))")"
      ;;
    getLoanAccountSummaryDetails)
      req_json="$(python3 -c "import json; print(json.dumps({'account_number':'$account'}))")"
      ;;
    *)
      req_json="$(python3 -c "import json; print(json.dumps({'account_number':'$account'}))")"
      ;;
  esac
  local resp
  resp="$(_demo_post_accounting "$api" "$stan" DEFAULT DEFAULT "$req_json")"
  python3 - "$resp" "$path" <<'PY'
import json, sys, re
obj = json.loads(sys.argv[1])
path = sys.argv[2]
cur = obj
for m in re.finditer(r"([^.\[\]]+)|\[(\d+)\]", path):
    key, idx = m.group(1), m.group(2)
    cur = cur[key] if key else cur[int(idx)]
print(cur)
PY
}

demo_assert_sql_eq() {
  local sql="$1" expected="$2" label="$3"
  local got
  got="$("${PG[@]}" -t -A -v ON_ERROR_STOP=1 -c "$sql" 2>/dev/null | tr -d '[:space:]')"
  if [[ "$got" != "$expected" ]]; then
    echo "FAIL: $label — got '$got' expected '$expected'" >&2
    return 1
  fi
  echo "OK: $label ($got)"
}

demo_assert_sql_gt() {
  local sql="$1" min="$2" label="$3"
  local got
  got="$("${PG[@]}" -t -A -v ON_ERROR_STOP=1 -c "$sql" 2>/dev/null | tr -d '[:space:]')"
  python3 - "$got" "$min" "$label" <<'PY'
import sys
got, min_s, label = sys.argv[1:4]
g, m = float(got), float(min_s)
if g <= m:
    print(f"FAIL: {label} — {g} not > {m}", file=sys.stderr)
    sys.exit(1)
print(f"OK: {label} ({got} > {min_s})")
PY
}

demo_assert_api_field_eq() {
  local api="$1" path="$2" expected="$3"
  local got
  got="$(_demo_api_get_path "$api" "$path")"
  if [[ "$got" != "$expected" ]]; then
    echo "FAIL: $api $path — got '$got' expected '$expected'" >&2
    return 1
  fi
  echo "OK: $api $path = $got"
}

demo_assert_api_field_gt() {
  local api="$1" path="$2" min="$3"
  local got
  got="$(_demo_api_get_path "$api" "$path")"
  python3 - "$got" "$min" "$api $path" <<'PY'
import sys
g, m = float(sys.argv[1]), float(sys.argv[2])
if g <= m:
    print(f"FAIL: {sys.argv[3]} — {g} not > {m}", file=sys.stderr)
    sys.exit(1)
print(f"OK: {sys.argv[3]} ({sys.argv[1]} > {sys.argv[2]})")
PY
}

demo_compute_overdue_repayment_amount() {
  local anchor_date="$1"
  : "${LOAN_ACCOUNT_ID:?LOAN_ACCOUNT_ID required}"
  "${PG[@]}" -t -A -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v anchor_date="$anchor_date" <<'SQL'
SELECT COALESCE(SUM(due_amount - paid_amount - COALESCE(waived_amount, 0)), 0)::numeric(20, 0)
FROM mfi_accounting.loan_due_details
WHERE loan_account_id = :loan_account_id::bigint
  AND is_deleted = false
  AND due_date::date <= :'anchor_date'::date
  AND (due_amount - paid_amount - COALESCE(waived_amount, 0)) > 0;
SQL
}

demo_repayment_timestamps_for_fixture() {
  dpic_repayment_timestamps
}

demo_wall_clock_business_eod_ms() { dpic_platform_repay_ms; }
demo_wall_clock_business_date() { dpic_platform_business_date; }

demo_sync_platform_business_date_from_job_time() {
  local job_time_ms="${1:-${JOB_TIME:-${DEMO_ANCHOR_MS:-}}}"
  [[ -n "$job_time_ms" ]] || return 0
  local ddmmyyyy
  ddmmyyyy="$(python3 - "$job_time_ms" <<'PY'
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
ms = int(sys.argv[1])
d = datetime.fromtimestamp(ms / 1000, ZoneInfo("Asia/Kolkata"))
print(d.strftime("%d-%m-%Y"))
PY
)"
  "${PG[@]}" -v ON_ERROR_STOP=1 -v prop_value="$ddmmyyyy" <<'SQL' >/dev/null
UPDATE mfi_masterdata.configuration
SET prop_value = :'prop_value', updated_on = NOW(), updated_by = 'DPI_FIXTURE_SYNC'
WHERE prop_key = 'current.business.date'
  AND service = 'ACCOUNTING'
  AND COALESCE(is_deleted, false) = false;
SQL
  echo "  demo: synced platform business date -> $ddmmyyyy (job_time=$job_time_ms)"
  bash "$ROOT/scripts/bin/novopay-service.sh" restart masterdata >/dev/null 2>&1 || true
  sleep 4
  bash "$ROOT/scripts/bin/novopay-service.sh" restart accounting >/dev/null 2>&1 \
    || bash "$ROOT/scripts/bin/novopay-service.sh" ensure accounting >/dev/null
  sleep 6
}

demo_ensure_fixture_platform_date() {
  : # batch JOB_TIME only; money APIs use dpic_repayment_timestamps / dpic_platform_repay_ms
}

demo_platform_business_date_ms() {
  local raw
  raw="$("${PG[@]}" -t -A -v ON_ERROR_STOP=1 <<'SQL' 2>/dev/null || true
SELECT prop_value
FROM mfi_masterdata.configuration
WHERE prop_key = 'current.business.date'
  AND service = 'ACCOUNTING'
  AND COALESCE(is_deleted, false) = false
ORDER BY id DESC
LIMIT 1;
SQL
)"
  python3 - "${raw:-}" <<'PY'
import re, sys
from datetime import datetime
from zoneinfo import ZoneInfo

raw = (sys.argv[1] or "").strip()
ist = ZoneInfo("Asia/Kolkata")

def midnight_ms(d: datetime) -> int:
    d = d.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=ist)
    return int(d.timestamp() * 1000)

if raw.isdigit() and len(raw) >= 12:
    print(raw)
    raise SystemExit(0)

for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
    try:
        print(midnight_ms(datetime.strptime(raw[:10], fmt)))
        raise SystemExit(0)
    except ValueError:
        pass

m = re.search(r"(\d{2})-(\d{2})-(\d{4})", raw)
if m:
    d, mo, y = m.groups()
    print(midnight_ms(datetime(int(y), int(mo), int(d))))
    raise SystemExit(0)

print(midnight_ms(datetime.now(ist)))
PY
}

demo_platform_business_eod_ms() {
  python3 - "$(demo_platform_business_date_ms)" <<'PY'
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
ms = int(sys.argv[1])
ist = ZoneInfo("Asia/Kolkata")
d = datetime.fromtimestamp(ms / 1000, ist).replace(hour=18, minute=0, second=0, microsecond=0)
print(int(d.timestamp() * 1000))
PY
}

demo_resolve_repayment_timestamps() {
  REPAY_MS="$(demo_platform_business_date_ms)"
  REPAY_DATE="$(python3 - "$REPAY_MS" <<'PY'
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
ms = int(sys.argv[1])
print(datetime.fromtimestamp(ms / 1000, ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d"))
PY
)"
  export REPAY_MS REPAY_DATE
}

demo_call_loan_repayment() {
  local amount="$1" crn="$2" repay_ms="$3" account="$4"
  local req_json
  req_json="$(python3 - "$amount" "$crn" "$repay_ms" "$account" <<'PY'
import json, sys
amount, crn, repay_ms, account = sys.argv[1:5]
print(json.dumps({
    "loan_repayment_details": {
        "account_number": account,
        "repayment_amount": str(amount),
        "repayment_time": repay_ms,
        "value_date": repay_ms,
        "repayment_mode": "CASH",
        "receipt_number": crn,
        "client_reference_number": crn,
    }
}))
PY
)"
  _demo_post_accounting loanRepayment "$crn" DEFAULT WITHOUT_MAKER_CHECKER "$req_json" >/dev/null
  echo ">>> loanRepayment OK crn=$crn amount=$amount"
}

demo_call_child_loan_repayment() {
  local amount="$1" crn="$2" repay_ms="$3" account="$4"
  local req_json
  req_json="$(python3 - "$amount" "$crn" "$repay_ms" "$account" <<'PY'
import json, sys
amount, crn, repay_ms, account = sys.argv[1:5]
print(json.dumps({
    "account_number": account,
    "repayment_amount": str(amount),
    "repayment_time": repay_ms,
    "value_date": repay_ms,
    "repayment_mode": "CASH",
    "receipt_number": crn,
    "client_reference_number": crn,
}))
PY
)"
  _demo_post_accounting childLoanRepayment "$crn" DEFAULT WITHOUT_MAKER_CHECKER "$req_json" >/dev/null
  echo ">>> childLoanRepayment OK crn=$crn amount=$amount"
}

demo_sync_registry_correlators() {
  python3 - "$ROOT/scripts/testing/registry.json" <<'PY'
import json, os, sys
from pathlib import Path
reg = Path(sys.argv[1])
data = json.loads(reg.read_text(encoding="utf-8"))
c = data.setdefault("_correlators", {})
for k in ("ACCOUNT_NUMBER", "LOAN_ACCOUNT_ID", "JOB_TIME", "FORECLOSURE_DATE", "DEMO_LAN", "LAN"):
    v = os.environ.get(k)
    if v:
        c[k] = str(v)
    if k == "LAN" and v:
        c["ACCOUNT_NUMBER"] = str(v)
reg.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
}

demo_on_or_after_anchor() {
  local today
  today="$("${PG[@]}" -t -A -v ON_ERROR_STOP=1 -c "SELECT CURRENT_DATE::text")"
  [[ "$today" > "${DEMO_ANCHOR_DATE}" || "$today" == "${DEMO_ANCHOR_DATE}" ]]
}

demo_show_dpi_api_keys() {
  for id in accounting.loan_basic dpic.overview_api dpic.summary_api; do
    echo ">>> ntest run $id"
    "$NTEST" run "$id" || return 1
    echo ""
  done
}

demo_show_status() {
  demo_load_state
  if [[ -f "$STATE_FILE" ]]; then
    echo "State: $STATE_FILE"
    grep -E '^(ACCOUNT_NUMBER|LOAN_ACCOUNT_ID|EXT_REF|JOB_TIME|LAST_REPAYMENT)' "$STATE_FILE" || true
  else
    echo "No state file — run phase1 first ($STATE_FILE)"
  fi
  if [[ -n "${LAN:-}" ]]; then
    echo "LAN=$LAN loan_account_id=${LOAN_ACCOUNT_ID:-?}"
  fi
}

demo_require_reversal_services() {
  demo_require_service
  bash "$ROOT/scripts/bin/novopay-service.sh" ensure task
  bash "$ROOT/scripts/bin/novopay-service.sh" ensure actor
}

demo_ensure_task_reversal_prereqs() {
  "${PG[@]}" -v ON_ERROR_STOP=1 -f "$ROOT/scripts/dpic/sql/setup_local_task_reversal_prereqs.sql" >/dev/null
}

demo_load_last_repayment_for_reversal() {
  : "${LOAN_ACCOUNT_ID:?LOAN_ACCOUNT_ID required}"
  local row
  row="$("${PG[@]}" -t -A -F'|' -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" <<'SQL'
SELECT tm.reference_number,
       lapd.client_reference_number,
       lapd.amount::text,
       COALESCE(lapd.dpi_amount, 0)::text
FROM mfi_accounting.loan_account_payments_details lapd
JOIN mfi_accounting.transaction_master tm ON tm.reference_number = lapd.transaction_reference_number
WHERE lapd.loan_account_id = :loan_account_id::bigint
  AND COALESCE(tm.reversed, false) = false
  AND COALESCE(lapd.is_deleted, false) = false
ORDER BY lapd.id DESC
LIMIT 1;
SQL
)"
  [[ -n "$row" ]] || return 1
  IFS='|' read -r REV_TXN_REF REV_CRN REV_AMOUNT REV_DPI <<<"$row"
  export REV_TXN_REF REV_CRN REV_AMOUNT REV_DPI
}

demo_platform_reversal_date_ms() {
  demo_wall_clock_business_eod_ms
}

demo_call_loan_transaction_reversal() {
  local fc="$1" stan="$2" rev_ms="$3"
  : "${REV_TXN_REF:?REV_TXN_REF required — run repayment first}"
  : "${ACCOUNT_NUMBER:-${LAN:-}}"
  local account="${ACCOUNT_NUMBER:-$LAN}"
  local lapd_row
  lapd_row="$("${PG[@]}" -t -A -F'|' -v ON_ERROR_STOP=1 -v ref="$REV_TXN_REF" <<'SQL'
SELECT lapd.amount::text, lapd.principal_amount::text, lapd.interest_amount::text,
       lapd.penalty_amount::text, lapd.fee_amount::text, lapd.excess_amount::text,
       lapd.client_reference_number,
       (EXTRACT(EPOCH FROM lapd.value_date) * 1000)::bigint::text,
       (EXTRACT(EPOCH FROM lapd.transaction_date) * 1000)::bigint::text,
       COALESCE(tc.type, 'LOAN_REPAYMENT'),
       COALESCE(tc.sub_type, 'CASH')
FROM mfi_accounting.loan_account_payments_details lapd
JOIN mfi_accounting.transaction_master tm ON tm.reference_number = lapd.transaction_reference_number
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
WHERE lapd.transaction_reference_number = :'ref'
ORDER BY lapd.id DESC
LIMIT 1;
SQL
)"
  [[ -n "$lapd_row" ]] || { echo "FAIL: no lapd for ref=$REV_TXN_REF" >&2; return 1; }
  IFS='|' read -r amt prin interest penal fee excess crn vd_ms td_ms txn_type txn_sub <<<"$lapd_row"
  local req_json
  req_json="$(python3 - "$account" "$REV_TXN_REF" "$rev_ms" "$vd_ms" "$td_ms" "$amt" "$crn" \
    "$txn_type" "$txn_sub" "$prin" "$interest" "$penal" "$fee" "$excess" <<'PY'
import json, sys
(account, ref, rev_ms, vd_ms, td_ms, amt, crn,
 txn_type, txn_sub, prin, interest, penal, fee, excess) = sys.argv[1:15]
print(json.dumps({
    "transaction_reversal_details": {
        "account_number": account,
        "transaction_ref_no": ref,
        "transaction_reversal_date": rev_ms,
        "transaction_value_date": vd_ms,
        "transaction_date": td_ms,
        "transaction_amount": amt,
        "channel_code": "WEB",
        "client_reference_number": crn,
        "reason": "OTHER",
        "description": "dpic demo reversal",
        "currency": "INR",
        "transaction_type": txn_type,
        "transaction_sub_type": txn_sub,
        "principal_amount": prin,
        "interest_amount": interest,
        "penalty_amount": penal,
        "fee_amount": fee,
        "excess_amount": excess,
    }
}))
PY
)"
  _demo_post_accounting loanAccountTransactionReversal "$stan" "$fc" DEFAULT "$req_json" >/dev/null
  echo ">>> loanAccountTransactionReversal $fc OK ref=$REV_TXN_REF"
}
