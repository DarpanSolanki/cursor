#!/usr/bin/env python3
"""SDCP-11294 — LMS->LOS disburse sync error_message placeholder matrix.

Drives the REAL Kafka disburseLoan path (disburse_loan_api_mfi_local ->
LmsMessageBrokerConsumer) with payloads mutated to trip different accounting
validations, then asserts on both:

  1. the raw accounting payload on los_lms_disbursement_syncmfi_local
  2. mfi_los.disburse_loan_process.failure_reason written by LOS

FAIL when the delivered error_message still carries an unresolved ${...}.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
KAFKA_HOME = os.environ.get("KAFKA_HOME", "/home/darpan/Documents/kafka_2.12-3.7.0")
BOOTSTRAP = os.environ.get("NPS_KAFKA_BOOTSTRAP", "127.0.0.1:9092")
SYNC_TOPIC = "los_lms_disbursement_syncmfi_local"
PAYLOADS = ROOT / "scripts" / "disbursement" / "payloads" / "canonical"
PUBLISHER = ROOT / "scripts" / "testing" / "disbursement" / "disburse_kafka_publish.py"
RESET = ROOT / "scripts" / "sql" / "reset" / "reset_disburse_loan_replay_mfi_from_json.py"
SCRATCH = Path(__file__).resolve().parent
PLACEHOLDER = re.compile(r"\$\{[^}]*}")

PRODUCT_ENTITY = {"2": "INDIVIDUAL", "44": "GROUP", "45": "INDIVIDUAL"}


def sh(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, capture_output=True, check=False, **kw)


def db_read(sql: str) -> str:
    p = sh(["bash", str(ROOT / "scripts" / "db-local.sh"), "--sql", sql])
    return p.stdout


def db_write(sql: str) -> None:
    f = SCRATCH / "_tmp_write.sql"
    f.write_text(sql, encoding="utf-8")
    p = sh(["bash", str(ROOT / "scripts" / "bin" / "db-local-write.sh"), "--file", str(f)])
    if p.returncode != 0:
        raise RuntimeError(f"db write failed: {p.stderr or p.stdout}")


def live_consumer_member() -> str | None:
    """An assigned CONSUMER-ID, not merely an existing group.

    agent-ops reports "consumer assigned (0s)" off stale group metadata, so a group
    with committed offsets and zero members looks healthy while nothing is consumed.
    """
    p = sh([
        f"{KAFKA_HOME}/bin/kafka-consumer-groups.sh", "--bootstrap-server", BOOTSTRAP,
        "--describe", "--group", "disburse_loan_api_consumer_mfi_local",
    ])
    for line in p.stdout.splitlines():
        cols = line.split()
        if len(cols) >= 7 and cols[0] == "disburse_loan_api_consumer_mfi_local" and cols[6] != "-":
            return cols[6]
    return None


def message_template(error_code: str) -> str | None:
    """The notification template accounting resolves from (Redis NOTIFICATION db 2).

    A scenario only exercises the fix when this template carries a ${...}.
    """
    if not error_code or error_code == "UNKNOWN_ERROR":
        return None
    p = sh(["redis-cli", "-n", "2", "get", f"localmfi_{error_code}_en-in"])
    val = (p.stdout or "").strip()
    return val or None


def end_offset() -> int:
    p = sh([
        f"{KAFKA_HOME}/bin/kafka-get-offsets.sh",
        "--bootstrap-server", BOOTSTRAP, "--topic", SYNC_TOPIC, "--time", "-1",
    ])
    for line in p.stdout.splitlines():
        if SYNC_TOPIC in line:
            return int(line.rsplit(":", 1)[1])
    raise SystemExit(f"cannot read end offset: {p.stdout} {p.stderr}")


def read_from(offset: int, want_ref: str, timeout_ms: int = 12000) -> dict | None:
    """Exit as soon as our record lands.

    --max-messages is what makes this fast: without it the console consumer sits
    out the whole --timeout-ms even when the message arrived in the first second.
    """
    deadline = time.time() + timeout_ms / 1000.0
    cursor = offset
    while time.time() < deadline:
        p = sh([
            f"{KAFKA_HOME}/bin/kafka-console-consumer.sh", "--bootstrap-server", BOOTSTRAP,
            "--topic", SYNC_TOPIC, "--partition", "0", "--offset", str(cursor),
            "--max-messages", "1", "--timeout-ms", "4000",
        ])
        got = False
        for line in p.stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            got = True
            cursor += 1
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if str(msg.get("external_ref_number")) == str(want_ref):
                return msg
        if not got:
            time.sleep(1)
    return None


# ---------------------------------------------------------------- mutations

def drop_purpose(entry_list, code):
    for e in entry_list or []:
        e["purpose"] = [p for p in (e.get("purpose") or []) if p.get("code") != code]
    return [e for e in (entry_list or []) if e.get("purpose")]


def m_root_rep_acct_missing(req):
    req["disbursement_repayment_account_details"] = drop_purpose(
        req.get("disbursement_repayment_account_details"), "REP_ACCT")


def m_member_rep_acct_missing(req):
    for m in req.get("member_details") or []:
        m["disbursement_repayment_account_details"] = drop_purpose(
            m.get("disbursement_repayment_account_details"), "REP_ACCT")


def m_member_rep_acct_duplicate(req):
    for m in req.get("member_details") or []:
        dra = m.get("disbursement_repayment_account_details") or []
        rep = [e for e in dra if any(p.get("code") == "REP_ACCT" for p in (e.get("purpose") or []))]
        if rep:
            dup = copy.deepcopy(rep[0])
            dup["account_number"] = str(dup.get("account_number", "1")) + "9"
            dra.append(dup)
        m["disbursement_repayment_account_details"] = dra


def m_root_rep_acct_number_overlong(req):
    for e in req.get("disbursement_repayment_account_details") or []:
        if any(p.get("code") == "REP_ACCT" for p in (e.get("purpose") or [])):
            e["account_number"] = "9" * 64


def m_installments_missing(req):
    req["repayment_details"]["number_of_installments"] = ""


def m_first_repayment_date_missing(req):
    req["repayment_details"]["first_repayment_date"] = ""


def m_sanction_date_missing(req):
    req["loan_details"]["sanction_date"] = ""


def m_repayment_mode_invalid(req):
    req["repayment_details"]["repayment_mode"] = "NOTALLOWED"


def m_interest_rate_out_of_range(req):
    req.setdefault("interest_details", {})["interest_rate"] = "99.000000"


def m_loan_amount_out_of_range(req):
    req["loan_details"]["loan_amount"] = "999999999.000000"
    req["loan_details"]["approved_amount"] = "999999999.000000"


SCENARIOS = [
    ("S15_INDL_loan_amount_range_134131", "indl", m_loan_amount_out_of_range),
    ("S16_JLG_loan_amount_range_134131", "jlg", m_loan_amount_out_of_range),
    ("S17_SHG_loan_amount_range_134131", "shg", m_loan_amount_out_of_range),
    ("S12_INDL_interest_rate_range_142001", "indl", m_interest_rate_out_of_range),
    ("S13_JLG_interest_rate_range_142001", "jlg", m_interest_rate_out_of_range),
    ("S14_SHG_interest_rate_range_142001", "shg", m_interest_rate_out_of_range),
    ("S9_INDL_repayment_mode_invalid_132168", "indl", m_repayment_mode_invalid),
    ("S10_JLG_repayment_mode_invalid_132168", "jlg", m_repayment_mode_invalid),
    ("S11_SHG_repayment_mode_invalid_132168", "shg", m_repayment_mode_invalid),
    ("S1_SHG_member_rep_acct_missing", "shg", m_member_rep_acct_missing),
    ("S2_SHG_member_rep_acct_duplicate", "shg", m_member_rep_acct_duplicate),
    ("S3_INDL_root_rep_acct_missing", "indl", m_root_rep_acct_missing),
    ("S4_INDL_rep_acct_number_overlong", "indl", m_root_rep_acct_number_overlong),
    ("S5_JLG_root_rep_acct_missing", "jlg", m_root_rep_acct_missing),
    ("S6_JLG_installments_missing", "jlg", m_installments_missing),
    ("S7_JLG_first_repayment_date_missing", "jlg", m_first_repayment_date_missing),
    ("S8_SHG_sanction_date_missing", "shg", m_sanction_date_missing),
]

PAYLOAD_FILE = {
    "jlg": PAYLOADS / "disburse_loan_sanity_request_4495972134234554346565.json",
    "indl": PAYLOADS / "disburse_loan_sanity_request_370164.json",
    "shg": PAYLOADS / "disburse_loan_sanity_request_shg_41333333.json",
}


def wait_consumer_idle(timeout_s: int = 45) -> bool:
    """Block until the disburse consumer has drained.

    The fixture reset bulk-UPDATEs loan_account/account for the same customers the
    in-flight disburse is writing. Firing it mid-flight wedges the consumer thread on
    a Yugabyte row lock; it then stops polling and the coordinator evicts it, so every
    later scenario times out. Draining first keeps writer and reset off the same rows.
    """
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        p = sh([
            f"{KAFKA_HOME}/bin/kafka-consumer-groups.sh", "--bootstrap-server", BOOTSTRAP,
            "--describe", "--group", "disburse_loan_api_consumer_mfi_local",
        ])
        for line in p.stdout.splitlines():
            cols = line.split()
            if len(cols) >= 6 and cols[0] == "disburse_loan_api_consumer_mfi_local":
                if cols[5] in ("0", "-"):
                    time.sleep(2)
                    return True
        time.sleep(2)
    return False


def reset_customer_loans(customer_ids: list[str]) -> None:
    """Close every prior loan for the payload's customers.

    Each scenario leaves an ACTIVE loan, so without this the next run for the same
    customer dies on 134494 (active loan for product) before reaching its validation.
    """
    ids = ",".join(str(int(c)) for c in customer_ids if str(c).strip().isdigit())
    if not ids:
        return
    db_write(
        "SET search_path TO mfi_accounting;\n"
        "UPDATE account a SET is_deleted=true, status='CLOSED', "
        "closing_date=COALESCE(a.closing_date, CURRENT_TIMESTAMP), updated_on=CURRENT_TIMESTAMP, "
        "updated_by='sdcp11294_matrix' FROM loan_account la "
        f"WHERE a.id=la.account_id AND la.customer_id IN ({ids}) AND a.is_deleted=false;\n"
        "UPDATE loan_account la SET is_deleted=true, loan_status='CLOSED', "
        "updated_on=CURRENT_TIMESTAMP, updated_by='sdcp11294_matrix', "
        "external_ref_number=LEFT('VOID_'||la.account_id::text||'_'"
        "||COALESCE(NULLIF(TRIM(la.external_ref_number),''),'NA'),64) "
        f"WHERE la.customer_id IN ({ids}) AND la.is_deleted=false;\n"
    )


def payload_customer_ids(req: dict) -> list[str]:
    ids = [str((req.get("loan_details") or {}).get("customer_id") or "")]
    ids += [str(m.get("customer_id") or "") for m in req.get("member_details") or []]
    return [i for i in ids if i]


def seed_los_row(entity_type: str, ext_ref: str) -> None:
    db_write(
        "DELETE FROM mfi_los.disburse_loan_process "
        f"WHERE entity_type='{entity_type}' AND entity_id={int(ext_ref)};\n"
        "INSERT INTO mfi_los.disburse_loan_process "
        "(id, entity_id, entity_type, status, retry_count, created_on, is_stp) VALUES "
        f"((SELECT COALESCE(MAX(id),0)+1 FROM mfi_los.disburse_loan_process), {int(ext_ref)}, "
        f"'{entity_type}', 1, 0, NOW(), true);\n"
    )


def los_failure_reason(entity_type: str, ext_ref: str) -> str:
    out = db_read(
        "SELECT COALESCE(failure_reason,'') FROM mfi_los.disburse_loan_process "
        f"WHERE entity_type='{entity_type}' AND entity_id={int(ext_ref)} ORDER BY id DESC LIMIT 1"
    )
    lines = [l.strip() for l in out.splitlines()]
    for i, l in enumerate(lines):
        if set(l) <= set("-+") and l:
            return lines[i + 1] if i + 1 < len(lines) else ""
    return ""


def run_scenario(name: str, product: str, mutate, ext_ref: str) -> dict:
    payload = json.loads(PAYLOAD_FILE[product].read_text(encoding="utf-8"))
    req = payload["request"]
    product_id = str(req["loan_details"]["product_id"])
    entity_type = PRODUCT_ENTITY[product_id]

    req["disbursement_details"]["external_ref_number"] = ext_ref
    req["loan_details"].pop("account_number", None)
    wait_consumer_idle()
    reset_customer_loans(payload_customer_ids(req))

    mutate(req)
    mutated = SCRATCH / f"_payload_{name}.json"
    mutated.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    seed_los_row(entity_type, ext_ref)
    before = end_offset()

    pub = sh(["python3", str(PUBLISHER), "--request-file", str(mutated)])
    if pub.returncode != 0:
        return {"scenario": name, "product": product.upper(), "verdict": "PUBLISH_FAIL",
                "detail": (pub.stderr or pub.stdout).strip()[:300]}

    msg = read_from(before, ext_ref)
    if msg is None:
        return {"scenario": name, "product": product.upper(), "verdict": "NO_SYNC_MESSAGE",
                "detail": f"no sync record for ext_ref={ext_ref} from offset {before}"}

    failure_reason = ""
    deadline = time.time() + 8
    while time.time() < deadline:
        failure_reason = los_failure_reason(entity_type, ext_ref)
        if failure_reason:
            break
        time.sleep(1)

    error_code = str(msg.get("error_code") or "")
    error_message = str(msg.get("error_message") or "")
    status = str(msg.get("status") or "")
    template = message_template(error_code)

    unresolved = bool(PLACEHOLDER.search(error_message)) or bool(PLACEHOLDER.search(failure_reason))
    if status == "SUCCESS":
        verdict = "NO_VALIDATION_FIRED"
    elif unresolved:
        verdict = "FAIL"
    elif template and PLACEHOLDER.search(template):
        verdict = "PASS_PROVEN"
    else:
        verdict = "NOT_EXERCISED"

    return {
        "scenario": name,
        "product": product.upper(),
        "external_ref_number": ext_ref,
        "status": status,
        "error_code": error_code,
        "template": template,
        "error_message": error_message,
        "los_failure_reason": failure_reason,
        "verdict": verdict,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="run")
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    member = live_consumer_member()
    if not member:
        print("BLOCKED: no live member on disburse_loan_api_consumer_mfi_local — accounting's "
              "Kafka consumer is not attached. A group with committed offsets but no member "
              "still answers 'assigned'; restart accounting and re-check.", flush=True)
        return 2
    print(f"[preflight] live disburse consumer: {member}", flush=True)

    base = int(os.environ.get("SDCP11294_EXT_REF_BASE", "88110000"))
    total = len([s for s in SCENARIOS if not args.only or args.only in s[0]])
    print(f"[{args.label}] starting {total} scenarios against the running accounting build", flush=True)
    results = []
    for idx, (name, product, mutate) in enumerate(SCENARIOS):
        if args.only and args.only not in name:
            continue
        t0 = time.time()
        try:
            r = run_scenario(name, product, mutate, str(base + idx))
        except Exception as exc:  # scratch harness: report, do not abort matrix
            r = {"scenario": name, "product": product.upper(), "verdict": "HARNESS_ERROR",
                 "detail": f"{type(exc).__name__}: {exc}"}
        results.append(r)
        print(f"[{args.label} {len(results)}/{total}] {name} {r.get('product','')} "
              f"code={r.get('error_code','-')} {r['verdict']} "
              f"({time.time()-t0:.0f}s) :: "
              f"{r.get('los_failure_reason', r.get('detail',''))[:70]}", flush=True)

    out = SCRATCH / f"result_{args.label}.json"
    out.write_text(json.dumps(results, indent=1), encoding="utf-8")

    print("\n=== MATRIX", args.label, "===")
    print(f"{'scenario':<40} {'prod':<5} {'code':<14} {'verdict':<16} {'template':<34} delivered")
    for r in results:
        print(f"{r['scenario']:<40} {r.get('product',''):<5} {r.get('error_code',''):<14} "
              f"{r['verdict']:<16} {str(r.get('template'))[:32]:<34} "
              f"{r.get('error_message', r.get('detail',''))[:46]}")

    proven = [r for r in results if r["verdict"] == "PASS_PROVEN"]
    failed = [r for r in results if r["verdict"] == "FAIL"]
    idle = [r for r in results if r["verdict"] == "NOT_EXERCISED"]
    print(f"\nPASS_PROVEN={len(proven)}  FAIL={len(failed)}  NOT_EXERCISED={len(idle)}")
    print("NOT_EXERCISED = the returned code has no ${...} template; proves nothing about the fix.")
    print(f"written: {out}")

    return 1 if failed or not proven else 0


if __name__ == "__main__":
    sys.exit(main())
