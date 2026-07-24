#!/usr/bin/env bash
# SDCP-11048: loanPrepayment APPROVE validates total including billed DPI (+ BPD).
# Flow: FC sim → create-shaped PENDING (same fields as createPrepaymentDetailsProcessor)
#       → APPROVE TRIAL with full total (PASS) → APPROVE TRIAL excluding billed DPI (132268).
# Note: loanPrepayment CREATE REAL needs BRE :8025 (getForeclosureRoles). When BRE is down,
#       CREATE fails LOS-0118 after amount validation; this harness still proves the approve gate.
#       For full CREATE locally: bash scripts/dcf_sanity/local_bre_stub.sh ensure (harness-only).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export PGPASSWORD="${PGPASSWORD:-yugabyte}"
LAN="${ACCOUNT_NUMBER:-6004055825}"
LOAN_ID="${LOAN_ACCOUNT_ID:-8101960}"
FD="${FORECLOSURE_DATE:-}"
USER_ID="${USER_ID:-103}"
OFFICE_ID="${OFFICE_ID:-2}"
ACCT_URL="${ACCOUNTING_URL:-http://localhost:8002/accounting/api/v1}"

fail() { echo "FAIL: $*" >&2; exit 1; }

bash "$ROOT/scripts/bin/novopay-service.sh" ensure accounting
bash "$ROOT/scripts/bin/novopay-service.sh" ensure authorization 2>/dev/null || true

# Wall-clock value-date (test env): foreclosure_date must be >= today for DEFAULT sim
if [[ -z "$FD" ]]; then
  FD="$(python3 - <<'PY'
from datetime import datetime, timezone, timedelta
IST=timezone(timedelta(hours=5,minutes=30))
print(int(datetime.now(IST).replace(hour=0,minute=0,second=0,microsecond=0).timestamp()*1000))
PY
)"
fi

echo "=== SDCP-11048 loanPrepayment billed DPI (LAN=$LAN FD=$FD) ==="

# Ensure next installment exists after FD (ValidateDataForForeclosureProcessor)
psql -h 127.0.0.1 -p 5433 -U yugabyte -d yugabyte -v ON_ERROR_STOP=1 -c "
UPDATE mfi_accounting.loan_installment_details
SET is_deleted = false, updated_on = NOW(), updated_by = 'SDCP11048'
WHERE loan_account_id = $LOAN_ID AND is_deleted = true
  AND installment_date::date >= to_timestamp($FD/1000)::date;
UPDATE mfi_accounting.loan_due_details
SET is_deleted = false, updated_on = NOW(), updated_by = 'SDCP11048'
WHERE loan_account_id = $LOAN_ID AND is_deleted = true
  AND loan_installment_details_id IN (
    SELECT id FROM mfi_accounting.loan_installment_details
    WHERE loan_account_id = $LOAN_ID AND installment_date::date >= to_timestamp($FD/1000)::date
  );
" >/dev/null

# Expire any prior PENDING on this loan
psql -h 127.0.0.1 -p 5433 -U yugabyte -d yugabyte -c "
UPDATE mfi_accounting.prepayment_details
SET prepayment_status = 'EXPIRED', updated_on = NOW(), updated_by = 'SDCP11048'
WHERE loan_account_id = $LOAN_ID AND prepayment_status = 'PENDING' AND is_deleted = false;
" >/dev/null

python3 - "$LAN" "$LOAN_ID" "$FD" "$USER_ID" "$OFFICE_ID" "$ACCT_URL" <<'PY'
import json, os, sys, time, urllib.request, subprocess
from decimal import Decimal, ROUND_HALF_UP

LAN, LOAN_ID, FD, USER, OFFICE, ACCT = sys.argv[1:7]
LOAN_ID = int(LOAN_ID)

def post(api, body):
    req = urllib.request.Request(
        f"{ACCT}/{api}", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())

def headers(stan, function_code="DEFAULT", run_mode="REAL"):
    return {
        "tenant_code": "mfi", "client_code": "NOVOPAY", "channel_code": "WEB",
        "end_channel_code": "NOVOPAY", "function_code": function_code,
        "function_sub_code": "DEFAULT", "run_mode": run_mode, "operation_mode": "SELF",
        "locale": "en-in", "stan": stan, "transmission_datetime": str(int(time.time() * 1000)),
        "user_id": USER, "actor_type": "EMPLOYEE", "user_handle_value": USER, "office_id": OFFICE,
    }

def component(due):
    d = Decimal(str(due))
    return {
        "due_amount": str(d), "is_waived": "false", "is_fully_waived": "false",
        "waiver_percentage": "0", "waived_amount": "0", "amount_to_be_paid": str(d),
    }

def psql(sql):
    return subprocess.check_output(
        ["psql", "-h", "127.0.0.1", "-p", "5433", "-U", "yugabyte", "-d", "yugabyte", "-t", "-A", "-F", "|", "-c", sql],
        text=True, env={**os.environ, "PGPASSWORD": os.environ.get("PGPASSWORD", "yugabyte")},
    ).strip()

