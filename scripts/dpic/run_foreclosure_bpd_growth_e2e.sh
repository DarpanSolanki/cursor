#!/usr/bin/env bash
# SDCP-11016: DEFAULT fetchLoanForeclosureSimulationDetails twice — bpd_amount increases.
# Needs LAN with maturity > foreclosure dates and schedule installments after FD.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export PGPASSWORD="${PGPASSWORD:-yugabyte}"
LAN="${ACCOUNT_NUMBER:-6004055825}"
LOAN_ID="${LOAN_ACCOUNT_ID:-8101960}"
ACCT_URL="${ACCOUNTING_URL:-http://localhost:8002/accounting/api/v1}"

fail() { echo "FAIL: $*" >&2; exit 1; }

bash "$ROOT/scripts/bin/novopay-service.sh" ensure accounting

# Value-date in test env = wall clock when wall > business date
FD1="$(python3 - <<'PY'
from datetime import datetime, timezone, timedelta
IST=timezone(timedelta(hours=5,minutes=30))
d=datetime.now(IST).replace(hour=0,minute=0,second=0,microsecond=0)
print(int(d.timestamp()*1000))
PY
)"
FD2="$(python3 - <<'PY'
from datetime import datetime, timezone, timedelta
IST=timezone(timedelta(hours=5,minutes=30))
d=datetime.now(IST).replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(days=7)
print(int(d.timestamp()*1000))
PY
)"

echo "=== SDCP-11016 BPD growth DEFAULT (LAN=$LAN FD1=$FD1 FD2=$FD2) ==="

# Restore soft-deleted installments after FD so ValidateDataForForeclosureProcessor finds next due
psql -h 127.0.0.1 -p 5433 -U yugabyte -d yugabyte -v ON_ERROR_STOP=1 -c "
UPDATE mfi_accounting.loan_installment_details
SET is_deleted = false, updated_on = NOW(), updated_by = 'SDCP11016'
WHERE loan_account_id = $LOAN_ID AND is_deleted = true
  AND installment_date::date >= to_timestamp($FD1/1000)::date;
UPDATE mfi_accounting.loan_due_details
SET is_deleted = false, updated_on = NOW(), updated_by = 'SDCP11016'
WHERE loan_account_id = $LOAN_ID AND is_deleted = true
  AND loan_installment_details_id IN (
    SELECT id FROM mfi_accounting.loan_installment_details
    WHERE loan_account_id = $LOAN_ID AND installment_date::date >= to_timestamp($FD1/1000)::date
  );
" >/dev/null

mat="$(psql -h 127.0.0.1 -p 5433 -U yugabyte -d yugabyte -t -A -c "
SELECT maturity_date::date FROM mfi_accounting.loan_account WHERE account_id=$LOAN_ID;
")"
[[ -n "$mat" ]] || fail "no maturity for loan $LOAN_ID"
echo "  maturity=$mat"

python3 - "$LAN" "$FD1" "$FD2" "$ACCT_URL" <<'PY'
import json, sys, time, urllib.request
from decimal import Decimal

LAN, FD1, FD2, ACCT = sys.argv[1:5]

def post(fd):
    body = {
        "headers": {
            "tenant_code": "mfi", "client_code": "NOVOPAY", "channel_code": "WEB",
            "end_channel_code": "NOVOPAY", "function_code": "DEFAULT",
            "function_sub_code": "DEFAULT", "run_mode": "REAL", "operation_mode": "SELF",
            "locale": "en-in", "stan": f"bpd_g_{int(time.time()*1000)}",
            "transmission_datetime": str(int(time.time() * 1000)),
            "user_id": "103", "actor_type": "EMPLOYEE", "user_handle_value": "103", "office_id": "2",
        },
        "request": {"account_number": LAN, "foreclosure_date": fd},
    }
    req = urllib.request.Request(
        f"{ACCT}/fetchLoanForeclosureSimulationDetails",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())

r1 = post(FD1)
r2 = post(FD2)
s1, s2 = r1.get("response_status", {}), r2.get("response_status", {})
if s1.get("code") != "30360":
    raise SystemExit(f"FAIL: FD1 DEFAULT sim {s1}")
if s2.get("code") != "30360":
    raise SystemExit(f"FAIL: FD2 DEFAULT sim {s2}")
fs1 = r1["foreclosure_simulation_details"]
fs2 = r2["foreclosure_simulation_details"]
bpd1 = Decimal(str(fs1.get("bpd_amount") or 0))
bpd2 = Decimal(str(fs2.get("bpd_amount") or 0))
print(f"DEFAULT FD1 bpd={bpd1} billed_dpi={fs1.get('billed_dpi')}")
print(f"DEFAULT FD2 bpd={bpd2} billed_dpi={fs2.get('billed_dpi')}")
if bpd2 <= bpd1:
    raise SystemExit(f"FAIL: expected bpd_amount to increase ({bpd1} → {bpd2})")
print(f"PASS: DEFAULT bpd_amount increased {bpd1} → {bpd2}")
PY
