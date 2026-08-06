#!/usr/bin/env python3
"""Drive NEFTv2 INDL/JLG to COMPLETED via accounting callback APIs (local simulator path).

Outbound bank legs hit Chameleon :8018 (doGenericSyncSTPNEF/NEI/Inquiry).
Stage advance requires ingress callbacks to accounting (not real bank).

Flow:
  NEFT_STAGE_1_PENDING
    → POST doGenericSyncSTPBankNEFNeftCallBack (faxml PROCESSED + paymentrefno)
  → disburseLoan function_sub_code=NEFT_STAGE_1_SUCCESS (fires ST_NEI)
  → POST doGenericSyncSTPBankNEINeftCallBack (faml codstatus=P)
  → COMPLETED

Group (SHG/JLG child) CLMT legs — `--parent-lan`:
  A child's NEFT stage does NOT live on `loan_account.disbursement_status`; it lives
  in the CLMT `loan_account_events_queue.data.disbursement_status`, and its CRR rows
  are booked under the PARENT LAN as `LOAN_DISBURSEMENT_EXTREF<childRef>_NEFT_NEF`.
  Looking either up by the child LAN finds nothing, which is why the local suite used
  to leave a group parked at PARENT_SUCCESS forever.

  `DoGenericSyncSTPBankNeftCallBackProcessor` already handles this (CHILD_TXN_MARKER
  `_EXTREF`): ST_NEF moves the CLMT row NEFT_STAGE_1_PENDING|DTFC_SUCCESS →
  NEFT_STAGE_1_SUCCESS and stamps the UTR; ST_NEI moves NEFT_STAGE_1_SUCCESS|
  NEFT_STAGE_2_PENDING → COMPLETED with event_status='C' and then calls
  syncParentAfterChildQueueProgress → parent COMPLETED once every CLMT is 'C'.
  The child path accepts NEI straight from NEFT_STAGE_1_SUCCESS, so no intermediate
  `disburseLoan NEFT_STAGE_1_SUCCESS` stage call is needed (unlike the single-loan path).

Usage:
  python3 scripts/complete_neft_v2_via_callbacks.py --lan 6000…
  python3 scripts/complete_neft_v2_via_callbacks.py --ext-ref-prefix <prefix>
  python3 scripts/complete_neft_v2_via_callbacks.py --parent-lan 6004162825
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCT = os.environ.get("ACCOUNTING_BASE", "http://127.0.0.1:8002/accounting")
TENANT = os.environ.get("TENANT_CODE", "mfi")


def _psql(sql: str) -> str:
    env = {**os.environ, "PGPASSWORD": os.environ.get("PGPASSWORD", "yugabyte")}
    return subprocess.check_output(
        [
            "psql",
            "-h",
            os.environ.get("YB_HOST", "localhost"),
            "-p",
            os.environ.get("YB_PORT", "5433"),
            "-U",
            os.environ.get("YB_USER", "yugabyte"),
            "-d",
            os.environ.get("YB_DB", "yugabyte"),
            "-v",
            "ON_ERROR_STOP=1",
            "-t",
            "-A",
            "-c",
            sql,
        ],
        env=env,
        text=True,
    ).strip()


def _loan_row(lan: str | None, ext_prefix: str | None) -> tuple[str, str, str, str]:
    if lan:
        row = _psql(
            f"""
SELECT a.account_number, la.external_ref_number, la.disbursement_status, la.account_id::text
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.account a ON a.id = la.account_id
WHERE a.account_number = '{lan}' AND COALESCE(la.is_deleted,false)=false
LIMIT 1;
"""
        )
    else:
        pref = (ext_prefix or "").replace("'", "''")
        row = _psql(
            f"""
SELECT a.account_number, la.external_ref_number, la.disbursement_status, la.account_id::text
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.account a ON a.id = la.account_id
WHERE COALESCE(la.is_deleted,false)=false
  AND la.external_ref_number LIKE '{pref}%'
ORDER BY la.updated_on DESC NULLS LAST
LIMIT 1;
"""
        )
    if not row or "|" not in row:
        raise SystemExit(f"loan not found lan={lan!r} ext_prefix={ext_prefix!r}")
    lan_s, ext, status, aid = row.split("|", 3)
    return lan_s, ext, status, aid


def _nef_client_ref(lan: str) -> str:
    row = _psql(
        f"""