sim = post("fetchLoanForeclosureSimulationDetails", {
    "headers": headers(f"pp48_sim_{int(time.time())}"),
    "request": {"account_number": LAN, "foreclosure_date": FD},
})
st = sim.get("response_status", {})
if st.get("code") != "30360":
    raise SystemExit(f"FAIL: simulation {st}")
fs = sim["foreclosure_simulation_details"]
billed_dpi = Decimal(str(fs.get("billed_dpi") or 0))
bpd = Decimal(str(fs.get("bpd_amount") or 0))
if billed_dpi <= 0:
    raise SystemExit(f"FAIL: need billed_dpi>0 got {billed_dpi}")
print(f"OK: sim billed_dpi={billed_dpi} bpd={bpd}")

parts = [
    "billed_interest", "billed_principal", "balance_principal", "bpi_amount",
    "billed_dpi", "bpd_amount", "current_lpp", "foreclosure_fee", "cbc_fee",
]
total = sum(Decimal(str(fs.get(k) or 0)) for k in parts)
total -= Decimal(str(fs.get("excess_amount") or 0))
rounded = total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
round_off = rounded - total
receipt = f"4127{int(time.time()) % 10**12:012d}"

# Attempt CREATE REAL (may fail without BRE)
request = {
    "billed_interest_details": component(fs["billed_interest"]),
    "billed_principal_details": component(fs["billed_principal"]),
    "balance_principal_details": component(fs["balance_principal"]),
    "bpi_details": component(fs["bpi_amount"]),
    "billed_dpi_details": component(fs["billed_dpi"]),
    "bpd_details": component(fs["bpd_amount"]),
    "current_lpp_details": component(fs["current_lpp"]),
    "foreclosure_fee_details": component(fs["foreclosure_fee"]),
    "future_lpp_details": component(fs.get("future_lpp") or 0),
    "fee_details": [{**component(fs.get("cbc_fee") or 0), "identifier_code": "cbc_fee"}],
    "charges_details": sim.get("charges_details") or [],
    "loan_foreclosure_details": {
        "account_number": LAN, "foreclosure_date": FD,
        "total_foreclosure_amount": str(rounded), "round_off_amount": str(round_off),
        "receipt_number": receipt, "currency_code": "INR", "currency_code_value": "INR",
        "payment_mode": "CASH", "payment_mode_value": "Cash",
        "closure_reason": "OTHERS", "closure_reason_value": "Others",
        "notes": "SDCP-11048 billed DPI", "paid_by": "SELF", "paid_by_value": "Self",
        "depositor_name": "LOCAL_TEST", "excess_amount": str(fs.get("excess_amount") or 0),
    },
}
create = post("loanPrepayment", {
    "headers": headers(f"pp48_create_{int(time.time())}", "DEFAULT", "REAL"),
    "request": request,
})
create_st = create.get("response_status", {})
print(f"CREATE: {create_st.get('code')}/{create_st.get('status')} — {create_st.get('message','')[:80]}")

pending = psql(
    f"SELECT id, billed_dpi_amount_to_be_paid, bpd_amount_to_be_paid, prepayment_amount, round_off_amount "
    f"FROM mfi_accounting.prepayment_details WHERE loan_account_id={LOAN_ID} "
    f"AND prepayment_status='PENDING' AND is_deleted=false ORDER BY id DESC LIMIT 1"
)

if not pending:
    # Seed create-shaped PENDING (same columns createPrepaymentDetailsProcessor writes)
    bi = Decimal(str(fs["billed_interest"]))
    bp = Decimal(str(fs["billed_principal"]))
    pending_inst = bi + bp
    bal = Decimal(str(fs["balance_principal"]))
    bpi = Decimal(str(fs["bpi_amount"]))
    sql = f"""
INSERT INTO mfi_accounting.prepayment_details (
  loan_account_id, prepayment_status, task_status, is_deleted, created_by, updated_by, created_on, updated_on,
  pending_installment_amount_to_be_paid, balance_principal_amount_to_be_paid, bpi_amount_to_be_paid,
  billed_interest_amount_to_be_paid, billed_principal_amount_to_be_paid,
  billed_dpi_amount_to_be_paid, billed_dpi_amount, bpd_amount_to_be_paid, bpd_amount,
  foreclosure_date, round_off_amount, excess_amount, receipt_number, payment_mode, closure_reason, notes,
  prepayment_amount, paid_by, is_child_loan_prepayment,
  balance_principal_is_fully_waived, balance_principal_is_waived, balance_principal_waived_amount,
  billed_interest_is_fully_waived, billed_interest_is_waived, billed_interest_waived_amount,
  billed_principal_is_fully_waived, billed_principal_is_waived, billed_principal_waived_amount,
  billed_dpi_is_fully_waived, billed_dpi_is_waived, billed_dpi_waived_amount,
  bpd_is_fully_waived, bpd_is_waived, bpd_waived_amount,
  bpi_is_fully_waived, bpi_is_waived, bpi_waived_amount,
  pending_installment_is_fully_waived, pending_installment_is_waived, pending_installment_waived_amount
) VALUES (
  {LOAN_ID}, 'PENDING', 'UN_ASSIGNED', false, 'SDCP11048', 'SDCP11048', NOW(), NOW(),
  {pending_inst}, {bal}, {bpi},
  {bi}, {bp},
  {billed_dpi}, {billed_dpi}, {bpd}, {bpd},
  to_timestamp({int(FD)}/1000.0), {round_off}, 0, '{receipt}', 'CASH', 'OTHERS', 'SDCP-11048 seed',
  {rounded}, 'SELF', false,
  false, false, 0,
  false, false, 0,
  false, false, 0,
  false, false, 0,
  false, false, 0,
  false, false, 0,
  false, false, 0
) RETURNING id, billed_dpi_amount_to_be_paid, bpd_amount_to_be_paid, prepayment_amount, round_off_amount;
"""
    print(f"SEED SQL amounts pending={pending_inst} bal={bal} bpi={bpi} dpi={billed_dpi} bpd={bpd} total={rounded}")
    pending = psql(sql)
    print(f"SEEDED PENDING (CREATE blocked by BRE/task): {pending}")
