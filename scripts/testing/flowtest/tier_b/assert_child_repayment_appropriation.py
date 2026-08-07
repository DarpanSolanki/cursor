#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = str(Path(__file__).resolve().parents[4])
ACCT = os.environ.get("ACCT_URL", "http://localhost:8002/accounting/api/v1")
PARENT_LAN = os.environ["PARENT_LAN"]
CHILD_SPEC = os.environ["CHILD_SPEC"]

SEQ_TO_COMPONENT = {
    "APP_LOGIC_PRIN": "PRIN",
    "APP_LOGIC_INT": "INT",
    "APP_LOGIC_PNLT": "PINT",
    "APP_LOGIC_FEES": "FEE",
}


def q(sql):
    out = subprocess.run(["bash", f"{ROOT}/scripts/db-local.sh", "--sql", sql],
                         capture_output=True, text=True, cwd=ROOT, check=True).stdout
    rows, started = [], False
    for line in out.splitlines():
        if line.strip() and set(line.strip()) <= set("-+"):
            started = True
            continue
        if not started or line.startswith("(") or not line.strip():
            continue
        rows.append([c.strip() for c in line.split("|")])
    return rows


def business_date():
    d = datetime.now(ZoneInfo("Asia/Kolkata")).replace(hour=18, minute=0, second=0, microsecond=0)
    return int(d.timestamp() * 1000), d.strftime("%Y-%m-%d")


def loan_id(lan):
    return int(q("SELECT la.account_id FROM mfi_accounting.loan_account la "
                 "JOIN mfi_accounting.account a ON a.id=la.account_id "
                 f"WHERE a.account_number='{lan}'")[0][0])


def liquidation_config(lid):
    r = q("SELECT lp.product_id, la.asset_criteria_slabs_id FROM mfi_accounting.loan_account la "
          f"JOIN mfi_accounting.loan_product lp ON lp.id=la.loan_product_id WHERE la.account_id={lid}")[0]
    c = q("SELECT sequence_1, sequence_2, sequence_3, sequence_4, liquidation_order "
          f"FROM mfi_accounting.loan_product_asset_criteria WHERE product_id={r[0]} "
          f"AND asset_criteria_slab_id={r[1]}")[0]
    return {SEQ_TO_COMPONENT[c[i]]: i + 1 for i in range(4)}, c[4]


def open_dues(lid, as_on):
    rows = q("SELECT id, component_type, due_date::date, due_amount, paid_amount, waived_amount "
             f"FROM mfi_accounting.loan_due_details WHERE loan_account_id={lid} "
             f"AND due_date <= DATE '{as_on}' AND due_amount > paid_amount + waived_amount "
             "AND is_deleted = false ORDER BY created_on, id")
    return [{"id": int(r[0]), "component": r[1], "due_date": r[2], "paid": Decimal(r[4]),
             "pending": Decimal(r[3]) - Decimal(r[4]) - Decimal(r[5])} for r in rows]


def sort_key(precedence, order):
    if order == "LIQ_INSTL":
        return lambda d: (d["due_date"], precedence[d["component"]])
    if order == "LIQ_COMP":
        return lambda d: (precedence[d["component"]], d["due_date"])
    raise SystemExit(f"unsupported liquidation_order {order}")


def simulate(dues, precedence, order, amount):
    split = {"PRIN": Decimal(0), "INT": Decimal(0), "PINT": Decimal(0), "FEE": Decimal(0)}
    per_due, left = {}, amount
    for d in sorted(dues, key=sort_key(precedence, order)):
        take = min(left, d["pending"])
        per_due[d["id"]] = d["paid"] + take
        split[d["component"]] += take
        left -= take
        if left == 0:
            break
    return split, left, per_due