SELECT client_reference_number
FROM mfi_accounting.client_request_response_log
WHERE loan_account_number = '{lan}'
  AND transaction_type LIKE '%NEFT_NEF%'
ORDER BY id DESC
LIMIT 1;
"""
    )
    if not row:
        raise SystemExit(f"no NEFT_NEF CRR for LAN {lan} — run disburse with --neft-version v2 first")
    return row.strip()


def _pending_clmt_rows(parent_lan: str) -> list[tuple[str, str, str]]:
    """(queue_row_id, child_ext_ref, clmt_stage) for CLMT rows not yet 'C'."""
    out = _psql(
        f"""
SELECT q.id::text, q.filler_2, COALESCE(q.data::json->>'disbursement_status','')
FROM mfi_accounting.loan_account_events_queue q
JOIN mfi_accounting.loan_account la ON la.account_id = q.parent_account_id
JOIN mfi_accounting.account a ON a.id = la.account_id
WHERE a.account_number = '{parent_lan}'
  AND q.event_type = 'CLMT'
  AND q.event_status <> 'C'
  AND COALESCE(q.is_deleted,false) = false
ORDER BY q.id;
"""
    )
    rows = []
    for line in out.splitlines():
        if line.strip():
            parts = line.split("|")
            rows.append((parts[0].strip(), parts[1].strip(), parts[2].strip()))
    return rows


def _child_nef_client_ref(parent_lan: str, child_ext_ref: str) -> str:
    """Child NEF CRR is booked under the PARENT LAN as ..._EXTREF<ref>_NEFT_NEF."""
    row = _psql(
        f"""
SELECT client_reference_number
FROM mfi_accounting.client_request_response_log
WHERE loan_account_number = '{parent_lan}'
  AND transaction_type LIKE '%%EXTREF{child_ext_ref}\\_NEFT\\_NEF'
ORDER BY id DESC
LIMIT 1;
"""
    )
    return row.strip()


def _clmt_state(row_id: str) -> tuple[str, str]:
    out = _psql(
        f"""
SELECT event_status, COALESCE(data::json->>'disbursement_status','')
FROM mfi_accounting.loan_account_events_queue WHERE id = {int(row_id)};
"""
    )
    if "|" not in out:
        return "", ""
    a, b = out.split("|", 1)
    return a.strip(), b.strip()


def _parent_status(parent_lan: str) -> str:
    return _psql(
        f"""