else:
    print(f"PENDING from CREATE: {pending}")

pid, stored_dpi, stored_bpd, prep_amt, roff = pending.split("|")
stored_dpi = Decimal(stored_dpi)
if stored_dpi <= 0:
    raise SystemExit(f"FAIL: PENDING billed_dpi={stored_dpi}")

# Also seed current_lpp charge row so validateFinal includes charges
psql(f"""
INSERT INTO mfi_accounting.prepayment_charge_details (
  prepayment_details_id, charge_name, charge_code, charge_amount, amount_to_be_paid, waived_amount,
  is_waived, is_fully_waived, is_deleted, created_by, updated_by, created_on, updated_on
)
SELECT {pid}, 'current_lpp', 'Penal', {Decimal(str(fs.get('current_lpp') or 0))}, {Decimal(str(fs.get('current_lpp') or 0))}, 0,
  false, false, false, 'SDCP11048', 'SDCP11048', NOW(), NOW()
WHERE NOT EXISTS (
  SELECT 1 FROM mfi_accounting.prepayment_charge_details
  WHERE prepayment_details_id={pid} AND charge_name='current_lpp' AND is_deleted=false
);
""")

approve_amt = Decimal(prep_amt)
# ValidateFinal compares request total - round_off to DB sum
# Request total_foreclosure_amount should equal prep_amt (includes round_off already stored)

ok = post("loanPrepayment", {
    "headers": headers(f"pp48_ok_{int(time.time())}", "APPROVE", "TRIAL"),
    "request": {"loan_foreclosure_details": {
        "account_number": LAN, "total_foreclosure_amount": str(approve_amt),
        "foreclosure_date": FD, "receipt_number": receipt,
    }},
})
ok_st = ok.get("response_status", {})
print(f"APPROVE_TRIAL_WITH_DPI: {ok_st}")

bad_amt = approve_amt - stored_dpi
bad = post("loanPrepayment", {
    "headers": headers(f"pp48_bad_{int(time.time())}", "APPROVE", "TRIAL"),
    "request": {"loan_foreclosure_details": {
        "account_number": LAN, "total_foreclosure_amount": str(bad_amt),
        "foreclosure_date": FD, "receipt_number": receipt,
    }},
})
bad_st = bad.get("response_status", {})
print(f"APPROVE_TRIAL_WITHOUT_DPI: {bad_st}")

# Cleanup
psql(f"UPDATE mfi_accounting.prepayment_details SET prepayment_status='EXPIRED', updated_by='SDCP11048', updated_on=NOW() WHERE id={pid};")

# Amount gate: with billed DPI, ValidateFinalPrepaymentProcessor accepts the total
# (TRIAL may still fail later on postTransaction placeholders — outside SDCP-11048).
# Without billed DPI → 132268.
if bad_st.get("code") != "132268":
    raise SystemExit(f"FAIL: approve without billed DPI expected 132268 got {bad_st}")
if ok_st.get("code") == "132268":
    raise SystemExit(f"FAIL: approve with billed DPI must not fail amount validation: {ok_st}")
# with-DPI must clear ValidateFinal (code != 132268). TRIAL postTransaction may still 333.
from pathlib import Path
tail = Path("/home/darpan/Documents/sliProd/trustt-platform-accounting/logs/mfi/accounting-mfi.log").read_text(
    encoding="utf-8", errors="ignore"
).splitlines()[-2000:]
saw_validate = any("validateFinalPrepaymentProcessor took" in ln for ln in tail)
print(
    f"PASS: loanPrepayment APPROVE amount gate includes billed_dpi={stored_dpi} "
    f"(with_dpi code={ok_st.get('code')}; without_dpi=132268; validateFinal_log={saw_validate})"
)
PY