def post(api, crn, req, fsc="WITHOUT_MAKER_CHECKER"):
    body = {"headers": {"tenant_code": "mfi", "client_code": "NOVOPAY", "channel_code": "WEB",
                        "end_channel_code": "NOVOPAY", "function_code": "DEFAULT",
                        "function_sub_code": fsc, "run_mode": "REAL", "operation_mode": "SELF",
                        "locale": "en-in", "stan": crn,
                        "transmission_datetime": str(int(time.time() * 1000)), "user_id": "263",
                        "actor_type": "EMPLOYEE", "user_handle_value": "263", "office_id": "2"},
            "request": req}
    r = urllib.request.Request(f"{ACCT}/{api}", data=json.dumps(body).encode(),
                               headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(r, timeout=180) as resp:
            out = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        out = json.loads(e.read())
    st = out.get("response_status") or {}
    if st.get("code") != "000":
        raise SystemExit(f"FAIL: {api} -> {st.get('code')}/{st.get('status')} {st.get('message','')[:300]}")
    return out


def fire_child_batch():
    started = int(time.time())
    subprocess.run([sys.executable, f"{ROOT}/scripts/testing/api-fire.py",
                    "childLoanEventProcessingBatchJob", "--batch",
                    "--job-time", str(int(time.time() * 1000))],
                   cwd=ROOT, capture_output=True, text=True, check=False)
    subprocess.run([sys.executable, "-c",
                    f"import sys; sys.path.insert(0, {ROOT + '/scripts/dcf_sanity'!r});"
                    "from clb_queue_harness import wait_batch_by_start;"
                    f"wait_batch_by_start('childLoanEventProcessingBatchJob', {started}, timeout_s=180)"],
                   cwd=ROOT, capture_output=True, text=True, check=False)


STATE = "/tmp/tierb_flow1_expect.json"


def recheck():
    st = json.load(open(STATE))
    failed = []
    for c in st:
        row = q("SELECT amount, principal_amount, interest_amount, penalty_amount, fee_amount, excess_amount "
                f"FROM mfi_accounting.loan_account_payments_details WHERE id = {c['row_id']}")[0]
        got = [Decimal(x) for x in row]
        names = ["amount", "principal_amount", "interest_amount", "penalty_amount", "fee_amount", "excess_amount"]
        for n, a, x in zip(names, got, [Decimal(v) for v in c["expected_row"]]):
            ok = a == x
            if not ok:
                failed.append(n)
            print(f"  {'OK  ' if ok else 'FAIL'} {c['lan']}.{n}: actual={a} expected={x}")
    if failed:
        raise SystemExit(f"FAIL: {len(failed)} childLoanRepayment appropriation assert(s) failed")
    print("=== childLoanRepayment appropriation assert PASS ===")


def main():
    if os.environ.get("RECHECK") == "1":
        return recheck()
    repay_ms, repay_date = business_date()
    children = []
    for spec in CHILD_SPEC.split(","):
        lan, amt = spec.split(":")
        lid = loan_id(lan)
        precedence, order = liquidation_config(lid)
        pin = os.environ.get("PIN_PRECEDENCE")
        if pin:
            precedence = {c: i + 1 for i, c in enumerate(pin.split(","))}
        dues = open_dues(lid, repay_date)
        amount = Decimal(amt)
        total_open = sum(d["pending"] for d in dues)
        if amount >= total_open:
            raise SystemExit(f"FAIL: {lan} amount {amount} not partial vs open {total_open}")
        expected, leftover, per_due = simulate(dues, precedence, order, amount)
        base = q("SELECT COALESCE(MAX(id),0) FROM mfi_accounting.loan_account_payments_details "
                 f"WHERE loan_account_id={lid}")[0][0]
        children.append({"lan": lan, "id": lid, "amount": amount, "order": order, "base_id": base,
                         "precedence": precedence, "expected": expected,
                         "leftover": leftover, "per_due": per_due})
        print(f"{lan} order={order} precedence={precedence} amount={amount} open={total_open}")
        print(f"  expected PRIN={expected['PRIN']} INT={expected['INT']} "
              f"PINT={expected['PINT']} FEE={expected['FEE']} excess={leftover}")

    total = sum(c["amount"] for c in children)
    crn = f"TIERB{int(time.time())}"
    post("loanRepayment", crn, {
        "loan_repayment_details": {"account_number": PARENT_LAN, "repayment_amount": str(total),
                                   "repayment_time": str(repay_ms), "value_date": str(repay_ms),
                                   "repayment_mode": "CASH", "receipt_number": crn,
                                   "client_reference_number": crn},
        "child_loans": [{"account_number": c["lan"], "repayment_amount": str(c["amount"])}
                        for c in children]})
    print(f">>> parent loanRepayment OK crn={crn} total={total}")
    fire_child_batch()

    failed, state = [], []
    for c in children:
        row = q("SELECT id, amount, principal_amount, interest_amount, penalty_amount, fee_amount, excess_amount "
                f"FROM mfi_accounting.loan_account_payments_details WHERE loan_account_id={c['id']} "
                f"AND id > {c['base_id']} ORDER BY id DESC LIMIT 1")
        if not row:
            failed.append((c["lan"], "payments row", "missing"))
            print(f"  FAIL {c['lan']}: no new loan_account_payments_details row (base id {c['base_id']})")
            continue
        row_id = int(row[0][0])
        got = [Decimal(x) for x in row[0][1:]]
        e = c["expected"]
        state.append({"lan": c["lan"], "row_id": row_id,
                      "expected_row": [str(c["amount"]), str(e["PRIN"]), str(e["INT"]),
                                       str(e["PINT"]), str(e["FEE"]), str(c["leftover"])]})
        checks = [("amount", got[0], c["amount"]),
                  ("principal_amount", got[1], e["PRIN"]),
                  ("interest_amount", got[2], e["INT"]),
                  ("penalty_amount", got[3], e["PINT"]),
                  ("fee_amount", got[4], e["FEE"]),
                  ("excess_amount", got[5], c["leftover"])]
        for n, a, x in checks:
            ok = a == x
            if not ok:
                failed.append((c["lan"], n, f"actual={a} expected={x}"))
            print(f"  {'OK  ' if ok else 'FAIL'} {c['lan']}.{n}: actual={a} expected={x}")
        ids = ",".join(str(i) for i in c["per_due"])
        for r in q("SELECT id, paid_amount FROM mfi_accounting.loan_due_details "
                   f"WHERE id IN ({ids}) AND loan_account_id={c['id']}"):
            i, paid = int(r[0]), Decimal(r[1])
            if paid != c["per_due"][i]:
                failed.append((c["lan"], f"loan_due_details[{i}].paid_amount",
                               f"actual={paid} expected={c['per_due'][i]}"))
                print(f"  FAIL {c['lan']}.loan_due_details[{i}].paid_amount: "
                      f"actual={paid} expected={c['per_due'][i]}")

    json.dump(state, open(STATE, "w"))
    if failed:
        raise SystemExit(f"FAIL: {len(failed)} childLoanRepayment appropriation assert(s) failed")
    print("=== childLoanRepayment appropriation assert PASS ===")


if __name__ == "__main__":
    main()