SELECT la.disbursement_status FROM mfi_accounting.loan_account la
JOIN mfi_accounting.account a ON a.id = la.account_id
WHERE a.account_number = '{parent_lan}';
"""
    ).strip()


def _fire_child_queue_batch() -> None:
    """childLoanEventProcessingBatchJob drains CLB/CLMT rows the callbacks advanced."""
    subprocess.run(
        [
            "python3",
            str(ROOT / "scripts/testing/api-fire.py"),
            "childLoanEventProcessingBatchJob",
            "--batch",
        ],
        cwd=str(ROOT),
        check=False,
        capture_output=True,
        text=True,
    )


def _dedupe_child_queue_rows() -> None:
    """Restore filler_2 uniqueness before resolving any child leg.

    Must run AFTER the disbursement (not only in reset): the run itself creates a new
    CLMT row carrying the canonical payload's hardcoded member ext ref, so it collides
    with rows left by every previous local group. `findOneByFiller2` is a single-result
    lookup, so the NEFT child callback then dies with
    IncorrectResultSizeDataAccessException and the child never leaves stage 1.
    Keeps the newest row per (filler_2, event_type) — i.e. this run's.
    """
    subprocess.run(
        [
            "bash",
            str(ROOT / "scripts/bin/db-local-write.sh"),
            "--file",
            str(ROOT / "scripts/sql/reset/local_dedupe_child_queue_rows.sql"),
        ],
        cwd=str(ROOT),
        check=False,
        capture_output=True,
        text=True,
    )


def complete_group_children(parent_lan: str, *, run_queue_batch: bool = True) -> int:
    """Drive every pending CLMT NEFT leg to COMPLETED, then the parent."""
    _dedupe_child_queue_rows()
    pending = _pending_clmt_rows(parent_lan)
    if not pending:
        print(f"  no pending CLMT rows for parent {parent_lan}")
    for row_id, child_ref, stage in pending:
        print(f"→ CLMT row={row_id} child_ext_ref={child_ref} stage={stage or '(none)'}")
        pref = _child_nef_client_ref(parent_lan, child_ref)
        if not pref:
            print(f"  SKIP: no ..._EXTREF{child_ref}_NEFT_NEF CRR under parent {parent_lan} "
                  f"(child rail is not NEFT, or NEF never fired)")
            continue
        print(f"  NEF client_reference_number={pref}")

        _, stage = _clmt_state(row_id)
        if stage in {"NEFT_STAGE_1_PENDING", "DTFC_SUCCESS"}:
            print("  → ST_NEF callback")
            _post_api("doGenericSyncSTPBankNEFNeftCallBack", _nef_callback(pref))
            time.sleep(2)
            _, stage = _clmt_state(row_id)
            print(f"    stage={stage}")

        if stage in {"NEFT_STAGE_1_SUCCESS", "NEFT_STAGE_2_PENDING"}:
            print("  → ST_NEI callback")
            _post_api("doGenericSyncSTPBankNEINeftCallBack", _nei_callback(pref))
            time.sleep(2)
            ev, stage = _clmt_state(row_id)
            print(f"    stage={stage} event_status={ev}")

        ev, stage = _clmt_state(row_id)
        if ev != "C":
            print(f"  WARN CLMT row {row_id} still event_status={ev} stage={stage}")

    if run_queue_batch:
        print("→ childLoanEventProcessingBatchJob")
        _fire_child_queue_batch()
        time.sleep(3)

    status = _parent_status(parent_lan)
    left = _pending_clmt_rows(parent_lan)
    print(f"=== parent {parent_lan} disbursement_status={status} pending_clmt={len(left)} ===")
    return 0 if status == "COMPLETED" else 1


def _post_api(api: str, body: dict) -> dict:
    import urllib.request

    url = f"{ACCT}/api/v1/{api}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8", "replace")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


def _envelope(request_obj: dict, *, function_code: str = "DEFAULT", function_sub_code: str = "DEFAULT") -> dict:
    stan = f"neftv2_{uuid.uuid4().hex[:16]}"
    return {
        "headers": {
            "tenant_code": TENANT,
            "actor_code": "SYSTEM",
            "channel_code": "API",
            "client_ip": "127.0.0.1",
            "function_code": function_code,
            "function_sub_code": function_sub_code,
            "stan": stan,
            "transmission_datetime": str(int(time.time() * 1000)),
            "user_id": "1",
        },
        "request": request_obj,
    }


def _nef_callback(paymentrefno: str) -> dict:
    return _envelope(
        {
            "faxml": {
                "header": {
                    "txtstatus": "PROCESSED",
                    "idtxn": "ST_NEF",
                    "extsysname": "NOVSL",
                    "codcurr": "INR",
                    "errorcode": "0",
                },
                "paymentlist": {
                    "payment": {
                        "paymentrefno": paymentrefno,
                        "errorcode": "0",
                        "errorMessage": "Success",
                        "referenceno": f"HDFCH{paymentrefno[-8:]}",
                    }
                },
            }
        }
    )


def _nei_callback(paymentrefno: str) -> dict:
    return _envelope(
        {
            "faml": {
                "inqlist": {
                    "payment": {
                        "paymentrefno": paymentrefno,
                        "codstatus": "P",
                        "errorcode": "0",
                        "referenceno": f"HDFCH{paymentrefno[-8:]}",
                    }
                }
            }
        }
    )


def _load_stage_payload(request_file: Path, lan: str, ext_ref: str, sub: str) -> dict:
    """Full disburseLoan body — stage resume still runs mandatoryFieldValidator (office_id, …)."""
    raw = json.loads(request_file.read_text(encoding="utf-8"))
    headers = dict(raw.get("headers") or {})
    headers.update(
        {
            "tenant_code": headers.get("tenant_code") or TENANT,
            "function_code": "DEFAULT",
            "function_sub_code": sub,
            "stan": f"neftv2_{uuid.uuid4().hex[:16]}",
            "transmission_datetime": str(int(time.time() * 1000)),
            "channel_code": headers.get("channel_code") or "API",
            "client_ip": headers.get("client_ip") or "127.0.0.1",
            "user_id": str(headers.get("user_id") or "1"),
            "run_mode": headers.get("run_mode") or "REAL",
        }
    )
    req = dict(raw.get("request") or {})
    # Flatten / ensure account_number for stage-sub validators
    req["account_number"] = lan
    req["loan_account_number"] = lan
    loan_details = dict(req.get("loan_details") or {})
    loan_details["account_number"] = lan
    req["loan_details"] = loan_details
    disb = dict(req.get("disbursement_details") or {})
    disb["external_ref_number"] = ext_ref
    # Canonical fixtures often leave "{{$timestamp}}" — pattern is ^[a-zA-Z0-9]+$
    crn = str(disb.get("client_reference_number") or "")
    if (not crn) or "{" in crn or "$" in crn or not crn.isalnum():
        disb["client_reference_number"] = f"neftv2{uuid.uuid4().hex[:14]}"
    req["disbursement_details"] = disb
    return {"headers": headers, "request": req}


def _disburse_stage(lan: str, ext_ref: str, sub: str, request_file: Path) -> dict:
    return _post_api("disburseLoan", _load_stage_payload(request_file, lan, ext_ref, sub))


def _wait_status(lan: str, want: set[str], timeout_s: int = 120) -> str:
    deadline = time.time() + timeout_s
    last = ""
    while time.time() < deadline:
        _, _, last, _ = _loan_row(lan, None)
        if last in want:
            return last
        time.sleep(2)
    raise SystemExit(f"timeout waiting {want} for {lan}; last={last}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--lan", default="")
    p.add_argument("--ext-ref-prefix", default="")
    p.add_argument(
        "--parent-lan",
        default="",
        help="SHG/JLG group parent LAN — completes every pending CLMT child NEFT leg, "
        "then drains the queue so the parent reaches COMPLETED",
    )
    p.add_argument("--skip-queue-batch", action="store_true",
                   help="with --parent-lan: skip firing childLoanEventProcessingBatchJob")
    p.add_argument("--skip-nei-replay", action="store_true")
    p.add_argument(
        "--request-file",
        default=str(
            ROOT / "scripts/disbursement/payloads/canonical/disburse_loan_sanity_request_370164.json"
        ),
        help="Full disburseLoan JSON (stage resume needs office_id and other mandatory fields)",
    )
    args = p.parse_args()
    if args.parent_lan:
        return complete_group_children(
            args.parent_lan, run_queue_batch=not args.skip_queue_batch
        )
    if not args.lan and not args.ext_ref_prefix:
        raise SystemExit("pass --lan, --ext-ref-prefix or --parent-lan")
    request_file = Path(args.request_file)
    if not request_file.is_file():
        raise SystemExit(f"request file not found: {request_file}")

    lan, ext, status, _aid = _loan_row(args.lan or None, args.ext_ref_prefix or None)
    print(f"loan lan={lan} ext={ext} status={status}")
    pref = _nef_client_ref(lan)
    print(f"NEF client_reference_number={pref}")

    if status in {"NEFT_STAGE_1_PENDING", "DTFC_SUCCESS"}:
        print("→ NEF callback")
        r = _post_api("doGenericSyncSTPBankNEFNeftCallBack", _nef_callback(pref))
        print("  callback resp keys:", list(r.keys())[:8])
        status = _wait_status(lan, {"NEFT_STAGE_1_SUCCESS", "NEFT_STAGE_2_PENDING", "COMPLETED"})
        print(f"  status={status}")

    if status == "NEFT_STAGE_1_SUCCESS" and not args.skip_nei_replay:
        print(f"→ disburseLoan NEFT_STAGE_1_SUCCESS (ST_NEI) via {request_file.name}")
        r = _disburse_stage(lan, ext, "NEFT_STAGE_1_SUCCESS", request_file)
        print("  disburseLoan resp:", json.dumps(r)[:300])
        status = _wait_status(lan, {"NEFT_STAGE_2_PENDING", "COMPLETED"}, timeout_s=180)
        print(f"  status={status}")

    if status == "NEFT_STAGE_2_PENDING":
        print("→ NEI callback")
        # Bank paymentrefno is the NEF ref (same in ST_NEI inquiry body); NEI CRR
        # client_reference_number (…0801) is the inquiry external ref and will NOT resolve.
        r = _post_api("doGenericSyncSTPBankNEINeftCallBack", _nei_callback(pref))
        print("  callback resp keys:", list(r.keys())[:8], "paymentrefno=", pref)
        status = _wait_status(lan, {"COMPLETED"}, timeout_s=180)
        print(f"  status={status}")

    print(f"=== DONE lan={lan} disbursement_status={status} ===")
    return 0 if status == "COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
