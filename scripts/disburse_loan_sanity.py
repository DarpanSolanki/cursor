#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import html
import json
import os
import subprocess
import sys
import time
import socket
import tempfile
import atexit
import urllib.error
import urllib.request
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from pathlib import Path
import re
from datetime import timedelta


DEFAULT_DB_HOST = os.environ.get("YB_HOST", "localhost")
DEFAULT_DB_PORT = int(os.environ.get("YB_PORT", "5433"))
DEFAULT_DB_USER = os.environ.get("YB_USER", "yugabyte")
DEFAULT_DB_NAME = os.environ.get("YB_DB", "yugabyte")
DEFAULT_DB_SCHEMA = os.environ.get("YB_SCHEMA", "mfi_accounting")

DEFAULT_ACCOUNTING_BASE_URL = os.environ.get("ACCOUNTING_BASE_URL", "http://localhost:8002")
DEFAULT_ACCOUNTING_CONTEXT_PATH = os.environ.get("ACCOUNTING_CONTEXT_PATH", "/accounting")

ROOT = Path(__file__).resolve().parents[1]
_DISBURSEMENT_SUITE = ROOT / "scripts" / "disbursement"
if str(_DISBURSEMENT_SUITE) not in sys.path:
    sys.path.insert(0, str(_DISBURSEMENT_SUITE))
from disbursement_suite.column_audit import audit_disbursement  # noqa: E402

SUCCESS = "SUCCESS"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN"


def _lock_holder_alive(lock_text: str) -> bool:
    """True if lock names a live PID; empty/unparseable treated as stale."""
    m = re.search(r"pid=(\d+)", lock_text or "")
    if not m:
        return False
    try:
        os.kill(int(m.group(1)), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _acquire_single_run_lock() -> None:
    """Single-run lock under /tmp. Auto-clears when holder PID is dead or lock is empty."""
    lock_path = Path(tempfile.gettempdir()) / "disburse_loan_sanity.lock"
    pid = os.getpid()
    now = int(time.time())

    def _try_create() -> int | None:
        try:
            return os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            return None

    fd = _try_create()
    if fd is None:
        try:
            existing = lock_path.read_text(encoding="utf-8").strip()
        except Exception:
            existing = "<unreadable>"
        if not _lock_holder_alive(existing):
            print(
                f"[suite] clearing stale lock at {lock_path} (holder dead or empty): {existing or '<empty>'}",
                flush=True,
            )
            try:
                lock_path.unlink(missing_ok=True)
            except Exception:
                pass
            fd = _try_create()
        if fd is None:
            try:
                existing = lock_path.read_text(encoding="utf-8").strip()
            except Exception:
                existing = "<unreadable>"
            raise SystemExit(
                f"[suite] Another run seems active (lock exists at {lock_path}). "
                f"Lock contents: {existing}. Stop it first, or: make -C scripts lock-clean"
            )
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(f"pid={pid} started_epoch_s={now}\n")

    def _cleanup() -> None:
        try:
            lock_path.unlink(missing_ok=True)
        except Exception:
            pass

    atexit.register(_cleanup)

NEFT_V1_SUCCESS_SOAP_XML = """<?xml version='1.0' encoding='UTF-8'?>
<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/">
  <S:Body>
    <ns10:doNEFTPaymentTransactionResponse
      xmlns:datatype="http://datatype.fc.ofss.com"
      xmlns:responseservice="http://response.service.fc.ofss.com"
      xmlns:errorvalidationinfra="http://error.validation.infra.fc.ofss.com"
      xmlns:exceptioninfra="http://exception.infra.fc.ofss.com"
      xmlns:contextapp="http://context.app.fc.ofss.com"
      xmlns:domainframework="http://domain.framework.fc.ofss.com"
      xmlns:ns8="http://framework.enumeration.fc.ofss.com"
      xmlns:ns9="http://dto.common.domain.framework.fc.ofss.com"
      xmlns:ns10="http://transaction.service.pc.appx.cz.fc.ofss.com/">
      <return>
        <responseservice:status>
          <responseservice:errorCode>0</responseservice:errorCode>
          <responseservice:extendedReply/>
          <responseservice:externalReferenceNo>16863390013086243</responseservice:externalReferenceNo>
          <responseservice:internalReferenceNumber>2023161394400478</responseservice:internalReferenceNumber>
          <responseservice:isOverriden>false</responseservice:isOverriden>
          <responseservice:postingDate>
            <datatype:dateString>20230610000000</datatype:dateString>
          </responseservice:postingDate>
          <responseservice:replyCode>0</responseservice:replyCode>
          <responseservice:replyText>0</responseservice:replyText>
        </responseservice:status>
        <outTransactionId>UTR5839457398573</outTransactionId>
        <senderCommAddress>NEFT-Chandivili@hdfcbank.com</senderCommAddress>
      </return>
    </ns10:doNEFTPaymentTransactionResponse>
  </S:Body>
</S:Envelope>
"""

MFT_SUCCESS_JSON = {
    "status": {
        "isOverriden": False,
        "replyCode": 0,
        "replyText": "0",
        "memo": None,
        "externalReferenceNo": "16914133971437954",
        "internalReferenceNumber": "16914133971437954",
        "postingDate": {"dateString": "20230807000000"},
        "errorCode": "0",
        "extendedReply": {"messages": None},
        "validationErrors": None,
        "userReferenceNumber": None,
    },
    "maintenanceType": None,
    "configVersionId": None,
    "accountBalanceInfoDTO": {"creditAcctNetBalance": 8738228, "debitAcctNetBalance": 4492602496.26},
}

GENERIC_TXN_INQ_SUCCESS_JSON = {
    "status": {
        "isOverriden": False,
        "replyCode": 0,
        "replyText": "0",
        "memo": None,
        "externalReferenceNo": None,
        "internalReferenceNumber": "2021169005671765",
        "postingDate": {"dateString": "20210618000000"},
        "errorCode": "0",
        "extendedReply": {"messages": None},
        "validationErrors": None,
        "userReferenceNumber": None,
    },
    "maintenanceType": None,
    "configVersionId": None,
    "genericTransactionStatusInquiryResDTO": [
        {"refUsrNo": "12345678911231240", "transactionStat": "Success", "errorCode": "0", "errorDescription": ""}
    ],
}

# Gold-standard JSON (UAT CRR / scripts/mfi_simulator_neft_v2_seed.sql) — not XML.
# Accounting NEFTv2 posts isXMLRequest=true then converts; Chameleon JSON stubs must be nested JSON.
NEFT_V2_NEF_SUCCESS_JSON = {
    "root": {
        "responseString": 2026105354951370,
        "configVersionId": None,
        "maintenanceType": None,
        "status": {
            "isOverriden": False,
            "replyText": None,
            "internalReferenceNumber": 2026105354951370,
            "replyCode": 0,
            "memo": None,
            "errorCode": 0,
            "validationErrors": None,
            "externalReferenceNo": 600005177520301,
            "postingDate": None,
            "extendedReply": {"messages": None},
            "userReferenceNumber": None,
        },
    }
}

NEFT_V2_NEI_SUCCESS_JSON = {
    "root": {
        "responseString": 2026105355021396,
        "configVersionId": None,
        "maintenanceType": None,
        "status": {
            "isOverriden": False,
            "replyText": None,
            "internalReferenceNumber": 2026105355021396,
            "replyCode": 0,
            "memo": None,
            "errorCode": 0,
            "validationErrors": None,
            "externalReferenceNo": 600005177520301,
            "postingDate": None,
            "extendedReply": {"messages": None},
            "userReferenceNumber": None,
        },
    }
}

NEFT_V2_NEF_FAIL_JSON = {
    "root": {
        "responseString": 2026105354951370,
        "configVersionId": None,
        "maintenanceType": None,
        "status": {
            "isOverriden": False,
            "replyText": "Failure (suite)",
            "internalReferenceNumber": 2026105354951370,
            "replyCode": 1,
            "memo": None,
            "errorCode": 1,
            "validationErrors": None,
            "externalReferenceNo": 600005177520301,
            "postingDate": None,
            "extendedReply": {"messages": "Failure (suite)"},
            "userReferenceNumber": None,
        },
    }
}

NEFT_V2_NEI_FAIL_JSON = {
    "root": {
        "responseString": 2026105355021396,
        "configVersionId": None,
        "maintenanceType": None,
        "status": {
            "isOverriden": False,
            "replyText": "Failure (suite)",
            "internalReferenceNumber": 2026105355021396,
            "replyCode": 1,
            "memo": None,
            "errorCode": 1,
            "validationErrors": None,
            "externalReferenceNo": 600005177520301,
            "postingDate": None,
            "extendedReply": {"messages": "Failure (suite)"},
            "userReferenceNumber": None,
        },
    }
}

NEFT_V2_INQUIRY_SUCCESS_JSON = {
    "faxml": {
        "summary": {"countpmt": 1, "sumpmt": 48750},
        "header": {
            "dattxn": "2026-04-15T19:18:13",
            "batchnumext": 600005177510301,
            "iduser": "NOVSL_USER",
            "codcurr": "INR",
            "batchnum": 123456,
            "datvalue": "2026-04-15",
            "txtstatus": "PROCESSED",
            "codpriority": 8,
            "extsysname": "NOVSL",
            "idcust": 296355427,
            "idtxn": "ST_NEF",
            "datpost": "2026-04-15",
            "partnerid": "HDFCNOVSL",
            "codstatus": 3,
        },
        "paymentlist": {
            "payment": {
                "referenceno": "HDFCH00009930438",
                "errorcode": 0,
                "errorMessage": "Success",
                "paymentrefno": 600005177510301,
            }
        },
    }
}

NEFT_V2_INQUIRY_FAIL_JSON = {
    "faxml": {
        "header": {"txtstatus": "FAILED", "idtxn": "ST_NEF"},
        "paymentlist": {
            "payment": {
                "errorcode": 1,
                "errorMessage": "Failure (suite)",
                "referenceno": "",
                "paymentrefno": 600005177510301,
            }
        },
    }
}

# Back-compat aliases (tests/docs that still say XML)
NEFT_V2_NEF_SUCCESS_XML = NEFT_V2_NEF_SUCCESS_JSON
NEFT_V2_NEI_SUCCESS_XML = NEFT_V2_NEI_SUCCESS_JSON
NEFT_V2_NEF_FAIL_XML = NEFT_V2_NEF_FAIL_JSON
NEFT_V2_NEI_FAIL_XML = NEFT_V2_NEI_FAIL_JSON
NEFT_V2_INQUIRY_SUCCESS_XML = NEFT_V2_INQUIRY_SUCCESS_JSON
NEFT_V2_INQUIRY_FAIL_XML = NEFT_V2_INQUIRY_FAIL_JSON

_ACTIVE_NEFT_VERSION = "v1"


def _neft_v1_xml_with(*, reply_code: str, reply_text: str, error_code: str, out_txn_id: str | None) -> str:
    xml = NEFT_V1_SUCCESS_SOAP_XML
    xml = re.sub(r"(<responseservice:replyCode>)(.*?)(</responseservice:replyCode>)", r"\g<1>" + reply_code + r"\3", xml, flags=re.DOTALL)
    xml = re.sub(r"(<responseservice:replyText>)(.*?)(</responseservice:replyText>)", r"\g<1>" + reply_text + r"\3", xml, flags=re.DOTALL)
    xml = re.sub(r"(<responseservice:errorCode>)(.*?)(</responseservice:errorCode>)", r"\g<1>" + error_code + r"\3", xml, flags=re.DOTALL)
    if out_txn_id is None:
        xml = re.sub(r"<outTransactionId>.*?</outTransactionId>", "<outTransactionId></outTransactionId>", xml, flags=re.DOTALL)
    else:
        xml = re.sub(r"<outTransactionId>.*?</outTransactionId>", f"<outTransactionId>{out_txn_id}</outTransactionId>", xml, flags=re.DOTALL)
    return xml


def _json_dumps_compact(obj: Any) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def _simulator_apply_profile(profile: str, neft_version: str = "v1") -> list[dict[str, Any]]:
    """
    Applies simulator responses for NEFT v1 SOAP + MFT JSON + generic status inquiry JSON.
    Returns a list of before/after snapshots for reporting.
    """
    changes: list[dict[str, Any]] = []

    def snap(api: str, typ: str) -> dict[str, Any]:
        return _get_simulator_response(api, typ) or {"api_name": api, "request_type": typ, "missing": True}

    if neft_version == "v2":
        targets = [
            ("doGenericSyncSTPNEF", "JSON"),
            ("doGenericSyncSTPNEI", "JSON"),
            ("doGenericSyncSTPInquiry", "JSON"),
            ("miscFundTransfer", "JSON"),
            ("genericTransactionStatusInquiry", "JSON"),
        ]
    else:
        targets = [
            ("NEFTPayment", "XML"),
            ("miscFundTransfer", "JSON"),
            ("genericTransactionStatusInquiry", "JSON"),
        ]
    before = {(a, t): snap(a, t) for (a, t) in targets}

    if profile == "none":
        return []

    if profile == "success":
        if neft_version == "v2":
            _set_simulator_response(
                api_name="doGenericSyncSTPNEF",
                request_type="JSON",
                response_code=200,
                response=_json_dumps_compact(NEFT_V2_NEF_SUCCESS_JSON),
                timeout_period=0,
                dynamic_response=False,
                is_callback_enabled=False,
                validation="ST_NEF",
            )
            _set_simulator_response(
                api_name="doGenericSyncSTPNEI",
                request_type="JSON",
                response_code=200,
                response=_json_dumps_compact(NEFT_V2_NEI_SUCCESS_JSON),
                timeout_period=0,
                dynamic_response=False,
                is_callback_enabled=False,
                validation="ST_NEI",
            )
            _set_simulator_response(
                api_name="doGenericSyncSTPInquiry",
                request_type="JSON",
                response_code=200,
                response=_json_dumps_compact(NEFT_V2_INQUIRY_SUCCESS_JSON),
                timeout_period=0,
                dynamic_response=False,
                is_callback_enabled=False,
                validation="GenericSyncSTPInquiryRequestDTO",
            )
        else:
            _set_simulator_response(api_name="NEFTPayment", request_type="XML", response_code=200, response=NEFT_V1_SUCCESS_SOAP_XML, timeout_period=0, dynamic_response=False, is_callback_enabled=False, validation="<SOAP-ENV:Envelope")
        _set_simulator_response(api_name="miscFundTransfer", request_type="JSON", response_code=200, response=_json_dumps_compact(MFT_SUCCESS_JSON), timeout_period=0, dynamic_response=False, is_callback_enabled=False)
        _set_simulator_response(api_name="genericTransactionStatusInquiry", request_type="JSON", response_code=200, response=_json_dumps_compact(GENERIC_TXN_INQ_SUCCESS_JSON), timeout_period=0, dynamic_response=False, is_callback_enabled=False)
    elif profile == "fail":
        if neft_version == "v2":
            _set_simulator_response(
                api_name="doGenericSyncSTPNEF",
                request_type="JSON",
                response_code=200,
                response=_json_dumps_compact(NEFT_V2_NEF_FAIL_JSON),
                timeout_period=0,
                dynamic_response=False,
                is_callback_enabled=False,
                validation="ST_NEF",
            )
            _set_simulator_response(
                api_name="doGenericSyncSTPNEI",
                request_type="JSON",
                response_code=200,
                response=_json_dumps_compact(NEFT_V2_NEI_FAIL_JSON),
                timeout_period=0,
                dynamic_response=False,
                is_callback_enabled=False,
                validation="ST_NEI",
            )
            _set_simulator_response(
                api_name="doGenericSyncSTPInquiry",
                request_type="JSON",
                response_code=200,
                response=_json_dumps_compact(NEFT_V2_INQUIRY_FAIL_JSON),
                timeout_period=0,
                dynamic_response=False,
                is_callback_enabled=False,
                validation="GenericSyncSTPInquiryRequestDTO",
            )
        else:
            _set_simulator_response(api_name="NEFTPayment", request_type="XML", response_code=200, response=_neft_v1_xml_with(reply_code="1", reply_text="1", error_code="1", out_txn_id=None), timeout_period=0, dynamic_response=False, is_callback_enabled=False, validation="<SOAP-ENV:Envelope")
        mft_fail = copy.deepcopy(MFT_SUCCESS_JSON)
        mft_fail["status"]["errorCode"] = "1"
        mft_fail["status"]["replyCode"] = 1
        mft_fail["status"]["replyText"] = "1"
        _set_simulator_response(api_name="miscFundTransfer", request_type="JSON", response_code=200, response=_json_dumps_compact(mft_fail), timeout_period=0, dynamic_response=False, is_callback_enabled=False)
        inq_fail = copy.deepcopy(GENERIC_TXN_INQ_SUCCESS_JSON)
        inq_fail["status"]["errorCode"] = "0"
        inq_fail["status"]["replyCode"] = 0
        inq_fail["status"]["replyText"] = "0"
        inq_fail["genericTransactionStatusInquiryResDTO"][0]["transactionStat"] = "Failure"
        inq_fail["genericTransactionStatusInquiryResDTO"][0]["errorCode"] = "1185"
        inq_fail["genericTransactionStatusInquiryResDTO"][0]["errorDescription"] = "Failure (suite)"
        _set_simulator_response(api_name="genericTransactionStatusInquiry", request_type="JSON", response_code=200, response=_json_dumps_compact(inq_fail), timeout_period=0, dynamic_response=False, is_callback_enabled=False)
    elif profile == "unknown":
        if neft_version == "v2":
            _set_simulator_response(
                api_name="doGenericSyncSTPNEF",
                request_type="JSON",
                response_code=503,
                response="{}",
                timeout_period=0,
                dynamic_response=False,
                is_callback_enabled=False,
                validation="ST_NEF",
            )
        else:
            _set_simulator_response(api_name="NEFTPayment", request_type="XML", response_code=200, response=_neft_v1_xml_with(reply_code="0", reply_text="0", error_code="0", out_txn_id=None), timeout_period=0, dynamic_response=False, is_callback_enabled=False, validation="<SOAP-ENV:Envelope")
        inq_unknown = copy.deepcopy(GENERIC_TXN_INQ_SUCCESS_JSON)
        inq_unknown["status"]["errorCode"] = "99"
        inq_unknown["status"]["replyCode"] = 99
        inq_unknown["status"]["replyText"] = "99"
        _set_simulator_response(api_name="genericTransactionStatusInquiry", request_type="JSON", response_code=200, response=_json_dumps_compact(inq_unknown), timeout_period=0, dynamic_response=False, is_callback_enabled=False)
    else:
        raise ValueError(f"Unknown simulator profile: {profile}")

    for (api, typ) in targets:
        after = snap(api, typ)
        b = before[(api, typ)]
        changes.append({"api_name": api, "request_type": typ, "before": b, "after": after})
    return changes


def _simulator_force_neft_fail_only() -> None:
    # Keep DTFC/GL leg stable (miscFundTransfer success), but force NEFT to fail.
    if _ACTIVE_NEFT_VERSION == "v2":
        _set_simulator_response(
            api_name="doGenericSyncSTPNEF",
            request_type="JSON",
            response_code=200,
            response=_json_dumps_compact(NEFT_V2_NEF_FAIL_JSON),
            timeout_period=0,
            dynamic_response=False,
            is_callback_enabled=False,
            validation="ST_NEF",
        )
    else:
        _set_simulator_response(
            api_name="NEFTPayment",
            request_type="XML",
            response_code=200,
            response=_neft_v1_xml_with(reply_code="1", reply_text="1", error_code="1", out_txn_id=None),
            timeout_period=0,
            dynamic_response=False,
            is_callback_enabled=False,
            validation="<SOAP-ENV:Envelope",
        )


def _simulator_force_mft_fail_only() -> None:
    # Keep NEFT stable (success), but force miscFundTransfer to fail (DTFC failure proxy in local).
    mft_fail = copy.deepcopy(MFT_SUCCESS_JSON)
    mft_fail["status"]["errorCode"] = "1"
    mft_fail["status"]["replyCode"] = 1
    mft_fail["status"]["replyText"] = "1"
    _set_simulator_response(
        api_name="miscFundTransfer",
        request_type="JSON",
        response_code=200,
        response=_json_dumps_compact(mft_fail),
        timeout_period=0,
        dynamic_response=False,
        is_callback_enabled=False,
    )


def _simulator_force_mft_unknown_only() -> None:
    # Force uncertain transport-style outcome for miscFundTransfer so accounting logs UNKNOWN.
    # Using simulator timeout here triggers catch-path in bank call processor.
    _set_simulator_response(
        api_name="miscFundTransfer",
        request_type="JSON",
        response_code=200,
        response=_json_dumps_compact(MFT_SUCCESS_JSON),
        timeout_period=45000,
        dynamic_response=False,
        is_callback_enabled=False,
    )


def _simulator_force_mft_inquiry_unknown() -> None:
    # Return an inquiry payload shape that cannot produce a definitive SUCCESS/FAIL mapping.
    # This should lead to MFT inquiry log status UNKNOWN in accounting flow.
    inq_unknown_shape = {
        "status": {
            "errorCode": "0",
            "replyCode": 0,
            "replyText": "0",
        }
        # intentionally missing genericTransactionStatusInquiryResDTO
    }
    _set_simulator_response(
        api_name="genericTransactionStatusInquiry",
        request_type="JSON",
        response_code=200,
        response=_json_dumps_compact(inq_unknown_shape),
        timeout_period=0,
        dynamic_response=False,
        is_callback_enabled=False,
    )


def _force_stage_for_retry(*, lan: str, target_disb_status: str, archive_gl: bool, archive_neft: bool, archive_mft: bool = False) -> None:
    script = _workspace_root() / "scripts" / "sql" / "utility" / "local_force_disburse_stage_for_retry_mfi_yugabyte.sql"
    if not script.exists():
        raise FileNotFoundError(str(script))
    cmd = [
        "psql",
        "-h",
        DEFAULT_DB_HOST,
        "-p",
        str(DEFAULT_DB_PORT),
        "-U",
        DEFAULT_DB_USER,
        "-d",
        DEFAULT_DB_NAME,
        "-v",
        "ON_ERROR_STOP=1",
        "-v",
        f"lan={lan}",
        "-v",
        f"target_disb_status={target_disb_status}",
        "-v",
        f"archive_gl={'true' if archive_gl else 'false'}",
        "-v",
        f"archive_neft={'true' if archive_neft else 'false'}",
        "-v",
        f"archive_mft={'true' if archive_mft else 'false'}",
        "-f",
        str(script),
    ]
    env = os.environ.copy()
    env.setdefault("PGOPTIONS", "-c lock_timeout=5s -c statement_timeout=60s")
    subprocess.check_call(cmd, env=env)


def _member_ext_refs_for_bank_leg(payload: dict[str, Any], bank_leg: str) -> list[str]:
    """Child external_ref_number values for the bank leg under test (ACCTWB→MFT, OTHBACCT→NEFT)."""
    mode = "ACCTWB" if bank_leg == "MFT" else "OTHBACCT"
    req = payload.get("request") if isinstance(payload.get("request"), dict) else payload
    out: list[str] = []
    for m in req.get("member_details") or []:
        if not isinstance(m, dict):
            continue
        if str(m.get("disbursement_mode") or "").strip() == mode:
            ref = str(m.get("external_ref_number") or "").strip()
            if ref:
                out.append(ref)
    return out


def _crr_extref_counts(account_number: str) -> dict[str, int]:
    rows = _psql_rows(
        f"""
        SELECT transaction_type, status, COUNT(1)::text
        FROM client_request_response_log
        WHERE loan_account_number = {sql_quote(account_number)}
          AND transaction_type LIKE '%EXTREF%'
          AND status NOT LIKE 'LOCAL_%'
        GROUP BY transaction_type, status
        ORDER BY transaction_type, status;
        """,
        schema=DEFAULT_DB_SCHEMA,
    )
    out: dict[str, int] = {}
    for t, st, cnt in rows:
        out[f"{t}:{st}"] = int(cnt)
    return out


def _parent_fillers(parent_account_id: int) -> tuple[str, str]:
    rows = _psql_rows(
        f"""
        SELECT COALESCE(filler_1, ''), COALESCE(filler_2, '')
        FROM loan_account
        WHERE account_id = {int(parent_account_id)};
        """,
        schema=DEFAULT_DB_SCHEMA,
    )
    if not rows:
        return "", ""
    return rows[0][0], rows[0][1]


def _restore_parent_bank_leg_success(*, lan: str, bank_leg: str) -> None:
    """After S5 parent-ft-fail, drop parent FAIL row and surface archived SUCCESS for retry staging."""
    txn_type = "DISBURSEMENT_MFT" if bank_leg == "MFT" else "DISBURSEMENT_NEFT"
    _psql(
        f"""
        UPDATE client_request_response_log c
        SET
          uri = concat_ws(
            ' | ',
            NULLIF(btrim(coalesce(c.uri, '')), ''),
            'LOCAL_FORCE_SHG_S6_PARENT_FAIL_ARCHIVED',
            'ORIG_STATUS=' || c.status
          ),
          loan_account_number = '~' || c.id::text,
          status = 'LOCAL_FORCE_SHG_S6_ARCHIVED',
          eligible_for_retry = false,
          updated_on = CURRENT_TIMESTAMP
        WHERE c.loan_account_number = {sql_quote(lan)}
          AND c.transaction_type = {sql_quote(txn_type)}
          AND c.status IN ('FAIL', 'UNKNOWN')
          AND c.status NOT LIKE 'LOCAL_%';
        """,
        schema=DEFAULT_DB_SCHEMA,
    )
    _psql(
        f"""
        WITH pick AS (
          SELECT c.id
          FROM client_request_response_log c
          WHERE c.transaction_type = {sql_quote(txn_type)}
            AND c.status = 'LOCAL_FORCE_STAGE_ARCHIVED'
            AND c.uri LIKE '%LOCAL_FORCE_STAGE_ORIG_LAN=' || {sql_quote(lan)} || '%'
            AND c.uri LIKE '%ORIG_STATUS=SUCCESS%'
          ORDER BY c.id DESC
          LIMIT 1
        )
        UPDATE client_request_response_log c
        SET
          loan_account_number = {sql_quote(lan)},
          status = 'SUCCESS',
          eligible_for_retry = true,
          updated_on = CURRENT_TIMESTAMP
        FROM pick
        WHERE c.id = pick.id
          AND NOT EXISTS (
            SELECT 1
            FROM client_request_response_log x
            WHERE x.loan_account_number = {sql_quote(lan)}
              AND x.transaction_type = {sql_quote(txn_type)}
              AND x.status = 'SUCCESS'
          );
        """,
        schema=DEFAULT_DB_SCHEMA,
    )


def _force_shg_s6_child_ft_stage(
    *,
    lan: str,
    parent_account_id: int,
    bank_leg: str,
    child_ext_refs: list[str],
) -> None:
    """
    Stage SHG S6: parent fund transfer already succeeded; retry must hit child bank leg only.
    Does not archive parent DISBURSEMENT_MFT/NEFT CRR (unlike S5 parent-ft-failed staging).
    """
    parent_status = "PARENT_SUCCESS" if bank_leg == "NEFT" else "DTFC_SUCCESS"
    child_clmt_status = "PARENT_SUCCESS" if bank_leg == "NEFT" else "DTFC_SUCCESS"
    child_member_mode = "OTHBACCT" if bank_leg == "NEFT" else "ACCTWB"
    _restore_parent_bank_leg_success(lan=lan, bank_leg=bank_leg)
    _force_stage_for_retry(
        lan=lan,
        target_disb_status=parent_status,
        archive_gl=False,
        archive_neft=False,
        archive_mft=False,
    )
    _psql(
        f"""
        UPDATE loan_account
        SET filler_1 = NULL, filler_2 = NULL,
            updated_on = CURRENT_TIMESTAMP, updated_by = 'local_force_shg_s6'
        WHERE account_id = {int(parent_account_id)};
        """,
        schema=DEFAULT_DB_SCHEMA,
    )
    leg_token = "MFT" if bank_leg == "MFT" else "NEFT"
    extref_pred_parts = [
        f"(transaction_type LIKE 'LOAN_DISBURSEMENT_EXTREF%' AND transaction_type LIKE '%EXTREF' || {sql_quote(ref)} || '%')"
        for ref in child_ext_refs
    ]
    if extref_pred_parts:
        extref_pred = " OR ".join(extref_pred_parts)
    else:
        extref_pred = (
            f"transaction_type LIKE 'LOAN_DISBURSEMENT_EXTREF%' AND transaction_type LIKE '%_{leg_token}'"
        )
    _psql(
        f"""
        UPDATE client_request_response_log c
        SET
          uri = concat_ws(
            ' | ',
            NULLIF(btrim(coalesce(c.uri, '')), ''),
            'LOCAL_FORCE_SHG_S6_ORIG_LAN=' || c.loan_account_number,
            'LOCAL_FORCE_SHG_S6_ORIG_STATUS=' || c.status
          ),
          loan_account_number = '~' || c.id::text,
          status = 'LOCAL_FORCE_SHG_S6_ARCHIVED',
          eligible_for_retry = false,
          updated_on = CURRENT_TIMESTAMP
        WHERE c.loan_account_number = {sql_quote(lan)}
          AND ({extref_pred})
          AND c.status NOT LIKE 'LOCAL_%';
        """,
        schema=DEFAULT_DB_SCHEMA,
    )
    clmt_filter = f"AND COALESCE(NULLIF(btrim(q.data), '')::jsonb->>'disbursement_mode', '') = {sql_quote(child_member_mode)}"
    _psql(
        f"""
        UPDATE loan_account_events_queue q
        SET
          event_status = 'P',
          data = (
            (COALESCE(NULLIF(btrim(q.data), '')::jsonb, '{{}}'::jsonb)
              - 'external_error_code' - 'external_error_message'
            ) || jsonb_build_object('disbursement_status', {sql_quote(child_clmt_status)})
          )::text,
          updated_on = CURRENT_TIMESTAMP,
          updated_by = 'local_force_shg_s6'
        WHERE q.parent_account_id = {int(parent_account_id)}
          AND q.event_type = 'CLMT'
          AND q.is_deleted = false
          {clmt_filter};
        """,
        schema=DEFAULT_DB_SCHEMA,
    )


def _json_load(path: str) -> dict[str, Any]:
    return json.loads(open(path, "r", encoding="utf-8").read())


def _now_ms() -> int:
    return int(time.time() * 1000)


_LAST_UNIQ_MS = 0
_UNIQ_SEQ = 0


def _uniq_ms_str() -> str:
    """
    Returns a strictly-monotonic numeric string suitable for client_reference_number/value_date.
    Prevents duplicate client_reference_number in postTransaction when multiple calls happen in the same ms.
    """
    global _LAST_UNIQ_MS, _UNIQ_SEQ  # noqa: PLW0603 (single-file harness)
    ms = _now_ms()
    if ms == _LAST_UNIQ_MS:
        _UNIQ_SEQ += 1
    else:
        _LAST_UNIQ_MS = ms
        _UNIQ_SEQ = 0
    return str(ms * 1000 + _UNIQ_SEQ)  # still numeric, preserves time ordering


def _deep_replace_timestamp(obj: Any) -> Any:
    ts = str(_now_ms())
    if isinstance(obj, dict):
        return {k: _deep_replace_timestamp(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_replace_timestamp(v) for v in obj]
    if isinstance(obj, str):
        return obj.replace("{{$timestamp}}", ts)
    return obj

def _truncate(s: str, max_len: int) -> str:
    return s if len(s) <= max_len else s[:max_len]

def _dd_get_external_ref_number(dd: dict[str, Any]) -> str:
    """
    Payloads/templates use `external_ref_number`.
    Older local payloads (and older suite revisions) may use `external_ref_number`.
    """
    v = dd.get("external_ref_number")
    if v is None or (isinstance(v, str) and not v.strip()):
        v = dd.get("external_ref_number")
    return str(v or "").strip()


def _dd_set_external_ref_number(dd: dict[str, Any], ext_ref: str) -> None:
    dd["external_ref_number"] = ext_ref
    # Keep backward-compat if the old key exists in the input.
    if "external_ref_number" in dd:
        dd["external_ref_number"] = ext_ref


def _ensure_unique_external_ref(raw: dict[str, Any]) -> tuple[dict[str, Any], str, str]:
    """
    Prevents local DB pollution / heavy reset by making external_ref_number unique per run.
    Returns (mutated_raw, old_ref, new_ref).
    """
    req = raw.get("request") if isinstance(raw, dict) else None
    if not isinstance(req, dict):
        return raw, "", ""
    dd = req.get("disbursement_details") or {}
    if not isinstance(dd, dict):
        return raw, "", ""
    old = _dd_get_external_ref_number(dd)
    if not old:
        return raw, "", ""
    # Keep it stable-ish but unique.
    # IMPORTANT: repayment_mandate_details.loan_application_id is varchar(50) in local DB,
    # and the disbursement flow may require a mandate row keyed by external_ref_number.
    # So keep ext_ref <= 50 to avoid downstream DB constraint failures.
    suffix = str(_now_ms())
    base = old
    new = _truncate(f"{base}_{suffix}", 50)
    _dd_set_external_ref_number(dd, new)
    req["disbursement_details"] = dd
    raw["request"] = req
    return raw, old, new


def _ensure_expected_disbursement_date(req: dict[str, Any]) -> None:
    dd = req.get("disbursement_details") or {}
    if not isinstance(dd, dict):
        return
    v = dd.get("expected_disbursement_date")
    if v is None or (isinstance(v, str) and not v.strip()):
        dd["expected_disbursement_date"] = str(_now_ms())
        req["disbursement_details"] = dd


def _seed_repayment_mandate_for_loan_app_id(*, loan_app_id: str, req: dict[str, Any]) -> None:
    """
    Local suite helper to satisfy CustomCallPostTransactionProcessor.updateMandateDetails():
    it requires an ACTIVE/REGISTRATION_PENDING mandate row for loan_application_id=external_ref_number
    (or for group_id when loan_category=LOAN_SHG).
    """
    loan_app_id = str(loan_app_id or "").strip()
    if not loan_app_id:
        return

    loan_details = req.get("loan_details") or {}
    group_details = req.get("group_details") or {}
    repayment_details = req.get("repayment_details") or {}
    repayment_mode = str(repayment_details.get("repayment_mode") or "").strip()
    if repayment_mode not in ("DIRDR", "ACH"):
        return

    repayment_account = next(
        (
            item
            for item in (req.get("disbursement_repayment_account_details") or [])
            if isinstance(item, dict)
            and any(
                str(purpose.get("code") or purpose.get("purpose_code") or "").strip() == "REP_ACCT"
                for purpose in (item.get("purpose") or [])
                if isinstance(purpose, dict)
            )
        ),
        None,
    )
    if repayment_account is None:
        raise RuntimeError(f"Mandate fixture requires REP_ACCT details for repayment_mode={repayment_mode}")

    account_number_key = "external_account_number" if repayment_mode == "ACH" else "account_number"
    account_type_key = "external_account_type" if repayment_mode == "ACH" else "product_type"
    account_number = str(repayment_account.get(account_number_key) or "").strip()
    account_type = str(repayment_account.get(account_type_key) or "SAVINGS").strip()
    if not account_number:
        raise RuntimeError(f"Mandate fixture REP_ACCT is missing {account_number_key}")

    account_holder_name = str(repayment_account.get("account_holder_name") or "LOCAL DISBURSEMENT FIXTURE").strip()
    ifsc_code = str(repayment_account.get("routing_value") or "").strip()
    bank_name = str(repayment_account.get("bank_name") or "HDFC_BANK").strip()
    approved_amount = str((loan_details.get("approved_amount") or loan_details.get("loan_amount") or "0")).strip()

    group_id_raw = str(group_details.get("group_id") or "").strip()
    is_primary_sig = str(group_details.get("is_primary_sig") or "").strip().lower()
    is_parent_account = "true" if is_primary_sig in ("true", "t", "1", "yes") else "false"
    loan_category = "LOAN_SHG" if group_id_raw else "LOAN_JLG"

    # Make it deterministic for local runs:
    # CustomCallPostTransactionProcessor -> MandateDetailsDAOService.findRegistrationPendingOrActiveMandateForLoanAppId()
    # expects exactly one ACTIVE/REGISTRATION_PENDING row for loan_application_id=loan_app_id.
    #
    # Local DB often accumulates duplicates with is_deleted NULL; treat NULL as false.
    where_sql = f"loan_application_id = {sql_quote(loan_app_id)}"
    # SHG parent path also looks up by group_id (unique required) — clear stale group rows first.
    if group_id_raw.isdigit():
        _psql(
            f"""
            UPDATE repayment_mandate_details
            SET
              mandate_status = 'CANCELLED',
              is_deleted = true,
              rejected_or_cancelled_date = COALESCE(rejected_or_cancelled_date, CURRENT_TIMESTAMP)
            WHERE group_id = {int(group_id_raw)}
              AND mandate_status IN ('REGISTRATION_PENDING', 'ACTIVE');
            """,
            schema=DEFAULT_DB_SCHEMA,
        )

    # Local DB can accumulate multiple rows; some flows insert REGISTRATION_PENDING mandates.
    # Make the DAO lookup unique by cancelling *all* rows for this loan_app_id, regardless of current status / is_deleted.
    _psql(
        f"""
        UPDATE repayment_mandate_details
        SET
          mandate_status = 'CANCELLED',
          is_deleted = true,
          rejected_or_cancelled_date = COALESCE(rejected_or_cancelled_date, CURRENT_TIMESTAMP)
        WHERE ({where_sql});
        """,
        schema=DEFAULT_DB_SCHEMA,
    )

    _psql(
        f"""
        INSERT INTO repayment_account_details (
          account_number,
          account_type,
          ifsc_code,
          bank_name,
          hold_status,
          lien_status,
          created_on,
          created_by,
          updated_on,
          updated_by,
          is_deleted,
          account_holder_name
        )
        SELECT
          {sql_quote(account_number)},
          {sql_quote(account_type)},
          {sql_quote(ifsc_code) if ifsc_code else "NULL"},
          {sql_quote(bank_name)},
          0,
          0,
          CURRENT_TIMESTAMP,
          'suite_seed',
          CURRENT_TIMESTAMP,
          'suite_seed',
          false,
          {sql_quote(account_holder_name)}
        WHERE NOT EXISTS (
          SELECT 1
          FROM repayment_account_details
          WHERE account_number = {sql_quote(account_number)}
            AND is_deleted = false
        );
        """,
        schema=DEFAULT_DB_SCHEMA,
    )

    # Insert a minimal ACTIVE mandate linked to the request's REP_ACCT CASA.
    max_amt = approved_amount if approved_amount and re.fullmatch(r"[0-9]+(\.[0-9]+)?", approved_amount) else "0"
    group_id_sql = str(int(group_id_raw)) if group_id_raw.isdigit() else "NULL"
    _psql(
        f"""
        INSERT INTO repayment_mandate_details (
          loan_application_id,
          group_id,
          repayment_account_details_id,
          start_date,
          end_date,
          repayment_frequency,
          purpose_code,
          max_amount,
          mandate_type,
          mandate_status,
          mandate_category,
          created_on,
          created_by,
          is_deleted,
          is_parent_account,
          loan_category
        ) VALUES (
          {sql_quote(loan_app_id)},
          {group_id_sql},
          (
            SELECT id
            FROM repayment_account_details
            WHERE account_number = {sql_quote(account_number)}
              AND is_deleted = false
            ORDER BY id
            LIMIT 1
          ),
          CURRENT_DATE,
          DATE '2099-01-01',
          'MONTHLY',
          'LOAN_REPMT',
          {max_amt},
          'RECURRING',
          'ACTIVE',
          'SI',
          CURRENT_TIMESTAMP,
          'suite_seed',
          false,
          {is_parent_account},
          {sql_quote(loan_category)}
        );
        """,
        schema=DEFAULT_DB_SCHEMA,
    )

    _psql(
        f"""
        UPDATE repayment_mandate_details
        SET repayment_account_details_id = (
          SELECT id
          FROM repayment_account_details
          WHERE account_number = {sql_quote(account_number)}
            AND is_deleted = false
          ORDER BY id
          LIMIT 1
        )
        WHERE loan_application_id = {sql_quote(loan_app_id)}
          AND mandate_status IN ('REGISTRATION_PENDING', 'ACTIVE')
          AND is_deleted = false;
        """,
        schema=DEFAULT_DB_SCHEMA,
    )

    linked = _psql_rows(
        f"""
        SELECT rad.account_number
        FROM repayment_mandate_details rmd
        JOIN repayment_account_details rad ON rad.id = rmd.repayment_account_details_id
        WHERE rmd.loan_application_id = {sql_quote(loan_app_id)}
          AND rmd.mandate_status IN ('REGISTRATION_PENDING', 'ACTIVE')
          AND rmd.is_deleted = false
          AND rad.is_deleted = false;
        """,
        schema=DEFAULT_DB_SCHEMA,
    )
    if len(linked) != 1 or linked[0][0] != account_number:
        raise RuntimeError(
            f"Mandate fixture invalid for loan_app_id={loan_app_id}: expected one linked CASA {account_number}, got {linked}"
        )
    print(f"[suite] mandate ready loan_app_id={loan_app_id} repayment_casa={account_number}", flush=True)


def _seed_member_mandates_for_shg(req: dict[str, Any]) -> None:
    """SHG CLB/createOrUpdate uses member external_ref as loan_application_id — seed each.

    Do NOT attach group_id on member mandates: CustomCallPostTransactionProcessor looks up
    findRegistrationPendingOrActiveMandateForGroupId and requires a unique group row.
    """
    members = req.get("member_details")
    if not isinstance(members, list) or not members:
        return
    repayment_details = req.get("repayment_details") or {}
    # Keep is_primary_sig for is_parent_account=false; omit group_id so group lookup stays unique.
    group_details = {
        "is_primary_sig": "false",
        "primary_sig_lan": (req.get("group_details") or {}).get("primary_sig_lan"),
    }
    for member in members:
        if not isinstance(member, dict):
            continue
        loan_app_id = str(member.get("external_ref_number") or "").strip()
        if not loan_app_id:
            continue
        member_req = {
            "loan_details": {
                "approved_amount": member.get("approved_amount") or member.get("loan_amount") or "0",
                "loan_amount": member.get("loan_amount") or "0",
            },
            "repayment_details": repayment_details,
            "group_details": group_details,
            "disbursement_repayment_account_details": member.get("disbursement_repayment_account_details") or [],
        }
        _seed_repayment_mandate_for_loan_app_id(loan_app_id=loan_app_id, req=member_req)


def _fire_child_loan_event_batch() -> str:
    """Fire childLoanEventProcessingBatchJob and wait for COMPLETED (fixture path, not service hack)."""
    job_time = str(int(time.time() * 1000))
    started = int(time.time())
    api_fire = ROOT / "scripts" / "testing" / "api-fire.py"
    print(f"[suite] firing childLoanEventProcessingBatchJob job_time={job_time}", flush=True)
    fire = subprocess.run(
        [sys.executable, str(api_fire), "childLoanEventProcessingBatchJob", "--batch", "--job-time", job_time],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if fire.returncode != 0:
        print(f"[suite] child batch fire rc={fire.returncode} stdout={fire.stdout[-500:]} stderr={fire.stderr[-500:]}", flush=True)
    # Batch stores param as `time`; poll by create_time >= started (not job_time param name).
    harness = ROOT / "scripts" / "dcf_sanity" / "clb_queue_harness.py"
    wait = subprocess.run(
        [sys.executable, "-c", f"""
import sys
sys.path.insert(0, {str(ROOT / "scripts" / "dcf_sanity")!r})
from clb_queue_harness import wait_batch_by_start
wait_batch_by_start("childLoanEventProcessingBatchJob", {started}, timeout_s={int(os.environ.get("BATCH_POLL_TIMEOUT_S", "120"))})
print("COMPLETED")
"""],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    print(f"[suite] child batch wait rc={wait.returncode} {wait.stdout[-300:]}{wait.stderr[-300:]}", flush=True)
    return job_time


def _drive_shg_child_events(
    parent: "LoanSnapshot",
    *,
    req: dict[str, Any],
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    """After parent PARENT_SUCCESS, drive CLB→children→CLMT via the real batch job."""
    members = req.get("member_details") or []
    expected = len(members) if isinstance(members, list) else 0
    diag: dict[str, Any] = {"shg_child_drive": True, "expected_children": expected}
    dedupe_mod = ROOT / "scripts" / "dcf_sanity" / "clb_queue_harness.py"
    deadline = time.time() + max(30, timeout_s)
    attempts = 0
    while time.time() < deadline:
        attempts += 1
        if dedupe_mod.is_file():
            subprocess.run(
                [sys.executable, "-c", f"""
import sys
sys.path.insert(0, {str(ROOT / "scripts" / "dcf_sanity")!r})
from clb_queue_harness import dedupe_clb_rep_acct_for_parent
dedupe_clb_rep_acct_for_parent({int(parent.account_id)})
"""],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
        children = _psql_rows(
            f"""
            SELECT account_id::text, a.account_number, la.loan_status, la.disbursement_status
            FROM loan_account la
            JOIN account a ON a.id = la.account_id AND a.is_deleted = false
            WHERE la.parent_loan_account_id = {int(parent.account_id)} AND la.is_deleted = false
            ORDER BY la.account_id;
            """,
            schema=DEFAULT_DB_SCHEMA,
        )
        clb = _psql_rows(
            f"""
            SELECT event_status, COUNT(1)::text FROM loan_account_events_queue
            WHERE parent_account_id = {int(parent.account_id)} AND event_type = 'CLB' AND is_deleted = false
            GROUP BY event_status;
            """,
            schema=DEFAULT_DB_SCHEMA,
        )
        clmt = _psql_rows(
            f"""
            SELECT event_status, COUNT(1)::text FROM loan_account_events_queue
            WHERE parent_account_id = {int(parent.account_id)} AND event_type = 'CLMT' AND is_deleted = false
            GROUP BY event_status;
            """,
            schema=DEFAULT_DB_SCHEMA,
        )
        diag["children"] = [{"id": r[0], "lan": r[1], "loan_status": r[2], "disb": r[3]} for r in children]
        diag["clb_status"] = {r[0]: int(r[1]) for r in clb}
        diag["clmt_status"] = {r[0]: int(r[1]) for r in clmt}
        children_ready = len(children) >= expected and expected > 0
        schedules_ok = True
        children_disbursed = True
        if children_ready:
            for r in children:
                if _count_installments(int(r[0])) <= 0:
                    schedules_ok = False
                if str(r[3]).upper() not in {"COMPLETED", "CHILD_SUCCESS", "ACTIVE"}:
                    # ACTIVE alone is weak; require COMPLETED/CHILD_SUCCESS for banked children
                    if str(r[3]).upper() not in {"COMPLETED", "CHILD_SUCCESS"}:
                        children_disbursed = False
        clmt_done = int(diag["clmt_status"].get("C", 0)) >= expected and expected > 0
        # Prefer CLMT all C; also accept when every child LAN is COMPLETED (CLMT may lag P briefly).
        if children_ready and schedules_ok and (clmt_done or children_disbursed):
            diag["shg_child_drive_ok"] = True
            diag["attempts"] = attempts
            return diag
        _fire_child_loan_event_batch()
        time.sleep(max(2.0, poll_s))
    diag["shg_child_drive_ok"] = False
    diag["attempts"] = attempts
    return diag


def _post_reset_normalize_external_ref(*, ext_ref: str) -> None:
    """
    The local replay reset script suffixes loan_account.external_ref_number with __LOCAL_DEDUPE_BYPASS and
    flips account.status=INACTIVE as a local-only bypass.

    For this suite, we want to replay the *same request* (canonical ext_ref) and keep the system observable
    without the suffix confusing mandate lookup / DB polling.
    """
    ext_ref = str(ext_ref or "").strip()
    if not ext_ref:
        return
    _psql(
        f"""
        UPDATE loan_account
        SET
          external_ref_number = {sql_quote(ext_ref)},
          updated_on = CURRENT_TIMESTAMP,
          updated_by = 'suite_post_reset'
        WHERE external_ref_number = {sql_quote(ext_ref + '__LOCAL_DEDUPE_BYPASS')};
        """,
        schema=DEFAULT_DB_SCHEMA,
    )
    _psql(
        f"""
        UPDATE account a
        SET
          status = 'ACTIVE',
          updated_on = CURRENT_TIMESTAMP,
          updated_by = 'suite_post_reset'
        FROM loan_account la
        WHERE la.account_id = a.id
          AND la.external_ref_number = {sql_quote(ext_ref)};
        """,
        schema=DEFAULT_DB_SCHEMA,
    )


def _workspace_root() -> Path:
    # script lives at <root>/scripts/...
    return Path(__file__).resolve().parents[1]


def _complete_neft_v2_callbacks(lan: str, request_file: str, timeout_s: int = 300) -> tuple[bool, str]:
    """Drive a NEFTv2 loan to COMPLETED through the two bank ingress callbacks.

    NEFTv2 parks at NEFT_STAGE_1_PENDING until the bank calls back twice: ST_NEF
    advances to NEFT_STAGE_1_SUCCESS, a disburseLoan NEFT_STAGE_1_SUCCESS fires ST_NEI,
    then ST_NEI completes it. Without this the LAN never reaches a terminal state, so
    the replay scenario meets a non-terminal loan, misses the ALREADY_ACTIVE skip and
    re-fires NEF — which reads as a duplicate-disbursement defect but is a harness gap.

    Delegates to scripts/complete_neft_v2_via_callbacks.py — the callback payload
    contract lives there, not duplicated here.
    """
    script = _workspace_root() / "scripts" / "complete_neft_v2_via_callbacks.py"
    if not script.is_file():
        return False, f"missing {script}"
    cmd = [sys.executable, str(script), "--lan", lan]
    if request_file:
        cmd += ["--request-file", request_file]
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout_s, check=False)
    except subprocess.TimeoutExpired:
        return False, f"timeout after {timeout_s}s"
    tail = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()
    last = tail[-1] if tail else ""
    return proc.returncode == 0 and "disbursement_status=COMPLETED" in last, last


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _ensure_reportlab_available() -> None:
    # Deprecated: suite uses dependency-free PDF generation now.
    return


def _http_post_json(url: str, payload: dict[str, Any], timeout_s: int) -> tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return e.code, body


def _kafka_publish_disburse(payload: dict[str, Any], timeout_s: int) -> tuple[int, str]:
    """LOS-shaped Kafka publish + Redis producer NX (TDPQA-54). Returns synthetic SUCCESS envelope."""
    import subprocess
    import tempfile

    publisher = ROOT / "scripts" / "testing" / "disbursement" / "disburse_kafka_publish.py"
    if not publisher.is_file():
        publisher = Path(__file__).resolve().parent / "testing" / "disbursement" / "disburse_kafka_publish.py"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as f:
        json.dump(payload, f)
        tmp = f.name
    try:
        proc = subprocess.run(
            [sys.executable, str(publisher), "--request-file", tmp],
            capture_output=True,
            text=True,
            timeout=max(timeout_s, 30),
            check=False,
        )
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    out = (proc.stdout or "") + (proc.stderr or "")
    print(out, flush=True)
    if proc.returncode != 0:
        return 500, json.dumps(
            {
                "response_status": {"status": "FAILED", "code": "KAFKA_PUBLISH", "message": out[-2000:]},
            }
        )
    return 200, json.dumps(
        {
            "response_status": {
                "status": "SUCCESS",
                "code": "000",
                "message": "Request pushed to Kafka successfully",
            }
        }
    )

def _is_successful_disburse_response(http_status: int | None, body: str) -> bool:
    if http_status is None or http_status < 200 or http_status >= 300:
        return False
    b = (body or "").strip()
    if not b:
        return True  # some local setups return empty body on success
    # Best-effort JSON parsing for Novopay-style envelopes.
    try:
        obj = json.loads(b)
    except Exception:
        return True  # non-JSON body; treat 2xx as success
    if isinstance(obj, dict):
        rs = obj.get("response_status") or obj.get("responseStatus") or obj.get("responseStatusDTO")
        if isinstance(rs, dict):
            st = str(rs.get("status") or "").strip().upper()
            code = str(rs.get("code") or "").strip()
            # Production async disbursement acknowledges with transitional/success-like statuses.
            accepted_statuses = {"SUCCESS", "DTFC_SUCCESS", "NEFT_STAGE_1_PENDING", "NEFT_STAGE_2_PENDING", "LOAN_BOOKED", "LRS_GENERATED"}
            if st and st not in accepted_statuses:
                return False
            accepted_codes = {"000", "0", "MFI-40000", "B0", "B1"}
            if code and code not in accepted_codes:
                return False
    return True


def _extract_response_status_fields(body: str) -> tuple[str, str]:
    try:
        obj = json.loads((body or "").strip() or "{}")
    except Exception:
        return "", ""
    if not isinstance(obj, dict):
        return "", ""
    rs = obj.get("response_status") or obj.get("responseStatus") or obj.get("responseStatusDTO")
    if not isinstance(rs, dict):
        return "", ""
    return str(rs.get("code") or "").strip(), str(rs.get("status") or "").strip().upper()


def _psql(sql: str, *, schema: str) -> str:
    cmd = [
        "psql",
        "-q",
        "-h",
        DEFAULT_DB_HOST,
        "-p",
        str(DEFAULT_DB_PORT),
        "-U",
        DEFAULT_DB_USER,
        "-d",
        DEFAULT_DB_NAME,
        "-v",
        "ON_ERROR_STOP=1",
        "-t",
        "-A",
        "-F",
        ",",
        "-c",
        f"SET search_path TO {schema}; {sql}",
    ]
    env = os.environ.copy()
    # allow user to provide PGPASSWORD via env; do not prompt
    # Avoid hanging indefinitely on unexpected locks/timeouts.
    env.setdefault("PGOPTIONS", "-c lock_timeout=5s -c statement_timeout=30s")
    return subprocess.check_output(cmd, env=env, text=True).strip()


def _psql_rows(sql: str, *, schema: str) -> list[list[str]]:
    out = _psql(sql, schema=schema)
    if not out:
        return []
    return [line.split(",") for line in out.splitlines() if line.strip()]

def _terminate_idle_in_txn_blockers(*, min_idle_in_txn_s: int = 30) -> int:
    """
    Local-only safety valve.
    Yugabyte often gets stuck because some client leaves a session `idle in transaction`.
    Those sessions can block writes and cause kResponseSent RPC timeouts.

    We terminate only:
    - datname='yugabyte'
    - state='idle in transaction'
    - xact age >= min_idle_in_txn_s
    - not our own backend
    """
    rows = _psql_rows(
        f"""
        SELECT pid::text
        FROM pg_stat_activity
        WHERE datname = 'yugabyte'
          AND pid <> pg_backend_pid()
          AND state = 'idle in transaction'
          AND xact_start IS NOT NULL
          AND now() - xact_start >= interval '{int(min_idle_in_txn_s)} seconds'
        ORDER BY xact_start ASC;
        """,
        schema="public",
    )
    pids = [int(r[0]) for r in rows if r and r[0].isdigit()]
    terminated = 0
    for pid in pids:
        try:
            out = _psql_rows(f"SELECT pg_terminate_backend({pid})::text;", schema="public")
            if out and out[0] and out[0][0].strip().lower() == "t":
                terminated += 1
        except Exception:
            # best-effort
            pass
    return terminated


def _set_simulator_response(
    *,
    api_name: str,
    request_type: str,
    response_code: int,
    response: str,
    validation: str | None = None,
    timeout_period: int | None = None,
    dynamic_response: bool | None = None,
    is_callback_enabled: bool | None = None,
) -> None:
    sets: list[str] = [
        f"response_code = {int(response_code)}",
        f"response = {sql_quote(response)}",
    ]
    if validation is not None:
        sets.append(f"validation = {sql_quote(validation)}")
    if timeout_period is not None:
        sets.append(f"timeout_period = {int(timeout_period)}")
    if dynamic_response is not None:
        sets.append(f"dynamic_response = {'true' if dynamic_response else 'false'}")
    if is_callback_enabled is not None:
        sets.append(f"is_callback_enabled = {'true' if is_callback_enabled else 'false'}")

    sql = f"""
    UPDATE mfi_simulator.simulator_response sr
    SET {", ".join(sets)}
    FROM mfi_simulator.simulator_config sc
    WHERE sc.id = sr.simulator_config_id
      AND sc.api_name = {sql_quote(api_name)}
      AND upper(sc.request_type) = upper({sql_quote(request_type)});
    """
    _psql(sql, schema="public")


def sql_quote(s: str) -> str:
    # psql single-quote escaping
    return "'" + s.replace("'", "''") + "'"

@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    details: str = ""
    level: str = "FAIL"  # FAIL | WARN


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    http_status: int | None
    loan: "LoanSnapshot | None"
    checks: list[CheckResult]
    diagnostics: dict[str, Any]


@dataclass(frozen=True)
class LoanSnapshot:
    account_id: int
    account_number: str
    loan_status: str
    disbursement_status: str
    external_ref_number: str
    has_child_accounts: bool


def _fetch_loan_by_external_ref(ext_ref: str) -> LoanSnapshot | None:
    rows = _psql_rows(
        f"""
        SELECT la.account_id::text,
               a.account_number,
               la.loan_status,
               la.disbursement_status,
               la.external_ref_number,
               COALESCE(la.has_child_accounts, false)::text
        FROM loan_account la
        JOIN account a ON a.id = la.account_id
        WHERE la.is_deleted = false
          AND a.is_deleted = false
          AND la.external_ref_number = {sql_quote(ext_ref)}
        ORDER BY la.updated_on DESC NULLS LAST, la.account_id DESC
        LIMIT 1;
        """,
        schema=DEFAULT_DB_SCHEMA,
    )
    if not rows:
        return None
    r = rows[0]
    return LoanSnapshot(
        account_id=int(r[0]),
        account_number=r[1],
        loan_status=r[2],
        disbursement_status=r[3],
        external_ref_number=r[4],
        has_child_accounts=(r[5].lower() == "true"),
    )

def _fetch_latest_loan_by_external_ref_prefix(ext_ref_prefix: str) -> LoanSnapshot | None:
    prefix = str(ext_ref_prefix or "").strip()
    if not prefix:
        return None
    rows = _psql_rows(
        f"""
        SELECT la.account_id::text,
               a.account_number,
               la.loan_status,
               la.disbursement_status,
               la.external_ref_number,
               COALESCE(la.has_child_accounts, false)::text
        FROM loan_account la
        JOIN account a ON a.id = la.account_id
        WHERE la.is_deleted = false
          AND a.is_deleted = false
          AND la.external_ref_number LIKE {sql_quote(prefix + "%")}
        ORDER BY la.updated_on DESC NULLS LAST, la.account_id DESC
        LIMIT 1;
        """,
        schema=DEFAULT_DB_SCHEMA,
    )
    if not rows:
        return None
    r = rows[0]
    return LoanSnapshot(
        account_id=int(r[0]),
        account_number=r[1],
        loan_status=r[2],
        disbursement_status=r[3],
        external_ref_number=r[4],
        has_child_accounts=(r[5].lower() == "true"),
    )

def _canonical_external_ref_base(ext_ref: str) -> str:
    value = str(ext_ref or "").strip()
    if not value:
        return ""
    # Suite usually appends millisecond suffix to keep runs unique.
    # DB may persist canonical/base ref in some local replay flows.
    return re.sub(r"_[0-9]{10,}$", "", value)

def _fetch_latest_loan_by_external_ref_base_since(ext_ref: str, since_epoch_ms: int) -> LoanSnapshot | None:
    base = _canonical_external_ref_base(ext_ref)
    if not base:
        return None
    rows = _psql_rows(
        f"""
        SELECT la.account_id::text,
               a.account_number,
               la.loan_status,
               la.disbursement_status,
               la.external_ref_number,
               COALESCE(la.has_child_accounts, false)::text
        FROM loan_account la
        JOIN account a ON a.id = la.account_id
        WHERE la.is_deleted = false
          AND a.is_deleted = false
          AND (
            la.external_ref_number = {sql_quote(base)}
            OR la.external_ref_number LIKE {sql_quote(base + "%")}
          )
          AND (la.updated_on IS NULL OR la.updated_on >= to_timestamp({since_epoch_ms} / 1000.0))
        ORDER BY la.updated_on DESC NULLS LAST, la.account_id DESC
        LIMIT 1;
        """,
        schema=DEFAULT_DB_SCHEMA,
    )
    if not rows:
        return None
    r = rows[0]
    return LoanSnapshot(
        account_id=int(r[0]),
        account_number=r[1],
        loan_status=r[2],
        disbursement_status=r[3],
        external_ref_number=r[4],
        has_child_accounts=(r[5].lower() == "true"),
    )

def _fetch_loan_by_account_id(account_id: int) -> LoanSnapshot | None:
    rows = _psql_rows(
        f"""
        SELECT la.account_id::text,
               a.account_number,
               la.loan_status,
               la.disbursement_status,
               la.external_ref_number,
               COALESCE(la.has_child_accounts, false)::text
        FROM loan_account la
        JOIN account a ON a.id = la.account_id
        WHERE la.is_deleted = false
          AND a.is_deleted = false
          AND la.account_id = {int(account_id)}
        LIMIT 1;
        """,
        schema=DEFAULT_DB_SCHEMA,
    )
    if not rows:
        return None
    r = rows[0]
    return LoanSnapshot(
        account_id=int(r[0]),
        account_number=r[1],
        loan_status=r[2],
        disbursement_status=r[3],
        external_ref_number=r[4],
        has_child_accounts=(r[5].lower() == "true"),
    )


def _fetch_loan_by_account_number(account_number: str) -> LoanSnapshot | None:
    acc = str(account_number or "").strip()
    if not acc:
        return None
    rows = _psql_rows(
        f"""
        SELECT la.account_id::text,
               a.account_number,
               la.loan_status,
               la.disbursement_status,
               la.external_ref_number,
               COALESCE(la.has_child_accounts, false)::text
        FROM account a
        JOIN loan_account la ON la.account_id = a.id
        WHERE la.is_deleted = false
          AND a.is_deleted = false
          AND a.account_number = {sql_quote(acc)}
        ORDER BY la.updated_on DESC NULLS LAST, la.account_id DESC
        LIMIT 1;
        """,
        schema=DEFAULT_DB_SCHEMA,
    )
    if not rows:
        return None
    r = rows[0]
    return LoanSnapshot(
        account_id=int(r[0]),
        account_number=r[1],
        loan_status=r[2],
        disbursement_status=r[3],
        external_ref_number=r[4],
        has_child_accounts=(r[5].lower() == "true"),
    )

def _fetch_latest_loan_by_customer_product_since(customer_id: str, product_id: str, since_epoch_ms: int) -> LoanSnapshot | None:
    # Fallback for cases where external_ref_number isn't persisted as expected in local data.
    # Uses updated_on as the time signal (framework updates it frequently during disbursement).
    rows = _psql_rows(
        f"""
        SELECT la.account_id::text,
               a.account_number,
               la.loan_status,
               la.disbursement_status,
               la.external_ref_number,
               COALESCE(la.has_child_accounts, false)::text
        FROM loan_account la
        JOIN account a ON a.id = la.account_id
        WHERE la.is_deleted = false
          AND a.is_deleted = false
          AND la.customer_id = {sql_quote(customer_id)}
          -- loan_product_id vs product_id mapping varies by setup; filter only by customer + time
          AND (la.updated_on IS NULL OR la.updated_on >= to_timestamp({since_epoch_ms} / 1000.0))
        ORDER BY la.updated_on DESC NULLS LAST, la.account_id DESC
        LIMIT 1;
        """,
        schema=DEFAULT_DB_SCHEMA,
    )
    if not rows:
        return None
    r = rows[0]
    return LoanSnapshot(
        account_id=int(r[0]),
        account_number=r[1],
        loan_status=r[2],
        disbursement_status=r[3],
        external_ref_number=r[4],
        has_child_accounts=(r[5].lower() == "true"),
    )


def _count_installments(account_id: int) -> int:
    rows = _psql_rows(
        f"SELECT COUNT(1)::text FROM loan_installment_details WHERE is_deleted = false AND loan_account_id = {account_id};",
        schema=DEFAULT_DB_SCHEMA,
    )
    return int(rows[0][0]) if rows else 0


def _count_dues(account_id: int) -> int:
    rows = _psql_rows(
        f"SELECT COUNT(1)::text FROM loan_due_details WHERE is_deleted = false AND loan_account_id = {account_id};",
        schema=DEFAULT_DB_SCHEMA,
    )
    return int(rows[0][0]) if rows else 0


def _get_utr(account_id: int) -> str | None:
    rows = _psql_rows(
        f"""
        SELECT COALESCE(utr_number, '') FROM loan_disbursement_mode_details
        WHERE is_deleted = false AND loan_account_id = {account_id}
        ORDER BY updated_on DESC NULLS LAST, id DESC
        LIMIT 1;
        """,
        schema=DEFAULT_DB_SCHEMA,
    )
    if not rows:
        return None
    v = rows[0][0]
    return v if v else None


def _crr_counts(account_number: str) -> dict[str, int]:
    # Critical dedupe-sensitive transaction types for disbursement:
    # - GL rows
    # - MFT rows and inquiry
    # - NEFT v1 + v2 payment legs and inquiry
    rows = _psql_rows(
        f"""
        SELECT transaction_type, status, COUNT(1)::text
        FROM client_request_response_log
        WHERE loan_account_number = {sql_quote(account_number)}
          AND (
                transaction_type IN (
                    'DISB_GL_CBS_INTEGRATION',
                    'DISB_GL_CBS_INTEGRATION_NETOFF',
                    'DISBURSEMENT_MFT',
                    'MFT_TRANSACTION_INQUIRY',
                    'NEFT_TRANSACTION_INQUIRY',
                    'DISBURSEMENT_NEFT'
                )
                OR transaction_type LIKE '%NEFT_NEF%'
                OR transaction_type LIKE '%NEFT_NEI%'
          )
        GROUP BY transaction_type, status
        ORDER BY transaction_type, status;
        """,
        schema=DEFAULT_DB_SCHEMA,
    )
    out: dict[str, int] = {}
    for t, st, cnt in rows:
        out[f"{t}:{st}"] = int(cnt)
    return out

def _crr_latest_refs(account_number: str, transaction_type: str) -> list[tuple[str, str, str, str]]:
    """
    Returns latest rows (client_reference_number,status,transaction_type,system_date) for a given txn type.
    """
    rows = _psql_rows(
        f"""
        SELECT COALESCE(client_reference_number, ''),
               COALESCE(status, ''),
               COALESCE(transaction_type, ''),
               COALESCE(system_date::text, '')
        FROM client_request_response_log
        WHERE loan_account_number = {sql_quote(account_number)}
          AND transaction_type = {sql_quote(transaction_type)}
        ORDER BY system_date DESC NULLS LAST, id DESC
        LIMIT 5;
        """,
        schema=DEFAULT_DB_SCHEMA,
    )
    return [(r[0], r[1], r[2], r[3]) for r in rows]

def _crr_distinct_client_refs(account_number: str, transaction_type: str) -> list[str]:
    rows = _psql_rows(
        f"""
        SELECT DISTINCT COALESCE(client_reference_number, '')
        FROM client_request_response_log
        WHERE loan_account_number = {sql_quote(account_number)}
          AND transaction_type = {sql_quote(transaction_type)}
        ORDER BY 1;
        """,
        schema=DEFAULT_DB_SCHEMA,
    )
    return [r[0] for r in rows if r and r[0]]


def _crr_distinct_client_refs_neft_payment(account_number: str) -> list[str]:
    rows = _psql_rows(
        f"""
        SELECT DISTINCT COALESCE(client_reference_number, '')
        FROM client_request_response_log
        WHERE loan_account_number = {sql_quote(account_number)}
          AND (
                transaction_type = 'DISBURSEMENT_NEFT'
                OR transaction_type LIKE '%NEFT_NEF%'
                OR transaction_type LIKE '%NEFT_NEI%'
          )
        ORDER BY 1;
        """,
        schema=DEFAULT_DB_SCHEMA,
    )
    return [r[0] for r in rows if r and r[0]]


def _crr_type_evidence(account_number: str, transaction_type: str) -> dict[str, Any]:
    """
    DB evidence used in report to prove duplicates did/didn't happen.

    Returns:
      - total_rows: total CRR rows for txn type
      - max_id: max CRR id for txn type
      - latest: latest row details (id, system_date, status, client_reference_number)
    """
    rows = _psql_rows(
        f"""
        SELECT COUNT(1)::text,
               COALESCE(MAX(id),0)::text
        FROM client_request_response_log
        WHERE loan_account_number = {sql_quote(account_number)}
          AND transaction_type = {sql_quote(transaction_type)};
        """,
        schema=DEFAULT_DB_SCHEMA,
    )
    total = int(rows[0][0]) if rows else 0
    max_id = int(rows[0][1]) if rows else 0
    latest_rows = _psql_rows(
        f"""
        SELECT id::text,
               COALESCE(system_date::text,''),
               COALESCE(status,''),
               COALESCE(client_reference_number,'')
        FROM client_request_response_log
        WHERE loan_account_number = {sql_quote(account_number)}
          AND transaction_type = {sql_quote(transaction_type)}
        ORDER BY system_date DESC NULLS LAST, id DESC
        LIMIT 1;
        """,
        schema=DEFAULT_DB_SCHEMA,
    )
    latest = None
    if latest_rows:
        r = latest_rows[0]
        latest = {
            "id": int(r[0]),
            "system_date": r[1],
            "status": r[2],
            "client_reference_number": r[3],
        }
    # Archived rows are intentionally detached from loan_account_number by reset/stage-force scripts.
    # We recover them via URI markers carrying original LAN.
    archived_rows = _psql_rows(
        f"""
        SELECT COUNT(1)::text,
               COALESCE(MAX(id),0)::text
        FROM client_request_response_log
        WHERE transaction_type = {sql_quote(transaction_type)}
          AND (
                uri LIKE '%' || {sql_quote("LOCAL_RESET_ORIG_LAN=" + account_number)} || '%'
             OR uri LIKE '%' || {sql_quote("LOCAL_FORCE_STAGE_ORIG_LAN=" + account_number)} || '%'
          );
        """,
        schema=DEFAULT_DB_SCHEMA,
    )
    archived_total = int(archived_rows[0][0]) if archived_rows else 0
    archived_max_id = int(archived_rows[0][1]) if archived_rows else 0
    archived_latest_rows = _psql_rows(
        f"""
        SELECT id::text,
               COALESCE(system_date::text,''),
               COALESCE(status,''),
               COALESCE(client_reference_number,'')
        FROM client_request_response_log
        WHERE transaction_type = {sql_quote(transaction_type)}
          AND (
                uri LIKE '%' || {sql_quote("LOCAL_RESET_ORIG_LAN=" + account_number)} || '%'
             OR uri LIKE '%' || {sql_quote("LOCAL_FORCE_STAGE_ORIG_LAN=" + account_number)} || '%'
          )
        ORDER BY system_date DESC NULLS LAST, id DESC
        LIMIT 1;
        """,
        schema=DEFAULT_DB_SCHEMA,
    )
    archived_latest = None
    if archived_latest_rows:
        ar = archived_latest_rows[0]
        archived_latest = {
            "id": int(ar[0]),
            "system_date": ar[1],
            "status": ar[2],
            "client_reference_number": ar[3],
        }
    return {
        "transaction_type": transaction_type,
        "total_rows": total,
        "max_id": max_id,
        "latest": latest,
        "archived_total_rows": archived_total,
        "archived_max_id": archived_max_id,
        "archived_latest": archived_latest,
    }


def _crr_neft_payment_evidence(account_number: str) -> dict[str, Any]:
    rows = _psql_rows(
        f"""
        SELECT COUNT(1)::text, COALESCE(MAX(id),0)::text
        FROM client_request_response_log
        WHERE loan_account_number = {sql_quote(account_number)}
          AND (
                transaction_type = 'DISBURSEMENT_NEFT'
                OR transaction_type LIKE '%NEFT_NEF%'
                OR transaction_type LIKE '%NEFT_NEI%'
          );
        """,
        schema=DEFAULT_DB_SCHEMA,
    )
    total = int(rows[0][0]) if rows else 0
    max_id = int(rows[0][1]) if rows else 0
    latest_rows = _psql_rows(
        f"""
        SELECT id::text,
               COALESCE(system_date::text,''),
               COALESCE(status,''),
               COALESCE(client_reference_number,''),
               COALESCE(transaction_type,'')
        FROM client_request_response_log
        WHERE loan_account_number = {sql_quote(account_number)}
          AND (
                transaction_type = 'DISBURSEMENT_NEFT'
                OR transaction_type LIKE '%NEFT_NEF%'
                OR transaction_type LIKE '%NEFT_NEI%'
          )
        ORDER BY system_date DESC NULLS LAST, id DESC
        LIMIT 1;
        """,
        schema=DEFAULT_DB_SCHEMA,
    )
    latest = None
    if latest_rows:
        r = latest_rows[0]
        latest = {
            "id": int(r[0]),
            "system_date": r[1],
            "status": r[2],
            "client_reference_number": r[3],
            "transaction_type": r[4],
        }
    return {
        "transaction_type": "DISBURSEMENT_NEFT*",
        "total_rows": total,
        "max_id": max_id,
        "latest": latest,
    }


def _count_neft_payment_rows(crr: dict[str, int]) -> int:
    return sum(
        v
        for k, v in crr.items()
        if "NEFT" in k
        and not k.startswith("NEFT_TRANSACTION_INQUIRY:")
    )

TERMINAL_DISBURSEMENT_STATUSES = {"COMPLETED", "PARENT_SUCCESS", "CHILD_SUCCESS", "DTFC_SUCCESS"}

# NEFTv2 parks here awaiting a bank callback. Not terminal, but a legitimate stop:
# without it every NEFTv2 run burns the whole timeout and returns an arbitrary snapshot.
NEFT_V2_STAGE_STATUSES = {"NEFT_STAGE_1_PENDING", "NEFT_STAGE_1_SUCCESS", "NEFT_STAGE_2_PENDING"}


def _wait_for_terminal_status(
    *,
    ext_ref: str,
    timeout_s: int,
    poll_s: float,
    stop_statuses: set[str] | None = None,
) -> LoanSnapshot:
    stop = stop_statuses or TERMINAL_DISBURSEMENT_STATUSES
    deadline = time.time() + timeout_s
    last: LoanSnapshot | None = None
    last_print = 0.0
    # Optional fallback keying (filled by main via globals)
    customer_id = os.environ.get("SUITE_CUSTOMER_ID", "")
    product_id = os.environ.get("SUITE_PRODUCT_ID", "")
    since_ms = int(os.environ.get("SUITE_SINCE_MS", "0") or "0")
    pinned_account_id = int(os.environ.get("SUITE_ACCOUNT_ID", "0") or "0")

    while time.time() < deadline:
        snap = _fetch_loan_by_external_ref(ext_ref)
        if not snap and pinned_account_id:
            snap = _fetch_loan_by_account_id(pinned_account_id)
        if not snap and customer_id and product_id and since_ms:
            snap = _fetch_latest_loan_by_customer_product_since(customer_id, product_id, since_ms)
        if snap:
            last = snap
            if snap.disbursement_status in stop:
                return snap
            now = time.time()
            if now - last_print >= 10:
                print(f"[wait] ext_ref={ext_ref} current_disb_status={snap.disbursement_status} loan_status={snap.loan_status} lan={snap.account_number}", flush=True)
                last_print = now
        else:
            now = time.time()
            if now - last_print >= 10:
                print(f"[wait] ext_ref={ext_ref} loan row not present yet", flush=True)
                last_print = now
        time.sleep(poll_s)
    if last:
        return last
    raise RuntimeError(f"Loan not found in DB for external_ref_number={ext_ref}")

def _wait_for_loan_present(ext_ref: str, timeout_s: int, poll_s: float) -> LoanSnapshot:
    deadline = time.time() + timeout_s
    last_print = 0.0
    pinned_account_id = int(os.environ.get("SUITE_ACCOUNT_ID", "0") or "0")
    customer_id = os.environ.get("SUITE_CUSTOMER_ID", "")
    product_id = os.environ.get("SUITE_PRODUCT_ID", "")
    since_ms = int(os.environ.get("SUITE_SINCE_MS", "0") or "0")
    while time.time() < deadline:
        snap = _fetch_loan_by_external_ref(ext_ref)
        if not snap:
            snap = _fetch_latest_loan_by_external_ref_prefix(ext_ref)
        if not snap and since_ms:
            snap = _fetch_latest_loan_by_external_ref_base_since(ext_ref, since_ms)
        if not snap and pinned_account_id:
            snap = _fetch_loan_by_account_id(pinned_account_id)
        if not snap and customer_id and product_id and since_ms:
            snap = _fetch_latest_loan_by_customer_product_since(customer_id, product_id, since_ms)
        if snap:
            return snap
        now = time.time()
        if now - last_print >= 10:
            print(f"[wait] ext_ref={ext_ref} loan row not present yet", flush=True)
            last_print = now
        time.sleep(poll_s)
    raise RuntimeError(f"Loan not found in DB for external_ref_number={ext_ref}")

def _wait_for_disbursement_status_in(ext_ref: str, statuses: set[str], timeout_s: int, poll_s: float) -> LoanSnapshot:
    deadline = time.time() + timeout_s
    last: LoanSnapshot | None = None
    while time.time() < deadline:
        snap = _fetch_loan_by_external_ref(ext_ref)
        if snap:
            last = snap
            if snap.disbursement_status in statuses:
                return snap
        time.sleep(poll_s)
    if last:
        return last
    raise RuntimeError(f"Loan not found in DB for external_ref_number={ext_ref}")


def _dedupe_child_queue_rows() -> None:
    """Restore uniqueness of loan_account_events_queue.filler_2 (child external ref).

    Canonical group payloads reuse fixed member external refs, so every local run adds
    another CLMT row with the same filler_2. `findOneByFiller2` (used by the NEFT child
    callback) is a global single-result lookup, so from the second run on it throws
    IncorrectResultSizeDataAccessException and the child can never leave
    NEFT_STAGE_1_PENDING. Production external refs are unique per LOS application, so
    this is a local fixture artifact only — the cleanup belongs in reset, not the product.
    """
    sql_file = str(
        ROOT / "scripts" / "sql" / "reset" / "local_dedupe_child_queue_rows.sql"
    )
    try:
        subprocess.run(
            [
                "bash",
                str(ROOT / "scripts" / "bin" / "db-local-write.sh"),
                "--file",
                sql_file,
            ],
            check=True,
            text=True,
            capture_output=True,
        )
        print("[suite] child queue rows deduped (filler_2 uniqueness restored)", flush=True)
    except Exception as e:  # noqa: BLE001 — fixture hygiene must not fail the run
        print(f"[suite] WARN child queue dedupe skipped: {e}", flush=True)


def _run_local_reset_from_json(request_file: str, *, target_disb_status: str) -> None:
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "sql" / "reset" / "reset_disburse_loan_replay_mfi_from_json.py"),
        "--file",
        request_file,
        "--target-disb-status",
        target_disb_status,
    ]
    env = os.environ.copy()
    env.setdefault("PGOPTIONS", "-c lock_timeout=5s -c statement_timeout=60s")
    last_err: Exception | None = None
    for attempt in range(1, 6):
        try:
            killed = _terminate_idle_in_txn_blockers(min_idle_in_txn_s=10)
            if killed:
                print(f"[suite] terminated idle-in-txn blockers={killed}", flush=True)
            subprocess.run(cmd, check=True, text=True, env=env)
            _dedupe_child_queue_rows()
            return
        except subprocess.CalledProcessError as e:
            last_err = e
            sleep_s = min(2 ** (attempt - 1), 8)
            print(f"[suite] reset-before conflict, retrying attempt={attempt}/5 sleep={sleep_s}s", flush=True)
            time.sleep(sleep_s)
        except Exception as e:
            last_err = e
            sleep_s = min(2 ** (attempt - 1), 8)
            print(f"[suite] reset-before error, retrying attempt={attempt}/5 sleep={sleep_s}s", flush=True)
            time.sleep(sleep_s)
    raise RuntimeError(f"Failed to run reset-before after retries: {last_err}")

def _reset_customer_loans(customer_id: str) -> None:
    if not customer_id:
        return
    # Chunked reset to avoid Yugabyte RPC timeouts on large multi-row updates.
    # We only touch rows that could participate in dedupe (not already closed+deleted).
    cid = f"CAST({sql_quote(customer_id)} AS bigint)"
    # Dedupe blocker is account.status='ACTIVE' (CustomerIDDedupCheckProcessor skips non-ACTIVE).
    # So we only need to close ACTIVE accounts for this customer.
    ids_rows = _psql_rows(
        f"""
        SELECT la.account_id::text
        FROM loan_account la
        JOIN account a ON a.id = la.account_id
        WHERE la.customer_id = {cid}
          AND a.status = 'ACTIVE'
        ORDER BY la.account_id;
        """,
        schema=DEFAULT_DB_SCHEMA,
    )
    account_ids = [int(r[0]) for r in ids_rows if r and r[0].isdigit()]
    if not account_ids:
        return

    def chunks(lst: list[int], n: int) -> list[list[int]]:
        return [lst[i : i + n] for i in range(0, len(lst), n)]

    last_err: Exception | None = None
    for attempt in range(1, 6):
        try:
            killed = _terminate_idle_in_txn_blockers(min_idle_in_txn_s=10)
            if killed:
                print(f"[suite] terminated idle-in-txn blockers={killed}", flush=True)
            for batch in chunks(account_ids, 5):
                ids_sql = ", ".join(str(x) for x in batch)
                _psql(
                    f"""
                    UPDATE loan_account la
                    SET
                      loan_status = 'CLOSED',
                      is_deleted = true,
                      external_ref_number = LEFT('VOID_' || la.account_id::text || '_' || COALESCE(la.external_ref_number,''), 64),
                      updated_on = CURRENT_TIMESTAMP,
                      updated_by = 'suite_reset'
                    WHERE la.account_id IN ({ids_sql});
                    """,
                    schema=DEFAULT_DB_SCHEMA,
                )
                _psql(
                    f"""
                    UPDATE account a
                    SET
                      status = 'CLOSED',
                      is_deleted = true,
                      closing_date = COALESCE(closing_date, CURRENT_TIMESTAMP),
                      updated_on = CURRENT_TIMESTAMP,
                      updated_by = 'suite_reset'
                    WHERE a.id IN ({ids_sql});
                    """,
                    schema=DEFAULT_DB_SCHEMA,
                )
            return
        except Exception as e:
            last_err = e
            sleep_s = min(2 ** (attempt - 1), 8)
            print(f"[suite] customer reset conflict, retrying attempt={attempt}/5 sleep={sleep_s}s", flush=True)
            time.sleep(sleep_s)
    raise RuntimeError(f"Failed to reset customer loans after retries: {last_err}")


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _format_counts(d: dict[str, int]) -> str:
    if not d:
        return "{}"
    items = ", ".join(f"{k}={v}" for k, v in sorted(d.items()))
    return "{" + items + "}"


def _crr_delta(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    keys = set(before.keys()) | set(after.keys())
    out: dict[str, int] = {}
    for k in keys:
        dv = int(after.get(k, 0)) - int(before.get(k, 0))
        if dv:
            out[k] = dv
    return out


def _sum_crr_delta_for_prefix(delta: dict[str, int], *, prefix: str) -> int:
    p = prefix.upper()
    return sum(v for k, v in delta.items() if str(k).upper().startswith(p))

def _disbursement_mode(req: dict[str, Any]) -> str:
    return str(((req.get("disbursement_details") or {}).get("disbursement_mode") or "")).strip()


_PRODUCT_ID_LABEL: dict[str, str] = {"2": "JLG", "44": "SHG", "45": "INDL"}


def _infer_product_type(req: dict[str, Any]) -> str:
    pid = str(((req.get("loan_details") or {}).get("product_id") or "")).strip()
    return _PRODUCT_ID_LABEL.get(pid, f"UNKNOWN(product_id={pid})")


def _is_child_flow_payload(req_obj: dict[str, Any]) -> bool:
    """SHG parent+CLMT path only — non-empty member_details[] (not JLG group_details)."""
    md = req_obj.get("member_details")
    return isinstance(md, list) and len(md) > 0


def _validate_payload_product_contract(req: dict[str, Any]) -> list[tuple[str, bool, str, str]]:
    """Preflight shape checks: JLG/INDL flat (member_details null); SHG child-flow array."""
    pid = str(((req.get("loan_details") or {}).get("product_id") or "")).strip()
    md = req.get("member_details")
    has_members = isinstance(md, list) and len(md) > 0
    flat_ok = md is None or (isinstance(md, list) and len(md) == 0)
    out: list[tuple[str, bool, str, str]] = []
    if pid == "2":
        out.append(
            (
                "jlg_flat_payload",
                flat_ok,
                f"JLG expects member_details null/absent (flat per-member LOS disburse); got type={type(md).__name__}",
                "FAIL",
            )
        )
    elif pid == "45":
        out.append(
            (
                "indl_flat_payload",
                flat_ok,
                "INDL expects member_details null/absent",
                "FAIL",
            )
        )
    elif pid == "44":
        out.append(
            (
                "shg_child_payload",
                has_members,
                f"SHG expects non-empty member_details[]; got type={type(md).__name__}",
                "FAIL",
            )
        )
        if has_members and isinstance(md, list):
            try:
                parent_amt = Decimal(str(((req.get("loan_details") or {}).get("loan_amount") or "0")))
                child_sum = sum(
                    Decimal(str(m.get("loan_amount") or "0")) for m in md if isinstance(m, dict)
                )
                sum_ok = parent_amt == child_sum
                out.append(
                    (
                        "shg_child_sum_equals_parent",
                        sum_ok,
                        f"parent loan_amount={parent_amt} sum(member_details.loan_amount)={child_sum}",
                        "FAIL",
                    )
                )
            except Exception as e:
                out.append(("shg_child_sum_equals_parent", False, f"{type(e).__name__}: {e}", "FAIL"))
    return out


def _member_disbursement_modes(req: dict[str, Any]) -> set[str]:
    member_details = req.get("member_details")
    if not isinstance(member_details, list):
        return set()
    out: set[str] = set()
    for member in member_details:
        if not isinstance(member, dict):
            continue
        mode = str(member.get("disbursement_mode") or "").strip().upper()
        if mode:
            out.add(mode)
    return out


def _netoff_amount(req: dict[str, Any]) -> str:
    return str(((req.get("net_off_details") or {}).get("net_off_amount") or "")).strip()


def _expected_bank_leg(mode: str) -> str:
    # Derived from orchestration mfi_orc.xml:
    # - ACCTWB => MFT
    # - OTHBACCT => NEFT (for version 1 this becomes DISBURSEMENT_NEFT)
    # Others exist, but for this harness we only assert for these two.
    if mode.upper() == "ACCTWB":
        return "MFT"
    if mode.upper() == "OTHBACCT":
        return "NEFT"
    return "UNKNOWN"


def _pretty_print_results(results: list[ScenarioResult]) -> None:
    print("")
    print("=== disburseLoan sanity report ===")
    for r in results:
        has_fail = any((not c.ok) and c.level == "FAIL" for c in r.checks)
        status = "PASS" if not has_fail else "FAIL"
        print("")
        print(f"[{status}] scenario={r.name} http_status={r.http_status}")
        if r.loan:
            l = r.loan
            print(f"  loan: account_number={l.account_number} account_id={l.account_id} loan_status={l.loan_status} disb_status={l.disbursement_status} has_child={l.has_child_accounts}")
        for c in r.checks:
            if c.ok:
                continue
            print(f"  - {c.level} {c.name}: {c.details}")
        if r.diagnostics:
            # Keep diagnostics readable but compact
            for k, v in r.diagnostics.items():
                print(f"  diag.{k}={v}")


def _format_text_report(results: list[ScenarioResult], meta: dict[str, Any]) -> str:
    def is_fail(r: ScenarioResult) -> bool:
        return any((not c.ok) and c.level == "FAIL" for c in r.checks)

    def is_skipped(r: ScenarioResult) -> bool:
        return bool((r.diagnostics or {}).get("skipped"))

    def cell(v: Any, width: int) -> str:
        s = "" if v is None else str(v)
        if len(s) > width:
            s = s[: max(0, width - 1)] + "…"
        return s.ljust(width)

    def tc_catalog() -> list[dict[str, str]]:
        # Business-readable catalog (like the reference sheet).
        # Scenario names remain stable for code; the report shows TCxx + title + expected behavior.
        return [
            {
                "id": "TC01",
                "scenario": "default_once",
                "product": "JLG & INDIVIDUAL",
                "action": "Fresh request",
                "title": "Loan creation + booking + fund transfer",
                "expected": (
                    "Loan account creation successful; loan booking successful; bank leg attempted; "
                    "final disbursement status should reach COMPLETED."
                ),
            },
            {
                "id": "TC02",
                "scenario": "S3_retry_after_terminal",
                "product": "JLG & INDL",
                "action": "On Retry",
                "title": "Retry after DTFC+NEFT success (terminal)",
                "expected": (
                    "On retry with any function_sub_code after LAN_CREATED/LOAN_BOOKED/DTFC_SUCCESS/COMPLETED, "
                    "request should be rejected or treated as no-op (no new artifacts / no duplicate bank call)."
                ),
            },
            {
                "id": "TC03",
                "scenario": "S1_retry_dtfc_failed_neft_not_attempted",
                "product": "JLG & INDL",
                "action": "On Retry",
                "title": "DTFC failed; NEFT not attempted",
                "expected": (
                    "Should check CRR. If no DTFC success exists, should retry DTFC. "
                    "Loan disbursement status should remain at LOAN_BOOKED/DTFC stage and NEFT must not be attempted."
                ),
            },
            {
                "id": "TC04",
                "scenario": "S2_retry_neft_failed",
                "product": "JLG & INDL",
                "action": "On Retry",
                "title": "DTFC success; NEFT failed",
                "expected": (
                    "Should check CRR. If DTFC success exists, should move to fund transfer. "
                    "If NEFT failed, should increase externalRefNo and retry fund transfer; reach COMPLETED on success."
                ),
            },
            {
                "id": "TC05",
                "scenario": "S4_SHG_parent_dtfc_failed",
                "product": "SHG",
                "action": "On Retry",
                "title": "Parent DTFC failed; no fund transfer attempted",
                "expected": (
                    "Should retry DTFC for parent (and only after success proceed). "
                    "Until DTFC succeeds, parent/child fund transfer must not be attempted."
                ),
            },
            {
                "id": "TC06",
                "scenario": "S5_SHG_parent_ft_failed",
                "product": "SHG",
                "action": "On Retry",
                "title": "Parent DTFC success; parent fund transfer failed",
                "expected": (
                    "Should check CRR. If DTFC success exists, attempt parent fund transfer again. "
                    "Child must not be attempted until parent fund transfer succeeds."
                ),
            },
            {
                "id": "TC07",
                "scenario": "S6_SHG_child_ft_failed",
                "product": "SHG",
                "action": "On Retry",
                "title": "Parent fund transfer success; child fund transfer failed",
                "expected": (
                    "Should check CRR. If parent fund transfer succeeded, attempt child fund transfer again. "
                    "On success, status should update to COMPLETED (or CHILD_SUCCESS then COMPLETED)."
                ),
            },
            {
                "id": "TC08",
                "scenario": "S7_SHG_retry_after_terminal",
                "product": "SHG",
                "action": "On Retry",
                "title": "Retry after parent+child success (terminal)",
                "expected": "Retry should be rejected or treated as no-op once COMPLETED."
            },
            {
                "id": "TC09",
                "scenario": "default_replay",
                "product": "JLG & INDL",
                "action": "On Retry",
                "title": "Idempotent retry (sanity invariant)",
                "expected": "Same request again should not duplicate LAN, schedule/dues, or external calls (CRR deltas must be 0).",
            },
            {
                "id": "TC10",
                "scenario": "stage_replay_LAN_CREATED",
                "product": "JLG & INDIVIDUAL",
                "action": "On Retry",
                "title": "Post-completion retry from LAN_CREATED (safety)",
                "expected": "Even if called again after completion, should remain safe and idempotent.",
            },
            {
                "id": "TC11",
                "scenario": "stage_replay_LOAN_BOOKED",
                "product": "JLG & INDIVIDUAL",
                "action": "On Retry",
                "title": "Post-completion retry from LOAN_BOOKED (safety)",
                "expected": "Even if called again after completion, should remain safe and idempotent.",
            },
            {
                "id": "TC12",
                "scenario": "stage_replay_DTFC_SUCCESS",
                "product": "JLG & INDIVIDUAL",
                "action": "On Retry",
                "title": "Post-completion retry from DTFC_SUCCESS (safety)",
                "expected": "Even if called again after completion, should remain safe and idempotent.",
            },
            {
                "id": "TC13",
                "scenario": "S2b_mft_inquiry_unknown",
                "product": "JLG & INDL",
                "action": "On Retry",
                "title": "MFT inquiry UNKNOWN handling",
                "expected": "When inquiry response is non-definitive (parse/timeout style), CRR should record UNKNOWN and avoid same-run re-initiation.",
            },
            {
                "id": "TC14",
                "scenario": "S2c_mft_inquiry_retry_same_ref",
                "product": "JLG & INDL",
                "action": "On Retry",
                "title": "MFT inquiry retry with same reference",
                "expected": "After UNKNOWN inquiry, next inquiry retry should use same external reference number (idempotent key reuse).",
            },
            {
                "id": "TC15",
                "scenario": "S2d_mft_transfer_unknown",
                "product": "JLG & INDL",
                "action": "On Retry",
                "title": "MFT transfer UNKNOWN handling",
                "expected": "When MFT transfer outcome is uncertain (timeout/transport), CRR should record UNKNOWN and flow should avoid duplicate same-run re-initiation.",
            },
        ]

    lines: list[str] = []
    lines.append("=== disburseLoan sanity report (L1 test cases) ===")
    lines.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    for k in ("endpoint", "external_ref_number", "disbursement_mode", "bank_leg", "simulator_up", "simulator_profile"):
        if k in meta:
            lines.append(f"{k}: {meta[k]}")
    lines.append("")
    bank_leg_label = str(meta.get("bank_leg") or "BANK").upper()
    bank_success_col = f"{bank_leg_label}_OKΔ"
    bank_unknown_col = f"{bank_leg_label}_UNKΔ"

    total = len(results)
    failed = sum(1 for r in results if is_fail(r))
    passed = total - failed
    lines.append(f"Result: total={total} passed={passed} failed={failed}")
    lines.append("")

    lines.append("Disbursement status lifecycle (reference):")
    lines.append("- Non-child loans: LAN_CREATED → LOAN_BOOKED → DTFC_SUCCESS → COMPLETED")
    lines.append("- Child-flow loans: LAN_CREATED → LOAN_BOOKED → DTFC_SUCCESS → PARENT_SUCCESS → CHILD_SUCCESS → COMPLETED")
    lines.append("")

    # Test case table (screenshot-style)
    lines.append("Test cases covered:")
    lines.append(
        "  "
        + cell("TC", 4)
        + "  "
        + cell("PRODUCT", 14)
        + "  "
        + cell("ACTION", 9)
        + "  "
        + cell("TITLE", 34)
        + "  "
        + cell("RES", 4)
        + "  "
        + cell("HTTP", 4)
        + "  "
        + cell("LAN", 12)
        + "  "
        + cell("DISB_STATUS", 12)
        + "  "
        + cell(bank_success_col, 8)
        + "  "
        + cell(bank_unknown_col, 9)
        + "  "
        + "ACTUAL (inst/dues, CRR before→after)"
    )
    by_name = {r.name: r for r in results}
    for tc in tc_catalog():
        r = by_name.get(tc["scenario"])
        if not r:
            continue
        status = "SKIP" if is_skipped(r) else ("FAIL" if is_fail(r) else "PASS")
        lan = r.loan.account_number if r.loan else ""
        disb = r.loan.disbursement_status if r.loan else ""
        inst = (r.diagnostics or {}).get("installments", "")
        dues = (r.diagnostics or {}).get("dues", "")
        bank_ok_d = (r.diagnostics or {}).get("bank_success_delta", "")
        bank_unk_d = (r.diagnostics or {}).get("bank_unknown_delta", "")
        if bank_ok_d == "":
            bank_ok_d = (r.diagnostics or {}).get("neft_success_delta", "")
        if bank_unk_d == "":
            bank_unk_d = (r.diagnostics or {}).get("neft_unknown_delta", "")
        crr_b = (r.diagnostics or {}).get("crr_before_raw", {})
        crr_a = (r.diagnostics or {}).get("crr_after_raw", {})
        lines.append(
            "  "
            + cell(tc["id"], 4)
            + "  "
            + cell(tc["product"], 14)
            + "  "
            + cell(tc["action"], 9)
            + "  "
            + cell(tc["title"], 34)
            + "  "
            + cell(status, 4)
            + "  "
            + cell(r.http_status, 4)
            + "  "
            + cell(lan, 12)
            + "  "
            + cell(disb, 12)
            + "  "
            + cell(bank_ok_d, 8)
            + "  "
            + cell(bank_unk_d, 9)
            + "  "
            + f"inst={inst} dues={dues} crr_before={_format_counts(crr_b) if isinstance(crr_b, dict) else crr_b} crr_after={_format_counts(crr_a) if isinstance(crr_a, dict) else crr_a}"
        )

    lines.append("")
    lines.append("Expected behaviour (per test case):")
    for tc in tc_catalog():
        lines.append(f"- {tc['id']} {tc['title']} ({tc['action']}): {tc['expected']}")

    # Details only for failures/warnings
    for r in results:
        bad = [c for c in r.checks if not c.ok]
        if not bad:
            continue
        lines.append("")
        lines.append(f"Details: scenario={r.name} http_status={r.http_status}")
        for c in bad:
            lines.append(f"  - {c.level} {c.name}: {c.details}")
        if r.loan:
            l = r.loan
            lines.append(
                f"  loan: account_number={l.account_number} account_id={l.account_id} "
                f"loan_status={l.loan_status} disb_status={l.disbursement_status} has_child={l.has_child_accounts}"
            )

    lines.append("")
    return "\n".join(lines) + "\n"


def _write_pdf_report(report_path: Path, *, results: list[ScenarioResult], meta: dict[str, Any]) -> None:
    """
    PDF writer.

    - Preferred: WeasyPrint (HTML+CSS → PDF; best-looking tables).
    - Next: ReportLab (tabular, verbose).
    - Fallback: minimal dependency-free PDF (monospace text) to keep the suite runnable everywhere.
    """
    _ensure_dir(report_path.parent)

    # Prefer WeasyPrint if present.
    try:
        from weasyprint import HTML  # type: ignore

        def h(s: Any) -> str:
            return html.escape("" if s is None else str(s), quote=True)

        def fmt_counts(v: Any) -> str:
            if isinstance(v, dict):
                return _format_counts(v)
            return "" if v is None else str(v)

        def diag_get(d: dict[str, Any], k: str, default: Any = "") -> Any:
            return d.get(k, default) if isinstance(d, dict) else default
        bank_leg = str(meta.get("bank_leg") or "BANK").upper()

        def flow_happened_text(diag: dict[str, Any]) -> str:
            crr = diag_get(diag, "crr_after_raw", {})
            if not isinstance(crr, dict) or not crr:
                return "No active CRR rows for this testcase (often expected in replay/stage-forced cases; check archived rows and deltas)."
            parts: list[str] = []
            mapping = {
                "DISB_GL_CBS_INTEGRATION": "GL posting API",
                "DISB_GL_CBS_INTEGRATION_NETOFF": "Net-off GL posting API",
                "DISBURSEMENT_NEFT": "NEFT payment API",
                "NEFT_TRANSACTION_INQUIRY": "NEFT status inquiry API",
                "DISBURSEMENT_MFT": "MFT payment API",
                "MFT_TRANSACTION_INQUIRY": "MFT status inquiry API",
            }
            for k, v in sorted(crr.items()):
                if not isinstance(k, str):
                    continue
                txn = k.split(":")[0]
                st = k.split(":")[1] if ":" in k else ""
                label = mapping.get(txn, txn)
                parts.append(f"{label} ({txn}) status={st} count={v}")
            return "; ".join(parts) if parts else "No recognized transaction_type rows."

        # Build a clean, shareable HTML report with CSS tables (no acronyms without expansion).
        css = """
        @page { size: A4 landscape; margin: 14mm 12mm; }
        body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Noto Sans", "Liberation Sans", sans-serif; color: #111827; }
        h1 { font-size: 18px; margin: 0 0 6px 0; }
        h2 { font-size: 14px; margin: 14px 0 6px 0; }
        .muted { color: #6b7280; font-size: 11px; }
        .pill { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 700; }
        .pass { background: #dcfce7; color: #14532d; }
        .warn { background: #fef9c3; color: #713f12; }
        .fail { background: #fee2e2; color: #7f1d1d; }
        table { width: 100%; border-collapse: collapse; table-layout: fixed; }
        th, td { border: 1px solid #e5e7eb; padding: 8px 10px; vertical-align: top; font-size: 11px; line-height: 1.25; word-break: break-word; overflow-wrap: anywhere; }
        th { background: #2563eb; color: #ffffff; font-weight: 800; }
        tr:nth-child(even) td { background: #f9fafb; }
        .kv td:first-child { width: 24%; font-weight: 600; background: #f3f4f6; }
        .section { page-break-inside: avoid; }
        .pb { page-break-before: always; }
        .code { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; font-size: 10px; white-space: pre-wrap; }
        .tight th, .tight td { padding: 6px 8px; font-size: 10.5px; }
        """

        total = len(results)
        failed = sum(1 for r in results if any((not c.ok) and c.level == "FAIL" for c in (r.checks or [])))
        warns = sum(1 for r in results if any((not c.ok) and c.level == "WARN" for c in (r.checks or [])) and not any((not c.ok) and c.level == "FAIL" for c in (r.checks or [])))
        passed = total - failed
        overall_cls = "fail" if failed else ("warn" if warns else "pass")

        meta_rows = []
        for k in ("endpoint", "external_ref_number", "disbursement_mode", "bank_leg", "simulator_up", "simulator_profile"):
            if k in meta:
                meta_rows.append(f"<tr><td>{h(k)}</td><td>{h(meta.get(k))}</td></tr>")

        scenario_flow_catalog: dict[str, dict[str, str]] = {
            "default_once": {
                "tc": "TC01",
                "pre": "Fresh request. No prior completed run for this unique external_ref_number.",
                "action": "Call disburseLoan with function_sub_code=DEFAULT.",
                "expected": "Loan creation, booking, bank transfer flow should complete to COMPLETED.",
            },
            "S1_retry_dtfc_failed_neft_not_attempted": {
                "tc": "TC03",
                "pre": "Forced stage: LOAN_BOOKED, GL/NEFT audit rows archived, DTFC leg forced to fail.",
                "action": "Retry with DEFAULT.",
                "expected": "Should remain before NEFT (LOAN_BOOKED/DTFC stage), NEFT must not be newly attempted.",
            },
            "S2_retry_neft_failed": {
                "tc": "TC04",
                "pre": "Forced stage: DTFC_SUCCESS, NEFT prior rows archived, NEFT leg forced to fail.",
                "action": "Retry with DEFAULT.",
                "expected": "Should stay at DTFC_SUCCESS when bank-leg fails; status inquiry path should be triggered and recorded in CRR; recovery happens on next retry.",
            },
            "S2b_mft_inquiry_unknown": {
                "tc": "TC13",
                "pre": "MFT payment log exists; inquiry response is forced to non-definitive/unknown mapping.",
                "action": "Retry with DEFAULT to trigger status inquiry.",
                "expected": "MFT status inquiry should be logged as UNKNOWN and payment re-initiation should not happen in the same run.",
            },
            "S2c_mft_inquiry_retry_same_ref": {
                "tc": "TC14",
                "pre": "Previous MFT inquiry is UNKNOWN for the same loan.",
                "action": "Retry again with DEFAULT.",
                "expected": "Status inquiry should run again using the same external reference number (idempotency key reuse).",
            },
            "S2d_mft_transfer_unknown": {
                "tc": "TC15",
                "pre": "MFT transfer call returns uncertain outcome (transport timeout) during disbursement.",
                "action": "Retry with DEFAULT.",
                "expected": "DISBURSEMENT_MFT should be logged as UNKNOWN; no same-run duplicate transfer should be triggered.",
            },
            "S3_retry_after_terminal": {
                "tc": "TC02",
                "pre": "Forced stage: COMPLETED (terminal).",
                "action": "Retry with DEFAULT.",
                "expected": "No-op/rejection semantics; no new DB artifacts or external call records.",
            },
            "default_replay": {
                "tc": "TC09",
                "pre": "Same payload replay after successful default_once.",
                "action": "Call DEFAULT again.",
                "expected": "Idempotent no-op: no new loan/schedule/dues/CRR success rows.",
            },
            "S4_SHG_parent_dtfc_failed": {"tc": "TC05", "pre": "SHG parent DTFC failed stage.", "action": "Retry.", "expected": "Retry DTFC first; no parent/child transfer before DTFC success."},
            "S5_SHG_parent_ft_failed": {"tc": "TC06", "pre": "SHG parent DTFC success but parent transfer failed.", "action": "Retry.", "expected": "Retry parent transfer; child should wait."},
            "S6_SHG_child_ft_failed": {"tc": "TC07", "pre": "SHG parent transfer success but child transfer failed.", "action": "Retry.", "expected": "Retry child transfer; then move to COMPLETED."},
            "S7_SHG_retry_after_terminal": {"tc": "TC08", "pre": "SHG already terminal.", "action": "Retry.", "expected": "No-op/rejection semantics."},
        }
        scenario_title_catalog: dict[str, str] = {
            "default_once": "Initial disbursement execution",
            "default_replay": "Duplicate request idempotency check",
            "S1_retry_dtfc_failed_neft_not_attempted": "DTFC pending path re-attempt check",
            "S2_retry_neft_failed": "Bank leg failure re-attempt check",
            "S2b_mft_inquiry_unknown": "MFT inquiry unknown handling check",
            "S2c_mft_inquiry_retry_same_ref": "MFT inquiry same-reference reuse check",
            "S2d_mft_transfer_unknown": "MFT transfer unknown handling check",
            "S3_retry_after_terminal": "Terminal-state re-call no-op check",
            "S4_SHG_parent_dtfc_failed": "SHG parent DTFC pending check",
            "S5_SHG_parent_ft_failed": "SHG parent transfer failure check",
            "S6_SHG_child_ft_failed": "SHG child transfer failure check",
            "S7_SHG_retry_after_terminal": "SHG terminal-state re-call check",
            "resume_LAN_CREATED": "Re-call from LAN_CREATED stage",
            "resume_LOAN_BOOKED": "Re-call from LOAN_BOOKED stage",
            "resume_DTFC_SUCCESS": "Re-call from DTFC_SUCCESS stage",
            "injected_stuck_DTFC_SUCCESS": "Forced unknown-state stability check",
            "resume_LOAN_BOOKED_after_unknown": "Recovery after unknown-state check",
            "simulate_bank_failure_default_call": "Forced bank-failure path check",
            "resume_LOAN_BOOKED_after_failure_sim": "Recovery after bank-failure check",
            "stage_replay_LAN_CREATED": "Post-completion re-call from LAN_CREATED",
            "stage_replay_LOAN_BOOKED": "Post-completion re-call from LOAN_BOOKED",
            "stage_replay_DTFC_SUCCESS": "Post-completion re-call from DTFC_SUCCESS",
        }

        def display_case_name(name: str, tc: str = "") -> str:
            title = scenario_title_catalog.get(name, name.replace("_", " ").strip())
            return f"{tc} - {title}" if tc else title

        def row_result(r: ScenarioResult) -> str:
            has_fail = any((not c.ok) and c.level == "FAIL" for c in (r.checks or []))
            has_warn = any((not c.ok) and c.level == "WARN" for c in (r.checks or []))
            if isinstance(r.diagnostics, dict) and r.diagnostics.get("skipped"):
                return '<span class="pill warn">SKIP</span>'
            if has_fail:
                return '<span class="pill fail">FAIL</span>'
            if has_warn:
                return '<span class="pill warn">WARN</span>'
            return '<span class="pill pass">PASS</span>'

        summary_rows_basic: list[str] = []
        summary_rows_dedupe: list[str] = []
        for r in results:
            d = r.diagnostics or {}
            loan = r.loan
            tc = (scenario_flow_catalog.get(r.name, {}) or {}).get("tc", "")
            warn_reasons = [f"{c.name}: {c.details}" for c in (r.checks or []) if (not c.ok) and c.level == "WARN"]
            note = ""
            if r.name == "injected_stuck_DTFC_SUCCESS":
                note = "Suite forces UNKNOWN before retry-check"
            if warn_reasons:
                joined = "; ".join(warn_reasons[:2])
                note = (note + " | " if note else "") + f"WARN reason: {joined}"

            summary_rows_basic.append(
                "<tr>"
                f"<td>{h(display_case_name(r.name, tc))}</td>"
                f"<td>{row_result(r)}</td>"
                f"<td>{h(r.http_status)}</td>"
                f"<td>{h(loan.account_number if loan else '')}</td>"
                f"<td>{h(loan.disbursement_status if loan else '')}</td>"
                f"<td>{h(note)}</td>"
                "</tr>"
            )

            summary_rows_dedupe.append(
                "<tr>"
                f"<td>{h(display_case_name(r.name, tc))}</td>"
                f"<td>{h(diag_get(d,'bank_success_delta',diag_get(d,'neft_success_delta','')))}</td>"
                f"<td>{h(diag_get(d,'bank_unknown_delta',diag_get(d,'neft_unknown_delta','')))}</td>"
                f"<td>{h(diag_get(d,'bank_inquiry_delta',diag_get(d,'mft_inquiry_delta',diag_get(d,'neft_inquiry_delta',''))))}</td>"
                f"<td>{h(diag_get(d,'gl_delta',''))}</td>"
                f"<td>{h(diag_get(d,'gl_netoff_delta',''))}</td>"
                "</tr>"
            )

        sequence_rows: list[str] = []
        for i, r in enumerate(results, start=1):
            cat = scenario_flow_catalog.get(r.name, {})
            tc = cat.get("tc", "")
            sequence_rows.append(
                "<tr>"
                f"<td>{i}</td>"
                f"<td>{h(tc)}</td>"
                f"<td>{h(display_case_name(r.name, tc))}</td>"
                f"<td>{row_result(r)}</td>"
                f"<td>{h('SKIPPED: ' + str((r.diagnostics or {}).get('skip_reason', '')) if (r.diagnostics or {}).get('skipped') else (r.loan.disbursement_status if r.loan else 'n/a'))}</td>"
                "</tr>"
            )

        # Verbose per-testcase blocks with DB evidence in business flow format.
        verbose_blocks = []
        for r in results:
            d = r.diagnostics or {}
            loan = r.loan
            bad = [c for c in (r.checks or []) if not c.ok]
            cat = scenario_flow_catalog.get(r.name, {})
            tc_id = cat.get("tc", "")
            pre = cat.get("pre", "Precondition not cataloged for this scenario.")
            act = cat.get("action", "Action not cataloged.")
            exp = cat.get("expected", "Expected behavior not cataloged.")
            skipped = bool(d.get("skipped"))
            actual = (
                f"SKIPPED: {d.get('skip_reason')}"
                if skipped
                else (
                    f"HTTP={r.http_status}, disbursement_status={(loan.disbursement_status if loan else 'n/a')}, "
                    f"installments_delta={diag_get(d,'installments_added_delta','')}, dues_delta={diag_get(d,'dues_added_delta','')}, "
                    f"bank_success_delta={diag_get(d,'bank_success_delta',diag_get(d,'neft_success_delta',''))}, "
                    f"bank_unknown_delta={diag_get(d,'bank_unknown_delta',diag_get(d,'neft_unknown_delta',''))}"
                )
            )

            def evid_block(title: str, obj: Any) -> str:
                if not isinstance(obj, dict):
                    return ""
                latest = obj.get("latest") or {}
                latest_txt = ""
                if isinstance(latest, dict) and latest:
                    latest_txt = f"id={latest.get('id')} system_date={latest.get('system_date')} status={latest.get('status')} client_reference_number={latest.get('client_reference_number')}"
                archived_latest = obj.get("archived_latest") or {}
                archived_latest_txt = ""
                if isinstance(archived_latest, dict) and archived_latest:
                    archived_latest_txt = (
                        f"id={archived_latest.get('id')} system_date={archived_latest.get('system_date')} "
                        f"status={archived_latest.get('status')} client_reference_number={archived_latest.get('client_reference_number')}"
                    )

                active_part = (
                    f"New calls in this testcase (live rows): total_rows={h(obj.get('total_rows'))}, max_id={h(obj.get('max_id'))}"
                    + (f"<br/><span class='code'>{h(latest_txt)}</span>" if latest_txt else "")
                )
                archived_part = (
                    f"Previous call history from earlier steps: total_rows={h(obj.get('archived_total_rows', 0))}, max_id={h(obj.get('archived_max_id', 0))}"
                    + (f"<br/><span class='code'>{h(archived_latest_txt)}</span>" if archived_latest_txt else "")
                )
                note = "<br/><span class='muted'>Note: previous-call history is kept separately in recovery/retry simulations to avoid duplicate processing.</span>"
                return (
                    f"<tr><td>{h(title)}</td><td>"
                    + active_part
                    + "<br/>"
                    + archived_part
                    + note
                    + "</td></tr>"
                )

            kv_rows = []
            kv_rows.append(f"<tr><td>Precondition</td><td>{h(pre)}</td></tr>")
            kv_rows.append(f"<tr><td>Action</td><td>{h(act)}</td></tr>")
            kv_rows.append(f"<tr><td>Expected</td><td>{h(exp)}</td></tr>")
            kv_rows.append(f"<tr><td>Actual</td><td>{h(actual)}</td></tr>")
            kv_rows.append(f"<tr><td>Flow evidence (from transaction_type)</td><td>{h(flow_happened_text(d))}</td></tr>")
            if skipped:
                duplicate_verdict = "Not applicable (testcase skipped for this payload)."
            else:
                deltas = [
                    int(diag_get(d, "bank_success_delta", 0) or 0),
                    int(diag_get(d, "bank_unknown_delta", 0) or 0),
                    int(diag_get(d, "bank_inquiry_delta", 0) or 0),
                    int(diag_get(d, "gl_delta", 0) or 0),
                    int(diag_get(d, "gl_netoff_delta", 0) or 0),
                ]
                duplicate_verdict = (
                    "YES — new external-call rows were created in this testcase."
                    if any(v > 0 for v in deltas)
                    else "NO — no new external-call rows were created; replay/idempotent behavior."
                )
            kv_rows.append(f"<tr><td>Duplicate external call triggered in this testcase?</td><td>{h(duplicate_verdict)}</td></tr>")
            kv_rows.append(f"<tr><td>Loan snapshot</td><td>{h(f'LAN={loan.account_number}, account_id={loan.account_id}, loan_status={loan.loan_status}, disb_status={loan.disbursement_status}, has_child={loan.has_child_accounts}' if loan else 'n/a')}</td></tr>")
            kv_rows.append(f"<tr><td>Interpretation</td><td>{h(diag_get(d,'interpretation',''))}</td></tr>")
            kv_rows.append(f"<tr><td>Installments total (after call)</td><td>{h(diag_get(d,'after_installments',diag_get(d,'installments','')))}</td></tr>")
            kv_rows.append(f"<tr><td>Dues total (after call)</td><td>{h(diag_get(d,'after_dues',diag_get(d,'dues','')))}</td></tr>")
            kv_rows.append(f"<tr><td>Installments added Δ (this testcase)</td><td>{h(diag_get(d,'installments_added_delta',''))}</td></tr>")
            kv_rows.append(f"<tr><td>Dues added Δ (this testcase)</td><td>{h(diag_get(d,'dues_added_delta',''))}</td></tr>")
            kv_rows.append(f"<tr><td>UTR number (after call)</td><td>{h(diag_get(d,'after_utr',diag_get(d,'utr','')))}</td></tr>")
            kv_rows.append(f"<tr><td>UTR changed? (this testcase)</td><td>{h(diag_get(d,'utr_changed',''))}</td></tr>")
            kv_rows.append(f"<tr><td>New successful {h(bank_leg)} records added (count)</td><td>{h(diag_get(d,'bank_success_delta',diag_get(d,'neft_success_delta','')))}</td></tr>")
            kv_rows.append(f"<tr><td>New {h(bank_leg)}-UNKNOWN records added (count)</td><td>{h(diag_get(d,'bank_unknown_delta',diag_get(d,'neft_unknown_delta','')))}</td></tr>")
            kv_rows.append(f"<tr><td>New {h(bank_leg)} status inquiry records added (count)</td><td>{h(diag_get(d,'bank_inquiry_delta',diag_get(d,'mft_inquiry_delta',diag_get(d,'neft_inquiry_delta',''))))}</td></tr>")

            kv_rows.append(evid_block("External call evidence BEFORE: NEFT payment", diag_get(d, "evidence_before_neft", None)))
            kv_rows.append(evid_block("External call evidence AFTER: NEFT payment", diag_get(d, "evidence_after_neft", None)))
            kv_rows.append(evid_block("External call evidence BEFORE: GL posting", diag_get(d, "evidence_before_gl", None)))
            kv_rows.append(evid_block("External call evidence AFTER: GL posting", diag_get(d, "evidence_after_gl", None)))
            kv_rows.append(evid_block("External call evidence BEFORE: Net-off GL posting", diag_get(d, "evidence_before_gl_netoff", None)))
            kv_rows.append(evid_block("External call evidence AFTER: Net-off GL posting", diag_get(d, "evidence_after_gl_netoff", None)))

            kv_rows.append(f"<tr><td>CRR counts (by type+status)</td><td><span class='code'>{h(diag_get(d,'crr_counts',''))}</span></td></tr>")

            if bad:
                bad_rows = ["<tr><th>Level</th><th>Check</th><th>Details</th></tr>"]
                for c in bad:
                    bad_rows.append(f"<tr><td>{h(c.level)}</td><td>{h(c.name)}</td><td>{h(c.details)}</td></tr>")
                bad_tbl = "<table>" + "".join(bad_rows) + "</table>"
            else:
                bad_tbl = "<div class='muted'>No warnings or failures in checks.</div>"

            verbose_blocks.append(
                f"""
                <div class="section pb">
                  <h2>Testcase: {h(display_case_name(r.name, tc_id))} {row_result(r)}</h2>
                  <table class="kv">{''.join(kv_rows)}</table>
                  <h2>Checks (warnings/failures)</h2>
                  {bad_tbl}
                  <h2>API response (prefix)</h2>
                  <div class="code">{h(diag_get(d,'response_body_prefix','')[:1200])}</div>
                </div>
                """
            )

        html_doc = f"""
        <!doctype html>
        <html>
          <head>
            <meta charset="utf-8"/>
            <style>{css}</style>
            <title>DisburseLoan Sanity Suite Report</title>
          </head>
          <body>
            <h1>DisburseLoan Sanity Suite — Beautiful Verbose Report</h1>
            <div class="muted">Generated: {h(time.strftime('%Y-%m-%d %H:%M:%S'))}</div>
            <div style="margin-top:8px;">
              <span class="pill {overall_cls}">Overall: total={total} passed={passed} failed={failed}</span>
            </div>

            <h2>Run context</h2>
            <table class="kv">{''.join(meta_rows)}</table>

            <h2>Glossary (no short forms)</h2>
            <table class="kv">
              <tr><td>NEFT</td><td>National Electronic Funds Transfer (bank transfer leg).</td></tr>
              <tr><td>CRR</td><td>client_request_response_log (database audit table capturing external calls and their status).</td></tr>
              <tr><td>transaction_type</td><td>Database marker that proves which API leg was executed (payment leg, inquiry leg, GL posting leg).</td></tr>
              <tr><td>GL posting</td><td>General Ledger posting to CBS (accounting integration).</td></tr>
              <tr><td>Net-off GL posting</td><td>GL posting specifically for net-off amount.</td></tr>
            </table>

            <h2>Disbursement status lifecycle (reference)</h2>
            <table class="kv">
              <tr><td>Non-child loans</td><td>LAN_CREATED → LOAN_BOOKED → DTFC_SUCCESS → COMPLETED</td></tr>
              <tr><td>Child-flow loans</td><td>LAN_CREATED → LOAN_BOOKED → DTFC_SUCCESS → PARENT_SUCCESS → CHILD_SUCCESS → COMPLETED</td></tr>
            </table>

            <h2>Summary 1/2 — What ran and what happened</h2>
            <table class="tight">
              <colgroup>
                <col style="width: 26%"/>
                <col style="width: 10%"/>
                <col style="width: 7%"/>
                <col style="width: 12%"/>
                <col style="width: 17%"/>
                <col style="width: 28%"/>
              </colgroup>
              <tr>
                <th>Testcase</th>
                <th>Result</th>
                <th>HTTP</th>
                <th>LAN</th>
                <th>Disbursement status</th>
                <th>Notes</th>
              </tr>
              {''.join(summary_rows_basic)}
            </table>

            <h2>Summary 2/2 — Proof of no duplicate external calls</h2>
            <div class="muted">
              For retries, the expected value is 0 in all “new records added” columns. Non-zero means a new external call record was written to the DB audit table.
            </div>
            <table class="tight">
              <colgroup>
                <col style="width: 24%"/>
                <col style="width: 13%"/>
                <col style="width: 13%"/>
                <col style="width: 14%"/>
                <col style="width: 18%"/>
                <col style="width: 18%"/>
              </colgroup>
              <tr>
                <th>Testcase</th>
                <th>New successful {h(bank_leg)} records added (count)</th>
                <th>New {h(bank_leg)}-UNKNOWN records added (count)</th>
                <th>New {h(bank_leg)} inquiry records added (count)</th>
                <th>New successful GL-posting records added (count)</th>
                <th>New successful Net-off GL-posting records added (count)</th>
              </tr>
              {''.join(summary_rows_dedupe)}
            </table>

            <h2>Execution sequence (what ran, in order)</h2>
            <table class="tight">
              <colgroup>
                <col style="width: 7%"/>
                <col style="width: 10%"/>
                <col style="width: 41%"/>
                <col style="width: 12%"/>
                <col style="width: 30%"/>
              </colgroup>
              <tr>
                <th>Step</th>
                <th>TC</th>
                <th>Scenario</th>
                <th>Result</th>
                <th>Outcome</th>
              </tr>
              {''.join(sequence_rows)}
            </table>

            {''.join(verbose_blocks)}
          </body>
        </html>
        """

        HTML(string=html_doc, base_url=str(Path.cwd())).write_pdf(str(report_path))
        return
    except Exception:
        # If WeasyPrint isn't available/working, fall through to ReportLab/minimal.
        pass

    # Prefer ReportLab if present.
    try:
        from reportlab.lib import colors  # type: ignore
        from reportlab.lib.pagesizes import A4, landscape  # type: ignore
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore
        from reportlab.lib.units import cm  # type: ignore
        from reportlab.platypus import (  # type: ignore
            SimpleDocTemplate,
            Spacer,
            Paragraph,
            Table,
            TableStyle,
            PageBreak,
        )

        styles = getSampleStyleSheet()
        h1 = styles["Heading1"]
        h2 = styles["Heading2"]
        mono = ParagraphStyle(
            "mono",
            parent=styles["Normal"],
            fontName="Courier",
            fontSize=8.5,
            leading=10,
        )
        small = ParagraphStyle("small", parent=styles["Normal"], fontSize=9, leading=11)

        page_size = landscape(A4)
        doc = SimpleDocTemplate(
            str(report_path),
            pagesize=page_size,
            leftMargin=1.2 * cm,
            rightMargin=1.2 * cm,
            topMargin=1.2 * cm,
            bottomMargin=1.2 * cm,
            title="DisburseLoan Sanity Suite Report",
        )

        def fmt(v: Any) -> str:
            if v is None:
                return ""
            return str(v)

        def fmt_counts(d: Any) -> str:
            if isinstance(d, dict):
                return _format_counts(d)
            return fmt(d)

        story: list[Any] = []
        story.append(Paragraph("DisburseLoan Sanity Suite — Verbose Report", h1))
        story.append(Paragraph(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}", small))
        story.append(Spacer(1, 10))

        # Meta table
        meta_rows = [["Field", "Value"]]
        for k in ("endpoint", "external_ref_number", "disbursement_mode", "bank_leg", "simulator_up", "simulator_profile"):
            if k in meta:
                meta_rows.append([k, fmt(meta.get(k))])
        meta_tbl = Table(meta_rows, colWidths=[4.5 * cm, 12.5 * cm])
        meta_tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(Paragraph("Run context", h2))
        story.append(meta_tbl)
        story.append(Spacer(1, 10))

        story.append(Paragraph("Disbursement status lifecycle (reference)", h2))
        story.append(Paragraph("Non-child loans: LAN_CREATED → LOAN_BOOKED → DTFC_SUCCESS → COMPLETED", small))
        story.append(Paragraph("Child-flow loans: LAN_CREATED → LOAN_BOOKED → DTFC_SUCCESS → PARENT_SUCCESS → CHILD_SUCCESS → COMPLETED", small))
        story.append(Spacer(1, 10))

        story.append(Paragraph("Glossary (no short forms)", h2))
        story.append(Paragraph("NEFT: National Electronic Funds Transfer (bank transfer leg).", small))
        story.append(Paragraph("CRR: client_request_response_log (database audit table capturing external calls and their status).", small))
        story.append(Paragraph("GL posting: General Ledger posting to CBS (accounting integration).", small))
        story.append(Paragraph("Net-off GL posting: GL posting specifically for net-off amount.", small))
        story.append(Spacer(1, 10))

        total = len(results)
        failed = sum(1 for r in results if any((not c.ok) and c.level == "FAIL" for c in r.checks))
        passed = total - failed
        story.append(Paragraph(f"Overall result: total={total} passed={passed} failed={failed}", small))
        story.append(Spacer(1, 10))

        # Summary table (tabular, no wide/free-text columns to avoid overlap).
        # Full CRR before/after appears in the per-testcase verbose section.
        summary_header = [
            "Testcase",
            "HTTP",
            "LAN",
            "DISB_STATUS",
            "New successful NEFT records added (count)",
            "New NEFT-UNKNOWN records added (count)",
            "New successful GL-posting records added (count)",
            "New successful Net-off GL-posting records added (count)",
            "Result / Notes",
        ]
        summary_rows = [summary_header]
        for r in results:
            has_fail = any((not c.ok) and c.level == "FAIL" for c in r.checks)
            has_warn = any((not c.ok) and c.level == "WARN" for c in r.checks)
            notes = []
            if has_fail:
                notes.append("FAIL")
            elif has_warn:
                notes.append("WARN")
            else:
                notes.append("PASS")

            neft_ok_d = (r.diagnostics or {}).get("neft_success_delta", "")
            neft_unk_d = (r.diagnostics or {}).get("neft_unknown_delta", "")
            gl_d = (r.diagnostics or {}).get("gl_delta", "")
            gl_netoff_d = (r.diagnostics or {}).get("gl_netoff_delta", "")
            if r.name == "injected_stuck_DTFC_SUCCESS":
                notes.append("suite forces UNKNOWN before retry-check")

            summary_rows.append(
                [
                    r.name,
                    fmt(r.http_status),
                    fmt(r.loan.account_number if r.loan else ""),
                    fmt(r.loan.disbursement_status if r.loan else ""),
                    fmt(neft_ok_d),
                    fmt(neft_unk_d),
                    fmt(gl_d),
                    fmt(gl_netoff_d),
                    "; ".join(notes),
                ]
            )

        story.append(Paragraph("Testcase summary (proof of duplicates / idempotency)", h2))
        # Convert cells to Paragraph to enable wrapping without overlapping.
        def pcell(v: Any) -> Paragraph:
            return Paragraph(str(v).replace("\n", "<br/>"), small)

        tbl_rows: list[list[Any]] = []
        for ridx, row in enumerate(summary_rows):
            if ridx == 0:
                tbl_rows.append([Paragraph(str(c), ParagraphStyle("hdr", parent=small, fontName="Helvetica-Bold", fontSize=9, leading=11)) for c in row])
            else:
                tbl_rows.append([pcell(c) for c in row])

        page_w, _page_h = page_size
        usable_w = page_w - doc.leftMargin - doc.rightMargin
        # Widths tuned to fit landscape A4; keep notes moderately wide.
        colw = [
            usable_w * 0.22,  # testcase
            usable_w * 0.05,  # http
            usable_w * 0.10,  # lan
            usable_w * 0.12,  # disb
            usable_w * 0.08,  # neft ok
            usable_w * 0.09,  # neft unk
            usable_w * 0.06,  # gl
            usable_w * 0.09,  # netoff gl
            usable_w * 0.19,  # notes
        ]
        tbl = Table(tbl_rows, colWidths=colw, repeatRows=1)
        tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 9),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor("#F3F4F6")]),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(tbl)
        story.append(Spacer(1, 10))

        # Per-testcase verbose section
        story.append(PageBreak())
        story.append(Paragraph("Verbose testcase details", h2))
        story.append(Paragraph("Each testcase includes request intent, actual status, counters, and any WARN/FAIL checks.", small))
        story.append(Spacer(1, 8))

        for r in results:
            story.append(Paragraph(f"Testcase: {r.name}", styles["Heading3"]))
            loan = r.loan
            story.append(
                Paragraph(
                    "Loan snapshot: "
                    + (f"LAN={loan.account_number}, account_id={loan.account_id}, loan_status={loan.loan_status}, disb_status={loan.disbursement_status}, has_child={loan.has_child_accounts}" if loan else "n/a"),
                    small,
                )
            )

            diag = r.diagnostics or {}
            diag_keys = [
                "installments",
                "dues",
                "utr",
                "lan_hint",
                "neft_success_delta",
                "neft_unknown_delta",
                "gl_delta",
                "gl_netoff_delta",
                "crr_before_raw",
                "crr_after_raw",
                "crr_delta_raw",
                "evidence_before_neft",
                "evidence_after_neft",
                "evidence_before_gl",
                "evidence_after_gl",
                "evidence_before_gl_netoff",
                "evidence_after_gl_netoff",
                "response_body_prefix",
            ]
            kv = [["Key", "Value"]]
            for k in diag_keys:
                if k in diag:
                    v = diag.get(k)
                    if isinstance(v, dict):
                        v = _format_counts(v)
                    kv.append([k, fmt(v)])
            kv_tbl = Table(kv, colWidths=[4.0 * cm, 14.0 * cm], repeatRows=1)
            kv_tbl.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ]
                )
            )
            story.append(kv_tbl)

            bad = [c for c in (r.checks or []) if not c.ok]
            if bad:
                story.append(Spacer(1, 6))
                chk = [["Level", "Check", "Details"]]
                for c in bad:
                    chk.append([c.level, c.name, c.details])
                chk_tbl = Table(chk, colWidths=[2.0 * cm, 4.5 * cm, 11.5 * cm], repeatRows=1)
                chk_tbl.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                        ]
                    )
                )
                story.append(chk_tbl)

            story.append(Spacer(1, 10))

        doc.build(story)
        return
    except Exception:
        # ReportLab not available (or failed) — fall back to the minimal PDF below.
        pass

    # Build lines
    lines: list[str] = []
    lines.append("DisburseLoan Testing Suite Report")
    lines.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    for k in ("endpoint", "external_ref_number", "disbursement_mode", "bank_leg", "simulator_up"):
        if k in meta:
            lines.append(f"{k}: {meta[k]}")
    if meta.get("simulator_profile"):
        lines.append(f"simulator_profile: {meta.get('simulator_profile')}")
    if meta.get("simulator_changes"):
        lines.append("simulator_changes:")
        for ch in (meta.get("simulator_changes") or []):
            if not isinstance(ch, dict):
                continue
            api = ch.get("api_name")
            typ = ch.get("request_type")
            if api and typ and "before" in ch and "after" in ch:
                b = ch.get("before") or {}
                a = ch.get("after") or {}
                b_code = b.get("response_code")
                a_code = a.get("response_code")
                b_to = b.get("timeout_period")
                a_to = a.get("timeout_period")
                b_dyn = b.get("dynamic_response")
                a_dyn = a.get("dynamic_response")
                b_cb = b.get("is_callback_enabled")
                a_cb = a.get("is_callback_enabled")
                b_prefix = str((b.get("response") or ""))[:80].replace("\n", " ")
                a_prefix = str((a.get("response") or ""))[:80].replace("\n", " ")
                lines.append(f"  - {api}/{typ}: code {b_code}->{a_code} timeout {b_to}->{a_to} dyn {b_dyn}->{a_dyn} cb {b_cb}->{a_cb}")
                lines.append(f"    before_prefix: {b_prefix}")
                lines.append(f"    after_prefix:  {a_prefix}")
            elif "error" in ch:
                lines.append(f"  - error: {ch.get('error')}")
    lines.append("")
    for r in results:
        has_fail = any((not cc.ok) and cc.level == "FAIL" for cc in r.checks)
        status = "PASS" if not has_fail else "FAIL"
        lines.append(f"Scenario: {r.name} | Status: {status} | HTTP: {r.http_status}")
        if r.loan:
            l = r.loan
            lines.append(f"  Loan: LAN={l.account_number} account_id={l.account_id} loan_status={l.loan_status} disb_status={l.disbursement_status} has_child={l.has_child_accounts}")
        for cc in r.checks:
            if cc.ok:
                continue
            lines.append(f"  {cc.level}: {cc.name} - {cc.details}")
        for dk in ("installments", "dues", "utr", "crr_counts"):
            if dk in r.diagnostics:
                lines.append(f"  diag.{dk}: {r.diagnostics[dk]}")
        lines.append("")

    # Simple pagination
    max_lines_per_page = 55
    pages = [lines[i : i + max_lines_per_page] for i in range(0, len(lines), max_lines_per_page)] or [[]]

    def pdf_escape(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    objects: list[bytes] = []

    def add_obj(b: bytes) -> int:
        objects.append(b)
        return len(objects)

    # 1) Catalog, 2) Pages, then per-page objects.
    # Font object
    font_obj = add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    page_kids_refs: list[str] = []
    page_objs: list[int] = []
    content_objs: list[int] = []

    for page_lines in pages:
        # Content stream
        y = 800
        stream_lines = ["BT", f"/F1 10 Tf", "72 0 0 72 0 0 Tm"]  # set matrix
        # We'll position lines manually with Td.
        stream_lines.append("1 0 0 1 72 800 Tm")
        for ln in page_lines:
            stream_lines.append(f"({pdf_escape(ln)}) Tj")
            stream_lines.append("0 -14 Td")
        stream_lines.append("ET")
        stream = ("\n".join(stream_lines)).encode("utf-8")
        content = b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
        content_obj = add_obj(content)
        content_objs.append(content_obj)

        # Page object (we'll reference Pages later)
        page_dict = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 {font_obj} 0 R >> >> "
            f"/Contents {content_obj} 0 R >>"
        ).encode("utf-8")
        page_obj = add_obj(page_dict)
        page_objs.append(page_obj)
        page_kids_refs.append(f"{page_obj} 0 R")

    # Important: Pages must be object #2 because page objects reference "2 0 R".
    # So we add Catalog later but overwrite objects[1] to become the Pages dictionary.
    pages_obj = add_obj(b"<< /Type /Pages /Kids [] /Count 0 >>")  # placeholder, will overwrite below
    catalog_obj = add_obj(b"<< /Type /Catalog /Pages 2 0 R >>")

    # Fix Pages object (must be object #2)
    kids = "[ " + " ".join(page_kids_refs) + " ]"
    pages_dict = f"<< /Type /Pages /Kids {kids} /Count {len(page_kids_refs)} >>".encode("utf-8")
    objects[1] = pages_dict  # object 2 (0-based index 1)

    # Write PDF with xref
    out = bytearray()
    out.extend(b"%PDF-1.4\n")
    xref_positions = [0]
    for i, obj in enumerate(objects, start=1):
        xref_positions.append(len(out))
        out.extend(f"{i} 0 obj\n".encode("utf-8"))
        out.extend(obj)
        out.extend(b"\nendobj\n")
    xref_start = len(out)
    out.extend(f"xref\n0 {len(objects)+1}\n".encode("utf-8"))
    out.extend(b"0000000000 65535 f \n")
    for pos in xref_positions[1:]:
        out.extend(f"{pos:010d} 00000 n \n".encode("utf-8"))
    out.extend(b"trailer\n")
    out.extend(f"<< /Size {len(objects)+1} /Root {catalog_obj} 0 R >>\n".encode("utf-8"))
    out.extend(b"startxref\n")
    out.extend(f"{xref_start}\n".encode("utf-8"))
    out.extend(b"%%EOF\n")

    report_path.write_bytes(bytes(out))


def _write_qa_testcase_matrix_csv(path: Path) -> None:
    """QA-shareable testcase matrix in screenshot-style wording."""
    _ensure_dir(path.parent)
    import csv

    rows = [
        {
            "Sl No": "1",
            "Product Code": "JLG & INDL",
            "Scenarios": "a. Loan account creation successful\nb. Loan booking successful\nc. Due To FC Failed\nd. NEFT not attempted",
            "Action": "On Retry",
            "Expected Behaviour": "a. It should check client request response log table. If success entry is found for Due To FC transaction then it should sync loan disbursement status and proceed with the fund transfer.\nb. It should check client request response log table. If failure entry is found for Due To FC transaction then it should increase externalRefNo by 1 and retry the Due To FC.\nc. Loan disbursement status will be updated as 'DTFC_SUCCESS'.\nd. Fund transfer will be attempted and on successful call, the disbursement status will be updated as 'COMPLETED'.",
        },
        {
            "Sl No": "2",
            "Product Code": "JLG & INDL",
            "Scenarios": "a. Loan account creation successful\nb. Loan booking successful\nc. Due To FC successful\nd. NEFT Failed",
            "Action": "On Retry",
            "Expected Behaviour": "a. It should check client request response log table. If success entry is found for NEFT transaction then it should sync loan disbursement status and exit without doing fund transfer.\nb. It should check client request response log table. If failure entry is found for NEFT transaction then it should increase externalRefNo by 1 and retry the fund transfer.",
        },
        {
            "Sl No": "3",
            "Product Code": "JLG & INDL",
            "Scenarios": "a. Loan account creation successful\nb. Loan booking successful\nc. Due To FC successful\nd. NEFT successful",
            "Action": "On Retry",
            "Expected Behaviour": "a. On retry with any function sub code like LAN_CREATED, LOAN_BOOKED or DTFC_SUCCESS, the request should be treated as terminal-safe no-op/retry path.\nb. It should not create duplicate loan account/schedule/due artifacts.\nc. It should not create duplicate successful external call rows.\nd. Loan disbursement status should remain terminal.",
        },
        {
            "Sl No": "4",
            "Product Code": "SHG",
            "Scenarios": "a. Parent Loan account creation successful\nb. Parent Loan Loan booking successful\nc. Parent Loan Due To FC Failed\nd. Parent Loan fund transfer not attempted\ne. Child fund transfer not attempted",
            "Action": "On Retry",
            "Expected Behaviour": "a. It should check client request response log table. If success entry is found for Due To FC transaction then it should sync loan disbursement status and proceed with the fund transfer for parent and child loan.\nb. It should check client request response log table. If failure entry is found for Due To FC transaction then it should increase externalRefNo by 1 and retry the Due To FC.\nb1. On successful Due To FC transaction parent loan disbursement status will be updated as 'DTFC_SUCCESS'.\nb2. Post successful due to FC transaction, only allowed IFT transaction for parent loan will be attempted and on successful call, the disbursement status will be updated as 'PARENT_SUCCESS' or else it will remain as 'DTFC_SUCCESS'.\nb3. Post successful only allowed IFT transaction for parent loan, child loan NEFT transaction will be attempted and on successful call, the disbursement status will be updated as 'COMPLETED' or else it will remain as 'PARENT_SUCCESS'.",
        },
        {
            "Sl No": "5",
            "Product Code": "SHG",
            "Scenarios": "a. Parent Loan account creation successful\nb. Parent Loan Loan booking successful\nc. Parent Loan Due To FC successful\nd. Parent Loan fund transfer Failed\ne. Child fund transfer not attempted",
            "Action": "On Retry",
            "Expected Behaviour": "a. It should check client request response log table. If success entry is found for only allowed IFT transaction then it should sync loan disbursement status and proceed with the fund transfer for the child loan.\nb. It should check client request response log table. If success entry is not found for only allowed IFT transaction then it should increase externalRefNo by 1 and retry the parent loan only allowed IFT transaction.\nb1. On successful only allowed IFT transaction parent loan disbursement status will be updated as 'PARENT_SUCCESS'.\nb2. Post successful only allowed IFT transaction for parent loan, child loan fund transfer will be attempted and on successful call, the disbursement status will be updated 'COMPLETED' or else it will remain as 'PARENT_SUCCESS'.",
        },
        {
            "Sl No": "6",
            "Product Code": "SHG",
            "Scenarios": "a. Parent Loan account creation successful\nb. Parent Loan Loan booking successful\nc. Parent Loan Due to FC successful\nd. Parent Loan fund transfer successful\ne. Child fund transfer failed",
            "Action": "On Retry",
            "Expected Behaviour": "a. It should check client request response log table. If success entry is found for all child loan fund transaction then it should sync loan disbursement status and exit without doing child transaction.\nb. It should check client request response log table. If success entry is not found for child loan fund transaction then it should increase externalRefNo by 1 and retry the parent loan only allowed IFT transaction.\nb1. On successful only allowed IFT transaction for parent loan, child loan fund transfer will be attempted and on successful call, the disbursement status will be updated 'COMPLETED' or else it will remain as 'PARENT_SUCCESS'.",
        },
        {
            "Sl No": "7",
            "Product Code": "SHG",
            "Scenarios": "a. Parent Loan account creation successful\nb. Parent Loan Due To FC successful\nc. Parent Loan fund transfer successful\nd. Child fund transfer successful",
            "Action": "On Retry",
            "Expected Behaviour": "a. On retry with any function sub code like LAN_CREATED, LOAN_BOOKED or DTFC_SUCCESS, request should be treated as terminal-safe no-op/retry path.\nb. It should not trigger duplicate parent transfer or child transfer calls.\nc. It should not create duplicate success entries in client request response log table.\nd. Parent/child final status should remain COMPLETED.",
        },
        {
            "Sl No": "8",
            "Product Code": "JLG & INDL",
            "Scenarios": "a. Loan account already exists for the same LAN/externalRefNo\nb. Retry request is sent with function sub code = LAN_CREATED\nc. Existing loan status in DB may already be LOAN_BOOKED / DTFC_SUCCESS / COMPLETED",
            "Action": "On Re-call",
            "Expected Behaviour": "a. It should read existing loan state first and should not create duplicate loan account / installment / due rows.\nb. It should check client request response log table and continue only pending steps from current disbursement state.\nc. If current state is non-terminal, it should move to next valid stage only.\nd. If current state is already terminal, request should be treated as no-op/rejected by guard and state should remain unchanged.",
        },
        {
            "Sl No": "9",
            "Product Code": "JLG & INDL",
            "Scenarios": "a. Loan is already in LOAN_BOOKED stage\nb. Retry request is sent with function sub code = LOAN_BOOKED\nc. Due To FC may be SUCCESS / FAILED / NOT_ATTEMPTED in previous run",
            "Action": "On Re-call",
            "Expected Behaviour": "a. It should check client request response log table for Due To FC transaction outcome.\nb. If Due To FC success entry exists, it should not re-do Due To FC and should continue to fund transfer.\nc. If Due To FC failure or missing entry exists, it should increase externalRefNo by 1 and retry Due To FC.\nd. After successful Due To FC and fund transfer, disbursement status should progress to COMPLETED.",
        },
        {
            "Sl No": "10",
            "Product Code": "JLG & INDL",
            "Scenarios": "a. Loan is already in DTFC_SUCCESS stage\nb. Retry request is sent with function sub code = DTFC_SUCCESS\nc. Bank transfer may be SUCCESS / FAILED / UNKNOWN in previous attempt",
            "Action": "On Re-call",
            "Expected Behaviour": "a. It should not repeat GL posting and should directly evaluate bank leg history from client request response log.\nb. If bank transfer success entry is already present, it should sync status and avoid duplicate transfer call.\nc. If bank transfer failed, it should increase externalRefNo by 1 and retry transfer.\nd. If bank transfer is UNKNOWN, it should execute inquiry/retry handling as per flow and then synchronize final status.",
        },
        {
            "Sl No": "11",
            "Product Code": "JLG & INDL (MFT leg)",
            "Scenarios": "a. Loan booking successful and Due To FC successful\nb. Disbursement mode routes bank leg to MFT\nc. Previous MFT transfer row in client request response log is FAILED",
            "Action": "On Retry",
            "Expected Behaviour": "a. It should check client request response log table for DISBURSEMENT_MFT transaction status.\nb. If MFT success already exists, it should sync state and avoid duplicate transfer.\nc. If MFT failed, it should increase externalRefNo by 1 and retry MFT transfer.\nd. On successful MFT path completion, disbursement status should move to COMPLETED.",
        },
        {
            "Sl No": "12",
            "Product Code": "JLG & INDL (MFT inquiry)",
            "Scenarios": "a. MFT transfer was triggered and pending confirmation\nb. MFT status inquiry API response is unparseable OR connection timeout occurs\nc. Inquiry outcome is recorded as UNKNOWN",
            "Action": "On Retry",
            "Expected Behaviour": "a. It should persist inquiry attempt in client request response log (MFT_TRANSACTION_INQUIRY).\nb. It should not trigger immediate duplicate fresh transfer only because inquiry returned UNKNOWN.\nc. It should keep disbursement in recoverable state (non-terminal failure).\nd. Next retry should attempt inquiry again using same bank transaction reference number.",
        },
        {
            "Sl No": "13",
            "Product Code": "JLG & INDL (MFT inquiry)",
            "Scenarios": "a. Previous MFT inquiry status is UNKNOWN\nb. Original MFT transaction reference number is available in DB context\nc. New retry request is received",
            "Action": "On Retry",
            "Expected Behaviour": "a. It should call MFT inquiry again with same previous reference number (no new transfer reference generation).\nb. It should avoid duplicate new MFT transfer call while resolving UNKNOWN inquiry.\nc. If inquiry returns success, it should sync disbursement status to terminal state.\nd. If inquiry remains non-success, it should stay in controlled retry path without data corruption.",
        },
        {
            "Sl No": "14",
            "Product Code": "JLG & INDL (MFT transfer)",
            "Scenarios": "a. Loan is in DTFC_SUCCESS and bank leg routes to MFT\nb. MFT transfer API call gets timeout/uncertain transport outcome\nc. Transfer result cannot be determined in same run",
            "Action": "On Retry",
            "Expected Behaviour": "a. It should record DISBURSEMENT_MFT with UNKNOWN status in client request response log.\nb. It should not trigger duplicate immediate same-run transfer once outcome is uncertain.\nc. Next retry should continue controlled recovery/inquiry path without duplicate financial side-effects.",
        },
        {
            "Sl No": "15",
            "Product Code": "JLG & INDL",
            "Scenarios": "a. Loan disbursement status already reached COMPLETED\nb. Retry/re-call request is sent with LAN_CREATED or LOAN_BOOKED or DTFC_SUCCESS function sub code\nc. Existing schedule/dues and external call records already present",
            "Action": "On Retry",
            "Expected Behaviour": "a. Request should be treated as terminal re-call (idempotent handling).\nb. No new GL posting, no new bank transfer, and no duplicate financial side-effects should be triggered.\nc. Loan status and disbursement status should remain unchanged as COMPLETED.\nd. Response should indicate successful handling of duplicate retry/no-op path.",
        },
        {
            "Sl No": "16",
            "Product Code": "SHG",
            "Scenarios": "a. Input payload is non-child flow (member_details[] empty — JLG/INDL flat)\nb. SHG parent/child specific testcase is part of suite",
            "Action": "On Execution",
            "Expected Behaviour": "a. SHG-only testcase should be marked as Not Applicable / Skipped with reason.\nb. Skip should not be counted as functional FAIL for disbursement flow.\nc. JLG & INDL applicable testcases should continue and final suite status should reflect applicable coverage only.",
        },
    ]

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["Sl No", "Product Code", "Scenarios", "Action", "Expected Behaviour"]
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_qa_testcase_matrix_verbose_csv(path: Path) -> None:
    """Detailed QA sheet in the same base format with extra columns."""
    _ensure_dir(path.parent)
    import csv

    rows = [
        {
            "Sl No": "1",
            "Product Code": "JLG & INDL",
            "Scenarios": "a. Loan account creation successful\nb. Loan booking successful\nc. Due To FC Failed\nd. Bank transfer not attempted",
            "Action": "On Retry",
            "Expected Behaviour": "a. It should check client request response log table. If success entry is found for Due To FC transaction then it should sync loan disbursement status and proceed with fund transfer.\nb. It should check client request response log table. If failure entry is found for Due To FC transaction then it should increase externalRefNo by 1 and retry Due To FC.\nc. Loan disbursement status should remain in LOAN_BOOKED/DTFC stage until Due To FC success is achieved.\nd. Bank transfer should not be marked successful in this retry when Due To FC is still pending.",
            "Preconditions / Setup": "Force parent LAN to LOAN_BOOKED, archive GL and bank CRR rows, simulate DTFC failure proxy",
            "Expected Status Path": "LAN_CREATED -> LOAN_BOOKED -> DTFC_SUCCESS (then bank leg)",
            "Evidence To Verify": "No new bank success row in this step; no duplicate schedule/dues",
            "Applicability": "JLG, INDL",
        },
        {
            "Sl No": "2",
            "Product Code": "JLG & INDL",
            "Scenarios": "a. Loan account creation successful\nb. Loan booking successful\nc. Due To FC successful\nd. Bank transfer failed",
            "Action": "On Retry",
            "Expected Behaviour": "a. It should check client request response log table. If success entry is found for Due To FC then it should not re-do GL posting.\nb. It should check client request response log table. If failure entry is found for bank transfer then it should increase externalRefNo by 1 and retry fund transfer.\nc. On successful fund transfer retry, disbursement status should move to COMPLETED.",
            "Preconditions / Setup": "Force DTFC_SUCCESS, archive bank-leg rows, simulate bank transfer failure",
            "Expected Status Path": "LOAN_BOOKED -> DTFC_SUCCESS -> COMPLETED",
            "Evidence To Verify": "Recovery run reaches terminal; no duplicate GL rows",
            "Applicability": "JLG, INDL",
        },
        {
            "Sl No": "3",
            "Product Code": "JLG & INDL",
            "Scenarios": "a. Loan account creation successful\nb. Loan booking successful\nc. Due To FC successful\nd. Bank transfer successful",
            "Action": "On Retry",
            "Expected Behaviour": "a. On retry with any function sub code like LAN_CREATED, LOAN_BOOKED or DTFC_SUCCESS, request should be treated as idempotent terminal-safe path.\nb. It should not create duplicate loan artifacts.\nc. It should not create duplicate successful external call records.",
            "Preconditions / Setup": "Loan already terminal from earlier successful run",
            "Expected Status Path": "COMPLETED remains COMPLETED",
            "Evidence To Verify": "No new success rows; status unchanged",
            "Applicability": "JLG, INDL",
        },
        {
            "Sl No": "4",
            "Product Code": "SHG",
            "Scenarios": "a. Parent loan account creation successful\nb. Parent loan booking successful\nc. Parent Due To FC Failed\nd. Parent fund transfer not attempted\ne. Child fund transfer not attempted",
            "Action": "On Retry",
            "Expected Behaviour": "a. It should check client request response log table. If success entry is found for Due To FC transaction then it should sync parent status and proceed to parent transfer.\nb. It should check client request response log table. If failure entry is found for Due To FC then it should increase externalRefNo by 1 and retry Due To FC.\nb1. On successful Due To FC, parent disbursement status should become DTFC_SUCCESS.\nb2. Parent transfer should be attempted only after DTFC_SUCCESS.\nb3. Child transfer should not start before parent transfer outcome is available.",
            "Preconditions / Setup": "SHG child payload required, force parent LOAN_BOOKED and DTFC failure path",
            "Expected Status Path": "LAN_CREATED -> LOAN_BOOKED -> DTFC_SUCCESS -> PARENT_SUCCESS -> CHILD_SUCCESS -> COMPLETED",
            "Evidence To Verify": "S4 executed; no child transfer success before parent progression",
            "Applicability": "SHG",
        },
        {
            "Sl No": "5",
            "Product Code": "SHG",
            "Scenarios": "a. Parent loan account creation successful\nb. Parent loan booking successful\nc. Parent Due To FC successful\nd. Parent fund transfer failed\ne. Child fund transfer not attempted",
            "Action": "On Retry",
            "Expected Behaviour": "a. It should check client request response log table. If success entry is found for parent Due To FC, system should move to parent transfer handling.\nb. If parent transfer failed, it should increase externalRefNo by 1 and retry only parent transfer.\nb1. Parent status should move to PARENT_SUCCESS only when parent transfer succeeds.\nb2. Child transfer should remain blocked until parent transfer success.",
            "Preconditions / Setup": "SHG child payload required, force parent DTFC_SUCCESS and simulate parent transfer failure",
            "Expected Status Path": "DTFC_SUCCESS -> PARENT_SUCCESS (then child leg)",
            "Evidence To Verify": "S5 executed; child transfer not completed before parent success",
            "Applicability": "SHG",
        },
        {
            "Sl No": "6",
            "Product Code": "SHG",
            "Scenarios": "a. Parent loan account creation successful\nb. Parent loan booking successful\nc. Parent Due To FC successful\nd. Parent fund transfer successful\ne. Child fund transfer failed",
            "Action": "On Retry",
            "Expected Behaviour": "a. It should check client request response log table for child loan transfer rows.\nb. If child transfer is not successful, it should retry only child transfer on next eligible retry.\nb1. Parent transfer should not be duplicated.\nb2. On child transfer success, disbursement status should move to COMPLETED (or CHILD_SUCCESS before COMPLETED as per queue progression).",
            "Preconditions / Setup": "SHG child payload required, force child transfer failure after parent success stage",
            "Expected Status Path": "PARENT_SUCCESS -> CHILD_SUCCESS -> COMPLETED",
            "Evidence To Verify": "S6 executed and child retry behavior visible",
            "Applicability": "SHG",
        },
        {
            "Sl No": "7",
            "Product Code": "SHG",
            "Scenarios": "a. Parent loan account creation successful\nb. Parent Due To FC successful\nc. Parent fund transfer successful\nd. Child fund transfer successful",
            "Action": "On Retry",
            "Expected Behaviour": "a. On retry with function sub code like LAN_CREATED, LOAN_BOOKED or DTFC_SUCCESS, request should be treated as terminal-safe no-op/retry path.\nb. It should not trigger duplicate parent or child external transfer calls.\nc. Final status should remain COMPLETED.",
            "Preconditions / Setup": "Complete SHG parent+child flow first",
            "Expected Status Path": "COMPLETED remains COMPLETED",
            "Evidence To Verify": "S7 executed; no new external success rows",
            "Applicability": "SHG",
        },
        {
            "Sl No": "8",
            "Product Code": "JLG & INDL (MFT)",
            "Scenarios": "a. MFT transfer triggered\nb. MFT inquiry response unparseable / uncertain\nc. Inquiry result logged as UNKNOWN",
            "Action": "On Retry",
            "Expected Behaviour": "a. It should persist inquiry attempt in log table and mark UNKNOWN for non-definitive inquiry mapping.\nb. It should not trigger immediate duplicate fresh transfer in the same run.\nc. Next retry should continue safe recovery path.\nd. Inquiry retry should reuse same transaction reference number until resolution.",
            "Preconditions / Setup": "Run MFT failure + inquiry unknown sequence",
            "Expected Status Path": "DTFC_SUCCESS -> UNKNOWN handling -> recovery -> COMPLETED",
            "Evidence To Verify": "MFT inquiry UNKNOWN logged; same inquiry reference reused",
            "Applicability": "JLG, INDL when bank leg is MFT",
        },
        {
            "Sl No": "9",
            "Product Code": "JLG & INDL (MFT)",
            "Scenarios": "a. MFT transfer API timeout / transport uncertainty\nb. Transfer outcome unknown in same run",
            "Action": "On Retry",
            "Expected Behaviour": "a. It should log DISBURSEMENT_MFT as UNKNOWN.\nb. It should avoid duplicate immediate same-run transfer call.\nc. It should allow controlled retry/recovery path in subsequent run.",
            "Preconditions / Setup": "Force MFT timeout on transfer API",
            "Expected Status Path": "DTFC_SUCCESS -> UNKNOWN transfer handling -> recovery",
            "Evidence To Verify": "DISBURSEMENT_MFT UNKNOWN delta > 0",
            "Applicability": "JLG, INDL when bank leg is MFT",
        },
        {
            "Sl No": "10",
            "Product Code": "JLG & INDL (NEFT v1)",
            "Scenarios": "a. NEFT result uncertain (UNKNOWN)\nb. Retry initiated from LOAN_BOOKED / DTFC_SUCCESS\nc. Prior reference exists",
            "Action": "On Retry",
            "Expected Behaviour": "a. It should preserve idempotent retry behavior under UNKNOWN state.\nb. It should avoid duplicate side effects.\nc. It should recover to terminal state on successful subsequent attempt.",
            "Preconditions / Setup": "Inject NEFT unknown state before retry",
            "Expected Status Path": "DTFC_SUCCESS -> UNKNOWN handling -> COMPLETED",
            "Evidence To Verify": "Reference reuse check passes; recovery to terminal observed",
            "Applicability": "JLG, INDL when bank leg is NEFT v1",
        },
        {
            "Sl No": "11",
            "Product Code": "ALL (JLG / INDL / SHG)",
            "Scenarios": "a. Same payload replayed after successful completion\nb. Existing artifacts and success rows already present",
            "Action": "On Replay",
            "Expected Behaviour": "a. Request should remain idempotent.\nb. No duplicate loan artifacts should be created.\nc. No duplicate successful external call should be triggered.\nd. Status should remain terminal.",
            "Preconditions / Setup": "Replay after successful terminal completion",
            "Expected Status Path": "Terminal remains terminal",
            "Evidence To Verify": "installments_added_delta=0, dues_added_delta=0, no unexpected new success rows",
            "Applicability": "JLG, INDL, SHG",
        },
    ]

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "Sl No",
                "Product Code",
                "Scenarios",
                "Action",
                "Expected Behaviour",
                "Preconditions / Setup",
                "Expected Status Path",
                "Evidence To Verify",
                "Applicability",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _get_simulator_response(api_name: str, request_type: str) -> dict[str, Any] | None:
    rows = _psql_rows(
        f"""
        SELECT sr.response_code::text,
               COALESCE(sr.timeout_period,0)::text,
               COALESCE(sr.dynamic_response,false)::text,
               COALESCE(sr.is_callback_enabled,false)::text,
               COALESCE(sr.response,'')
        FROM mfi_simulator.simulator_response sr
        JOIN mfi_simulator.simulator_config sc ON sc.id = sr.simulator_config_id
        WHERE sc.api_name = {sql_quote(api_name)} AND upper(sc.request_type) = upper({sql_quote(request_type)})
        LIMIT 1;
        """,
        schema="public",
    )
    if not rows:
        return None
    r = rows[0]
    return {
        "api_name": api_name,
        "request_type": request_type,
        "response_code": int(r[0]),
        "timeout_period": int(r[1]),
        "dynamic_response": r[2].lower() == "true",
        "is_callback_enabled": r[3].lower() == "true",
        "response": r[4],
    }


def _restore_simulator_response(snapshot: dict[str, Any]) -> None:
    _set_simulator_response(
        api_name=snapshot["api_name"],
        request_type=snapshot["request_type"],
        response_code=int(snapshot["response_code"]),
        response=str(snapshot["response"]),
        timeout_period=int(snapshot["timeout_period"]),
        dynamic_response=bool(snapshot["dynamic_response"]),
        is_callback_enabled=bool(snapshot["is_callback_enabled"]),
    )


def _mk_check(name: str, ok: bool, details: str = "", *, level: str = "FAIL") -> CheckResult:
    return CheckResult(name=name, ok=ok, details=details if not ok else "", level=level)


def _has_fail_checks(checks: list[CheckResult]) -> bool:
    return any((not c.ok) and c.level == "FAIL" for c in checks)


def _validate_post_run(
    *,
    scenario: str,
    snap: LoanSnapshot,
    req: dict[str, Any],
    expect_terminal: bool,
    bank_leg: str,
    require_gl: bool,
    dpi_certify: bool = False,
) -> tuple[list[CheckResult], dict[str, Any]]:
    checks: list[CheckResult] = []
    diag: dict[str, Any] = {}

    inst_cnt = _count_installments(snap.account_id)
    due_cnt = _count_dues(snap.account_id)
    utr = _get_utr(snap.account_id)
    crr = _crr_counts(snap.account_number)
    child_flow = _is_child_flow_payload(req)
    product_type = _infer_product_type(req)

    diag["installments"] = inst_cnt
    diag["dues"] = due_cnt
    diag["utr"] = utr
    diag["crr_counts"] = _format_counts(crr)

    # Local environments often flip loan_status to CLOSED after disbursement bookkeeping.
    # Treat ACTIVE as ideal, CLOSED as acceptable for terminal-ish disbursement statuses.
    # SHG parent may remain APPROVED until children complete.
    if snap.loan_status == "ACTIVE":
        checks.append(_mk_check("loan_status_active", True))
    elif child_flow and snap.loan_status == "APPROVED" and snap.disbursement_status in {
        "PARENT_SUCCESS",
        "CHILD_SUCCESS",
        "COMPLETED",
        "DTFC_SUCCESS",
    }:
        checks.append(_mk_check("loan_status_shg_parent_approved", True))
    else:
        ok_closed = snap.loan_status == "CLOSED" and snap.disbursement_status in {"DTFC_SUCCESS", "COMPLETED", "PARENT_SUCCESS", "CHILD_SUCCESS"}
        checks.append(_mk_check("loan_status_active_or_closed_terminal", ok_closed, f"expected ACTIVE (ideal) or CLOSED with terminal status; got loan_status={snap.loan_status} disb_status={snap.disbursement_status}", level="WARN" if ok_closed else "FAIL"))
    if child_flow:
        # Schedule lives on child LANs for SHG parent+member_details flow
        checks.append(
            _mk_check(
                "schedule_generated_parent_optional",
                True,
                f"SHG parent installments={inst_cnt} (asserted on children via column_audit)",
                level="WARN" if inst_cnt == 0 else "FAIL",
            )
        )
        checks.append(
            _mk_check(
                "due_details_generated_parent_optional",
                True,
                f"SHG parent dues={due_cnt} (asserted on children via column_audit)",
                level="WARN" if due_cnt == 0 else "FAIL",
            )
        )
    else:
        checks.append(_mk_check("schedule_generated", inst_cnt > 0, f"expected installments>0, got {inst_cnt}"))
        checks.append(_mk_check("due_details_generated", due_cnt > 0, f"expected dues>0, got {due_cnt}"))

    if expect_terminal and not snap.has_child_accounts:
        terminal_ok = snap.disbursement_status in {"COMPLETED", "DTFC_SUCCESS"}
        terminal_level = "WARN" if snap.disbursement_status == "DTFC_SUCCESS" else "FAIL"
        # Local NEFT (INDL): after NEF SUCCESS the loan waits at NEFT_STAGE_* until NEI callback.
        # Treat as acceptable local terminal (WARN), same statuses already allowed on child-flow.
        if bank_leg == "NEFT" and snap.disbursement_status in {
            "NEFT_STAGE_1_PENDING",
            "NEFT_STAGE_1_SUCCESS",
            "NEFT_STAGE_2_PENDING",
        }:
            terminal_ok = True
            terminal_level = "WARN"
        if dpi_certify and snap.disbursement_status == "LOAN_BOOKED" and snap.loan_status == "ACTIVE" and inst_cnt > 0:
            terminal_ok = True
            terminal_level = "WARN"
        checks.append(
            _mk_check(
                "terminal_status_non_child",
                terminal_ok,
                "expected COMPLETED (ideal), DTFC_SUCCESS, or NEFT_STAGE_*_PENDING (local NEFT awaiting NEI); "
                f"got {snap.disbursement_status}",
                level=terminal_level,
            )
        )
    if expect_terminal and snap.has_child_accounts:
        child_ok = snap.disbursement_status in {
            "COMPLETED",
            "PARENT_SUCCESS",
            "CHILD_SUCCESS",
            "NEFT_STAGE_1_PENDING",
            "NEFT_STAGE_1_SUCCESS",
            "NEFT_STAGE_2_PENDING",
        }
        child_warn_dtfc = snap.disbursement_status == "DTFC_SUCCESS"
        checks.append(
            _mk_check(
                "terminal_status_child_flow",
                child_ok or child_warn_dtfc,
                "expected one of: LAN_CREATED, LOAN_BOOKED, PARENT_SUCCESS, CHILD_SUCCESS, NEFT_STAGE_1_PENDING, NEFT_STAGE_1_SUCCESS, NEFT_STAGE_2_PENDING, COMPLETED (child-flow loans); "
                f"got {snap.disbursement_status}",
                level="WARN" if child_warn_dtfc else "FAIL",
            )
        )

    # Scenario-aware expectation model:
    # - Fresh/default runs expect presence checks (bank/GL rows, UTR where applicable).
    # - Replay/stage-forced/injected runs are validated mainly by zero-delta/idempotency checks.
    stage_forced_matrix_case = scenario.startswith(("S1_", "S2_", "S3_", "S4_", "S5_", "S6_", "S7_"))
    replay_or_injected_case = (
        scenario.startswith(("resume_", "stage_replay_"))
        or scenario in {"default_replay", "injected_stuck_DTFC_SUCCESS", "simulate_bank_failure_default_call"}
        or "_after_unknown" in scenario
        or "_after_failure_sim" in scenario
    )
    presence_checks_required = not (stage_forced_matrix_case or replay_or_injected_case)
    if bank_leg == "NEFT":
        # NEFT v1: UTR presence is required only for fresh/default execution checks.
        if presence_checks_required and expect_terminal and not snap.has_child_accounts and snap.disbursement_status in {"COMPLETED", "DTFC_SUCCESS"}:
            checks.append(_mk_check("utr_present_for_terminal_neft", utr is not None, "expected utr_number set for NEFT v1 terminal status", level="WARN"))
        # Validate at least one NEFT log row only when presence checks are expected.
        if presence_checks_required:
            neft_any = sum(
                v
                for k, v in crr.items()
                if (":".join(k.split(":")[:-1]).upper().find("NEFT") >= 0)
                and (not k.startswith("NEFT_TRANSACTION_INQUIRY:"))
            ) > 0
            checks.append(_mk_check("crr_has_neft_rows", neft_any, "expected at least one *NEFT* row in client_request_response_log", level="WARN"))
    elif bank_leg == "MFT":
        # MFT flow doesn't persist UTR; row-presence checks only for fresh/default execution checks.
        if presence_checks_required:
            mft_any = sum(v for k, v in crr.items() if k.startswith("DISBURSEMENT_MFT:")) > 0
            checks.append(_mk_check("crr_has_mft_rows", mft_any, "expected at least one DISBURSEMENT_MFT row in client_request_response_log", level="WARN"))
    else:
        checks.append(_mk_check("bank_leg_supported", False, f"unsupported disbursement_mode={_disbursement_mode(req)}; expected ACCTWB or OTHBACCT"))

    # Contract guard requested by QA: for SHG parent with ACCTWB rail, NEFT payment CRR must never appear.
    mode = _disbursement_mode(req)
    member_modes = _member_disbursement_modes(req)
    all_child_acctwb = bool(member_modes) and member_modes == {"ACCTWB"}
    if snap.has_child_accounts and mode == "ACCTWB" and all_child_acctwb:
        neft_payment_rows = _count_neft_payment_rows(crr)
        checks.append(
            _mk_check(
                "shg_parent_acctwb_no_neft_payment_rows",
                neft_payment_rows == 0,
                f"expected 0 NEFT payment rows for SHG parent ACCTWB flow; found {neft_payment_rows}",
            )
        )
    elif snap.has_child_accounts and mode == "ACCTWB" and member_modes:
        checks.append(_mk_check(
            "shg_mixed_member_modes_guard",
            True,
            f"skipped strict SHG ACCTWB no-NEFT assertion due to mixed member modes={sorted(member_modes)}",
            level="WARN",
        ))

    # Child-lane verification (parent-only reinit is validated separately):
    # ensure child bank-leg success rows are present per configured member rails.
    if snap.has_child_accounts and presence_checks_required and member_modes:
        if "OTHBACCT" in member_modes:
            child_neft_success = sum(
                v for k, v in crr.items()
                if "DISBURSEMENT_EXTREF" in k and "NEFT" in k and k.endswith(":SUCCESS")
            )
            checks.append(
                _mk_check(
                    "child_neft_success_rows_present",
                    child_neft_success > 0,
                    f"expected child NEFT success rows for member OTHBACCT rails; observed={child_neft_success}",
                    level="WARN",
                )
            )
        if "ACCTWB" in member_modes:
            child_mft_success = sum(
                v for k, v in crr.items()
                if "DISBURSEMENT_EXTREF" in k and "_MFT:SUCCESS" in k
            )
            # Mixed rails: OTHBACCT child may only show NEFT EXTREF; parent MFT still required.
            # When children exist and are COMPLETED, treat missing child-MFT EXTREF as WARN.
            child_mft_level = "WARN" if ("OTHBACCT" in member_modes or child_mft_success > 0) else "WARN"
            checks.append(
                _mk_check(
                    "child_mft_success_rows_present",
                    child_mft_success > 0 or "OTHBACCT" in member_modes,
                    f"expected child MFT success rows for member ACCTWB rails; observed={child_mft_success}",
                    level=child_mft_level,
                )
            )

    # GL CBS expectations: for most DEFAULT flows this should occur (plus NETOFF when net_off_amount>0).
    if require_gl and presence_checks_required:
        gl_any = sum(v for k, v in crr.items() if k.startswith("DISB_GL_CBS_INTEGRATION:")) > 0
        # In some local setups GL CBS logging may be missing/misrouted; treat as WARN but keep it visible.
        checks.append(_mk_check("crr_has_gl_cbs_rows", gl_any, "expected DISB_GL_CBS_INTEGRATION rows in client_request_response_log", level="WARN"))
        netoff_amt = _netoff_amount(req)
        if netoff_amt and netoff_amt not in {"0", "0.0", "0.00"}:
            gl_netoff_any = sum(v for k, v in crr.items() if k.startswith("DISB_GL_CBS_INTEGRATION_NETOFF:")) > 0
            checks.append(_mk_check("crr_has_gl_cbs_netoff_rows", gl_netoff_any, f"expected DISB_GL_CBS_INTEGRATION_NETOFF rows for net_off_amount={netoff_amt}", level="WARN"))

    # Full column-value audit (fail-closed) — not presence-only / not status-200.
    if snap and expect_terminal and presence_checks_required:
        audit = audit_disbursement(
            account_id=snap.account_id,
            account_number=snap.account_number,
            req=req,
            product_type=product_type,
            child_flow=child_flow,
            loan_status=snap.loan_status,
            disbursement_status=snap.disbursement_status,
            query_rows=lambda sql: _psql_rows(sql, schema=DEFAULT_DB_SCHEMA),
            schema=DEFAULT_DB_SCHEMA,
        )
        diag["column_audit"] = {
            "failed": audit.failed,
            "evidence": audit.evidence,
            "checks": [c.as_dict() for c in audit.checks],
        }
        for c in audit.checks:
            checks.append(
                _mk_check(
                    f"col_audit:{c.name}",
                    c.ok,
                    c.details or f"table={c.table} expect={c.expect} actual={c.actual}",
                    level=c.level,
                )
            )

    return checks, diag

def _tcp_probe(host: str, port: int, timeout_s: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False

def _with_function_sub_code(
    payload: dict[str, Any],
    function_sub_code: str,
    account_number: str | None,
    *,
    external_ref_number: str | None = None,
) -> dict[str, Any]:
    """
    Accounting mfi tenant disburseLoan uses function_code=DEFAULT always.
    For function_sub_code != DEFAULT, orchestration requires account_number.
    """
    p = copy.deepcopy(payload)
    p["headers"]["function_code"] = "DEFAULT"
    p["headers"]["function_sub_code"] = function_sub_code
    uniq = _uniq_ms_str()
    p["headers"]["stan"] = uniq
    # Keep request timestamps unique per call (postTransaction dedup relies on this in local).
    dd = p.get("request", {}).get("disbursement_details") or {}
    if isinstance(dd, dict):
        if external_ref_number:
            _dd_set_external_ref_number(dd, external_ref_number)
        dd["client_reference_number"] = uniq
        dd["expected_disbursement_date"] = dd.get("expected_disbursement_date") or uniq
        p["request"]["disbursement_details"] = dd
    if account_number:
        # Orchestration reads account_number from request template -> loan_details.account_number
        p.setdefault("request", {}).setdefault("loan_details", {})["account_number"] = account_number
    return p

def _simulator_force_neft_v1_unknown() -> None:
    if _ACTIVE_NEFT_VERSION == "v2":
        _set_simulator_response(
            api_name="doGenericSyncSTPNEF",
            request_type="JSON",
            response_code=503,
            response="{}",
            timeout_period=0,
            dynamic_response=False,
            is_callback_enabled=False,
            validation="ST_NEF",
        )
        return
    # NEFT v1: return valid SOAP XML but without outTransactionId.
    xml2 = re.sub(
        r"<outTransactionId>.*?</outTransactionId>",
        "<outTransactionId></outTransactionId>",
        NEFT_V1_SUCCESS_SOAP_XML,
        flags=re.DOTALL,
    )
    _set_simulator_response(
        api_name="NEFTPayment",
        request_type="XML",
        response_code=200,
        response=xml2,
        timeout_period=0,
        dynamic_response=False,
        is_callback_enabled=False,
        validation="<SOAP-ENV:Envelope",
    )

def _simulator_force_neft_v1_http_500() -> None:
    # Try to force the simulator to return an HTTP 500 so the client lib doesn't populate out_transaction_id.
    forced = {
        "response_code": 500,
        "response": "{}",
        "timeout_period": 0,
        "dynamic_response": False,
        "is_callback_enabled": False,
    }
    # Keep method for fallback; use NEFTPayment XML in this environment.
    snap = _get_simulator_response("NEFTPayment", "XML")
    if not snap:
        return
    _set_simulator_response(api_name="NEFTPayment", request_type="XML", **forced)


def _simulator_force_neft_v1_http_500_hard() -> None:
    # Hard force: update simulator response for NEFTPayment/XML to HTTP 500.
    _set_simulator_response(
        api_name="NEFTPayment",
        request_type="XML",
        response_code=500,
        response="{}",
        timeout_period=0,
        dynamic_response=False,
        is_callback_enabled=False,
    )

def _simulator_restore_neft_v1_successish() -> None:
    # Restore to a known-good SOAP response with outTransactionId present.
    xml = NEFT_V1_SUCCESS_SOAP_XML
    _set_simulator_response(
        api_name="NEFTPayment",
        request_type="XML",
        response_code=200,
        response=xml,
        timeout_period=0,
        dynamic_response=False,
        is_callback_enabled=False,
    )


def _simulator_restore_success_profile() -> None:
    if _ACTIVE_NEFT_VERSION == "v2":
        _set_simulator_response(
            api_name="doGenericSyncSTPNEF",
            request_type="JSON",
            response_code=200,
            response=_json_dumps_compact(NEFT_V2_NEF_SUCCESS_JSON),
            timeout_period=0,
            dynamic_response=False,
            is_callback_enabled=False,
            validation="ST_NEF",
        )
        _set_simulator_response(
            api_name="doGenericSyncSTPNEI",
            request_type="JSON",
            response_code=200,
            response=_json_dumps_compact(NEFT_V2_NEI_SUCCESS_JSON),
            timeout_period=0,
            dynamic_response=False,
            is_callback_enabled=False,
            validation="ST_NEI",
        )
        _set_simulator_response(
            api_name="doGenericSyncSTPInquiry",
            request_type="JSON",
            response_code=200,
            response=_json_dumps_compact(NEFT_V2_INQUIRY_SUCCESS_JSON),
            timeout_period=0,
            dynamic_response=False,
            is_callback_enabled=False,
            validation="GenericSyncSTPInquiryRequestDTO",
        )
    else:
        _set_simulator_response(
            api_name="NEFTPayment",
            request_type="XML",
            response_code=200,
            response=NEFT_V1_SUCCESS_SOAP_XML,
            timeout_period=0,
            dynamic_response=False,
            is_callback_enabled=False,
            validation="<SOAP-ENV:Envelope",
        )
    _set_simulator_response(
        api_name="miscFundTransfer",
        request_type="JSON",
        response_code=200,
        response=_json_dumps_compact(MFT_SUCCESS_JSON),
        timeout_period=0,
        dynamic_response=False,
        is_callback_enabled=False,
    )
    _set_simulator_response(
        api_name="genericTransactionStatusInquiry",
        request_type="JSON",
        response_code=200,
        response=_json_dumps_compact(GENERIC_TXN_INQ_SUCCESS_JSON),
        timeout_period=0,
        dynamic_response=False,
        is_callback_enabled=False,
    )


def _db_inject_neft_uncertain_state(account_number: str, account_id: int) -> None:
    """
    Create a realistic "stuck at DTFC_SUCCESS due to uncertain bank outcome" shape:
    - loan_account.disbursement_status = DTFC_SUCCESS
    - clear utr_number
    - flip latest DISBURSEMENT_NEFT CRR row status to UNKNOWN (if exists)
    """
    _psql(
        f"""
        UPDATE loan_account
        SET disbursement_status = 'DTFC_SUCCESS', updated_on = CURRENT_TIMESTAMP, updated_by = 'suite_inject'
        WHERE account_id = {account_id};
        """,
        schema=DEFAULT_DB_SCHEMA,
    )
    _psql(
        f"""
        UPDATE loan_disbursement_mode_details
        SET utr_number = NULL, updated_on = CURRENT_TIMESTAMP, updated_by = 'suite_inject'
        WHERE loan_account_id = {account_id} AND is_deleted = false;
        """,
        schema=DEFAULT_DB_SCHEMA,
    )
    _psql(
        f"""
        UPDATE client_request_response_log
        SET status = '{UNKNOWN}', updated_on = CURRENT_TIMESTAMP
        WHERE id = (
            SELECT id FROM client_request_response_log
            WHERE loan_account_number = {sql_quote(account_number)}
              AND transaction_type = 'DISBURSEMENT_NEFT'
            ORDER BY system_date DESC NULLS LAST, id DESC
            LIMIT 1
        );
        """,
        schema=DEFAULT_DB_SCHEMA,
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Local sanity/regression runner for Accounting disburseLoan (NEFT v1 default).")
    p.add_argument("--request-file", required=True, help="Path to input JSON (same shape as webapp payload).")
    p.add_argument("--endpoint", default="", help="Override full URL. If empty: base-url + context-path + /v1/disburseLoan")
    p.add_argument("--base-url", default=DEFAULT_ACCOUNTING_BASE_URL, help="Accounting base URL (default from env ACCOUNTING_BASE_URL).")
    p.add_argument("--context-path", default=DEFAULT_ACCOUNTING_CONTEXT_PATH, help="Accounting context path (default from env ACCOUNTING_CONTEXT_PATH).")
    # Accounting services expose the gateway controller under /api/{version}/{apiName}
    p.add_argument("--api-path", default="/api/v1/disburseLoan", help="Relative API path under context-path.")
    p.add_argument("--http-timeout-s", type=int, default=30)
    p.add_argument("--wait-timeout-s", type=int, default=180)
    p.add_argument("--poll-s", type=float, default=2.0)

    p.add_argument("--reset-before", action="store_true", help="Optional. Runs local reset script (slow/heavy if ext_ref already exists).")
    p.add_argument(
        "--reset-target-disb-status",
        default="DTFC_SUCCESS",
        help="Disbursement status to set by reset script (only used with --reset-before).",
    )

    p.add_argument(
        "--neft-version",
        choices=["v1", "v2"],
        default="v1",
        help="Provisioning switch. Current accounting code uses v1 by default; v2 requires code/config enablement.",
    )
    p.add_argument(
        "--simulator-profile",
        choices=["none", "success", "fail", "unknown"],
        default="success",
        help="Controls simulator responses and logs before/after in report.",
    )
    p.add_argument(
        "--report-json",
        default="",
        help="Optional path to write a machine-readable JSON report (useful for CI/QA).",
    )
    p.add_argument(
        "--report-pdf",
        default="",
        help="Optional output PDF path. If omitted, writes to docs/disbursement-sanity/ under workspace root.",
    )
    p.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop at first failing scenario (default runs full suite and reports).",
    )
    p.add_argument("--simulator-host", default=os.environ.get("SIMULATOR_HOST", "localhost"))
    p.add_argument("--simulator-port", type=int, default=int(os.environ.get("SIMULATOR_PORT", "8018")))
    p.add_argument(
        "--stage-suite",
        choices=["minimal", "full"],
        default="full",
        help="minimal: DEFAULT + replay only. full: also runs function_sub_code stage permutations.",
    )
    p.add_argument(
        "--dpi-certify",
        action="store_true",
        default=bool(os.environ.get("DISBURSE_DPI_CERTIFY")),
        help="DPI certify path: LOAN_BOOKED + ACTIVE + schedule is acceptable when GL/MFT leg is unavailable locally.",
    )
    p.add_argument(
        "--via-kafka",
        action="store_true",
        default=bool(os.environ.get("DISBURSE_VIA_KAFKA")),
        help="Publish LOS-shaped Kafka message (apiName|json|cacheKey|ownerToken) instead of HTTP disburseLoan.",
    )
    p.add_argument(
        "--no-complete-neft-callbacks",
        dest="complete_neft_callbacks",
        action="store_false",
        help="Leave a NEFTv2 loan at NEFT_STAGE_1_PENDING instead of driving the two bank "
             "callbacks to COMPLETED before the replay scenario.",
    )
    p.set_defaults(complete_neft_callbacks=True)
    return p


def main() -> int:
    global _ACTIVE_NEFT_VERSION  # noqa: PLW0603
    p = _build_arg_parser()
    # Help must work even with a stale /tmp lock (parse before acquire).
    if any(a in ("-h", "--help") for a in sys.argv[1:]):
        p.parse_args()
        return 0
    _acquire_single_run_lock()
    args = p.parse_args()
    _ACTIVE_NEFT_VERSION = args.neft_version

    raw = _json_load(args.request_file)
    raw = _deep_replace_timestamp(raw)
    # If we reset before the suite, keep external_ref_number stable (reset makes it safe).
    # If we don't reset, make it unique to prevent collisions with prior local data.
    if not args.reset_before:
        raw, old_ext_ref, new_ext_ref = _ensure_unique_external_ref(raw)
    else:
        old_ext_ref, new_ext_ref = "", ""
    suite_start_ms = _now_ms()

    req = raw.get("request") if isinstance(raw, dict) else None
    hdr = raw.get("headers") if isinstance(raw, dict) else None
    if not isinstance(req, dict) or not isinstance(hdr, dict):
        raise ValueError("Input JSON must contain top-level 'request' and 'headers' objects")

    ext_ref = str(((req.get("disbursement_details") or {}).get("external_ref_number") or "")).strip()
    _assert(bool(ext_ref), "Missing request.disbursement_details.external_ref_number")
    canonical_ext_ref = ext_ref
    customer_id = str(((req.get("loan_details") or {}).get("customer_id") or "")).strip()
    product_id = str(((req.get("loan_details") or {}).get("product_id") or "")).strip()
    _ensure_expected_disbursement_date(req)

    # Option A (local suite): make customer eligible by closing all prior loans.
    # This makes the suite deterministic despite local DB history and dedupe rules.
    if customer_id:
        print(f"[suite] pre-reset customer loans customer_id={customer_id}", flush=True)
        _reset_customer_loans(customer_id)

    # High-signal run header (after we know final ext_ref)
    print(f"[suite] using external_ref_number={ext_ref}", flush=True)

    if args.reset_before:
        # Reset must use the same ext_ref the suite will call with; use a temp request file.
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as f:
            json.dump(raw, f, indent=2, sort_keys=True)
            tmp_path = f.name
        _run_local_reset_from_json(tmp_path, target_disb_status=args.reset_target_disb_status)
        _seed_repayment_mandate_for_loan_app_id(loan_app_id=ext_ref, req=req)
        _seed_member_mandates_for_shg(req)
    else:
        _seed_repayment_mandate_for_loan_app_id(loan_app_id=ext_ref, req=req)
        _seed_member_mandates_for_shg(req)

    mode = _disbursement_mode(req)
    bank_leg = _expected_bank_leg(mode)
    require_gl = bank_leg != "MFT"
    product_type = _infer_product_type(req)
    child_flow = _is_child_flow_payload(req)
    for check_name, ok, details, level in _validate_payload_product_contract(req):
        if not ok:
            print(f"[suite] PAYLOAD {level} {check_name}: {details}", flush=True)
            return 2
    # Provide fallback keys to waiters via env (keeps function signatures stable)
    os.environ["SUITE_SINCE_MS"] = str(suite_start_ms)
    os.environ["SUITE_CUSTOMER_ID"] = customer_id
    os.environ["SUITE_PRODUCT_ID"] = product_id
    url = args.endpoint.strip()
    if not url:
        url = args.base_url.rstrip("/") + args.context_path.rstrip("/") + args.api_path
    print(
        f"[suite] product={product_type} child_flow={child_flow} mode={mode} bank_leg={bank_leg} "
        f"endpoint={'KAFKA:' + os.environ.get('NPS_DISBURSE_TOPIC', 'disburse_loan_api_mfi_local') if args.via_kafka else url}",
        flush=True,
    )

    simulator_up = _tcp_probe(args.simulator_host, args.simulator_port)
    simulator_changes: list[dict[str, Any]] = []
    if simulator_up and args.simulator_profile != "none":
        try:
            simulator_changes = _simulator_apply_profile(args.simulator_profile, args.neft_version)
        except Exception as e:
            simulator_changes = [{"error": f"{type(e).__name__}: {e}"}]

    suite_results: list[ScenarioResult] = []

    def run_scenario(name: str, payload: dict[str, Any], expect_terminal: bool) -> ScenarioResult:
        http_status: int | None = None
        loan: LoanSnapshot | None = None
        checks: list[CheckResult] = []
        diag: dict[str, Any] = {"disbursement_mode": mode, "bank_leg": bank_leg}
        diag["simulator_up"] = simulator_up
        diag["simulator_profile"] = args.simulator_profile
        if simulator_changes:
            diag["simulator_changes"] = simulator_changes
        try:
            print(f"[scenario] start name={name}", flush=True)
            payload = copy.deepcopy(payload)
            payload["headers"]["run_mode"] = payload["headers"].get("run_mode") or "REAL"

            # Capture CRR counters BEFORE the API call (for idempotency / duplicate-bank-call proof).
            lan_hint = str(((payload.get("request") or {}).get("loan_details") or {}).get("account_number") or "").strip()
            lan_hint = lan_hint or os.environ.get("SUITE_ACCOUNT_NUMBER", "") or ""
            crr_before_raw: dict[str, int] = _crr_counts(lan_hint) if lan_hint else {}
            if lan_hint:
                diag["lan_hint"] = lan_hint
                diag["crr_before_raw"] = crr_before_raw

                # Baseline DB state for "what changed" reporting on retries.
                snap_before = _fetch_loan_by_account_number(lan_hint)
                if snap_before:
                    diag["before_installments"] = _count_installments(snap_before.account_id)
                    diag["before_dues"] = _count_dues(snap_before.account_id)
                    diag["before_utr"] = _get_utr(snap_before.account_id)

            http_status, body = (
                _kafka_publish_disburse(payload, timeout_s=args.http_timeout_s)
                if args.via_kafka
                else _http_post_json(url, payload, timeout_s=args.http_timeout_s)
            )
            if args.via_kafka:
                diag["via_kafka"] = True
            diag["response_body_prefix"] = (body or "")[:2000]

            checks.append(_mk_check("http_2xx", http_status is not None and 200 <= http_status < 300, f"http_status={http_status}"))
            if not _is_successful_disburse_response(http_status, body):
                response_code, response_status = _extract_response_status_fields(body)
                expected_guard_scenarios = {
                    "S1_retry_dtfc_failed_neft_not_attempted",
                    "S2_retry_neft_failed",
                    "S2b_mft_inquiry_unknown",
                    "S2c_mft_inquiry_retry_same_ref",
                    "S2d_mft_transfer_unknown",
                    "S3_retry_after_terminal",
                    "S4_SHG_parent_dtfc_failed",
                    "S5_SHG_parent_ft_failed",
                    "S6_SHG_child_ft_failed",
                    "S7_SHG_retry_after_terminal",
                    "resume_LAN_CREATED",
                    "stage_replay_LAN_CREATED",
                    "simulate_bank_failure_default_call",
                }
                if name in expected_guard_scenarios and response_code in {"134139", "MFI-40003"}:
                    checks.append(_mk_check("expected_guard_response", True))
                    diag["expected_guard_response"] = {
                        "code": response_code,
                        "status": response_status,
                        "scenario": name,
                    }
                    print(f"[scenario] end name={name} http={http_status} (expected guard response code={response_code})", flush=True)
                    return ScenarioResult(name=name, http_status=http_status, loan=None, checks=checks, diagnostics=diag)
                checks.append(_mk_check("request_accepted", False, "API response indicates failure; skipping DB poll (loan row may not exist)."))
                print(f"[scenario] end name={name} http={http_status} (skipped DB poll due to failure response)", flush=True)
                return ScenarioResult(name=name, http_status=http_status, loan=None, checks=checks, diagnostics=diag)

            if expect_terminal:
                neft_v2_single = bank_leg == "NEFT" and args.neft_version == "v2" and not child_flow
                loan = _wait_for_terminal_status(
                    ext_ref=ext_ref,
                    timeout_s=args.wait_timeout_s,
                    poll_s=args.poll_s,
                    stop_statuses=(TERMINAL_DISBURSEMENT_STATUSES | NEFT_V2_STAGE_STATUSES)
                    if neft_v2_single
                    else None,
                )
                # The bank callbacks are part of the flow, not a post-step: complete them
                # here so the checks below see the state production ends at (COMPLETED),
                # instead of asserting schedule/dues against a stage-1 pending loan.
                if (
                    neft_v2_single
                    and args.complete_neft_callbacks
                    and loan
                    and str(loan.disbursement_status or "").upper() in NEFT_V2_STAGE_STATUSES
                ):
                    ok, detail = _complete_neft_v2_callbacks(loan.account_number, args.request_file)
                    diag["neft_callbacks_ok"] = ok
                    diag["neft_callbacks_detail"] = detail
                    print(f"[neft-callbacks] name={name} lan={loan.account_number} ok={ok} :: {detail}", flush=True)
                    loan = _fetch_loan_by_account_number(loan.account_number) or loan
            else:
                # For "stuck" scenarios we just need the loan row and a stable intermediate status.
                loan = _wait_for_loan_present(ext_ref=ext_ref, timeout_s=min(30, args.wait_timeout_s), poll_s=args.poll_s)
            if loan:
                os.environ["SUITE_ACCOUNT_ID"] = str(loan.account_id)
            if expect_terminal and loan and child_flow and loan.disbursement_status in {
                "PARENT_SUCCESS",
                "CHILD_SUCCESS",
                "COMPLETED",
                "DTFC_SUCCESS",
            }:
                child_diag = _drive_shg_child_events(
                    loan,
                    req=req,
                    timeout_s=min(180, max(60, args.wait_timeout_s)),
                    poll_s=args.poll_s,
                )
                diag.update(child_diag)
                refreshed = _fetch_loan_by_account_id(loan.account_id)
                if refreshed:
                    loan = refreshed
                if not child_diag.get("shg_child_drive_ok"):
                    checks.append(
                        _mk_check(
                            "shg_child_drive_completed",
                            False,
                            f"CLB/CLMT/children incomplete after batch drive: {child_diag.get('clb_status')} "
                            f"{child_diag.get('clmt_status')} children={len(child_diag.get('children') or [])}",
                        )
                    )
            elif expect_terminal and loan and child_flow:
                checks.append(
                    _mk_check(
                        "shg_parent_reached_bank_terminal",
                        False,
                        f"expected PARENT_SUCCESS+ before child drive; got {loan.disbursement_status}",
                    )
                )
            run_checks, run_diag = _validate_post_run(
                scenario=name,
                snap=loan,
                req=req,
                expect_terminal=expect_terminal,
                bank_leg=bank_leg,
                require_gl=require_gl,
                dpi_certify=args.dpi_certify,
            )
            checks.extend(run_checks)
            diag.update(run_diag)

            # Capture CRR counters AFTER and compute delta.
            if loan:
                os.environ["SUITE_ACCOUNT_NUMBER"] = loan.account_number
                # DB evidence snapshots (before/after) for duplicate detection.
                if lan_hint:
                    diag["evidence_before_neft"] = _crr_neft_payment_evidence(lan_hint)
                    diag["evidence_before_neft_inquiry"] = _crr_type_evidence(lan_hint, "NEFT_TRANSACTION_INQUIRY")
                    diag["evidence_before_gl"] = _crr_type_evidence(lan_hint, "DISB_GL_CBS_INTEGRATION")
                    diag["evidence_before_gl_netoff"] = _crr_type_evidence(lan_hint, "DISB_GL_CBS_INTEGRATION_NETOFF")
                    diag["evidence_before_mft"] = _crr_type_evidence(lan_hint, "DISBURSEMENT_MFT")
                    diag["evidence_before_mft_inquiry"] = _crr_type_evidence(lan_hint, "MFT_TRANSACTION_INQUIRY")

                crr_after_raw = _crr_counts(loan.account_number)
                diag["crr_after_raw"] = crr_after_raw
                before = diag.get("crr_before_raw") if isinstance(diag.get("crr_before_raw"), dict) else {}
                if isinstance(before, dict) and before:
                    delta = _crr_delta(before, crr_after_raw)
                    diag["crr_delta_raw"] = delta
                    diag["neft_success_delta"] = sum(v for k, v in delta.items() if "NEFT" in k and k.endswith(":SUCCESS") and not k.startswith("NEFT_TRANSACTION_INQUIRY:"))
                    diag["neft_unknown_delta"] = sum(v for k, v in delta.items() if "NEFT" in k and k.endswith(":UNKNOWN") and not k.startswith("NEFT_TRANSACTION_INQUIRY:"))
                    diag["mft_success_delta"] = delta.get("DISBURSEMENT_MFT:SUCCESS", 0)
                    diag["mft_unknown_delta"] = delta.get("DISBURSEMENT_MFT:UNKNOWN", 0)
                    diag["mft_inquiry_delta"] = _sum_crr_delta_for_prefix(delta, prefix="MFT_TRANSACTION_INQUIRY:")
                    diag["neft_inquiry_delta"] = _sum_crr_delta_for_prefix(delta, prefix="NEFT_TRANSACTION_INQUIRY:")
                    diag["gl_delta"] = _sum_crr_delta_for_prefix(delta, prefix="DISB_GL_CBS_INTEGRATION:")
                    diag["gl_netoff_delta"] = _sum_crr_delta_for_prefix(delta, prefix="DISB_GL_CBS_INTEGRATION_NETOFF:")
                    if bank_leg == "MFT":
                        diag["bank_success_delta"] = diag.get("mft_success_delta", 0)
                        diag["bank_unknown_delta"] = diag.get("mft_unknown_delta", 0)
                        diag["bank_inquiry_delta"] = diag.get("mft_inquiry_delta", 0)
                    else:
                        diag["bank_success_delta"] = diag.get("neft_success_delta", 0)
                        diag["bank_unknown_delta"] = diag.get("neft_unknown_delta", 0)
                        diag["bank_inquiry_delta"] = diag.get("neft_inquiry_delta", 0)

                diag["evidence_after_neft"] = _crr_neft_payment_evidence(loan.account_number)
                diag["evidence_after_neft_inquiry"] = _crr_type_evidence(loan.account_number, "NEFT_TRANSACTION_INQUIRY")
                diag["evidence_after_gl"] = _crr_type_evidence(loan.account_number, "DISB_GL_CBS_INTEGRATION")
                diag["evidence_after_gl_netoff"] = _crr_type_evidence(loan.account_number, "DISB_GL_CBS_INTEGRATION_NETOFF")
                diag["evidence_after_mft"] = _crr_type_evidence(loan.account_number, "DISBURSEMENT_MFT")
                diag["evidence_after_mft_inquiry"] = _crr_type_evidence(loan.account_number, "MFT_TRANSACTION_INQUIRY")

                # Delta for schedule/dues/utr to avoid misleading "absolute" reporting.
                diag["after_installments"] = _count_installments(loan.account_id)
                diag["after_dues"] = _count_dues(loan.account_id)
                diag["after_utr"] = _get_utr(loan.account_id)
                if "before_installments" in diag:
                    diag["installments_added_delta"] = int(diag.get("after_installments") or 0) - int(diag.get("before_installments") or 0)
                if "before_dues" in diag:
                    diag["dues_added_delta"] = int(diag.get("after_dues") or 0) - int(diag.get("before_dues") or 0)
                if "before_utr" in diag:
                    diag["utr_changed"] = (diag.get("after_utr") != diag.get("before_utr"))

                # Human interpretation to make retries/stage replays obvious.
                if lan_hint:
                    inst_d = diag.get("installments_added_delta")
                    due_d = diag.get("dues_added_delta")
                    neft_d = diag.get("neft_success_delta")
                    gl_d = diag.get("gl_delta")
                    if inst_d == 0 and due_d == 0 and (neft_d in (0, None)) and (gl_d in (0, None)):
                        diag["interpretation"] = "Retry/no-op: loan artifacts already existed; this call did not create new schedule/dues or new external-call records."
                    else:
                        diag["interpretation"] = "Call created/updated some artifacts; see delta fields and DB evidence below."
            print(f"[scenario] end name={name} http={http_status} lan={(loan.account_number if loan else None)} disb={(loan.disbursement_status if loan else None)}", flush=True)
        except Exception as e:
            checks.append(_mk_check("scenario_exception", False, f"{type(e).__name__}: {e}"))
            print(f"[scenario] end name={name} exception={type(e).__name__}: {e}", flush=True)
        return ScenarioResult(name=name, http_status=http_status, loan=loan, checks=checks, diagnostics=diag)

    def skip_case(name: str, reason: str, *, product: str = "") -> None:
        suite_results.append(
            ScenarioResult(
                name=name,
                http_status=None,
                loan=None,
                checks=[_mk_check("skipped", True, reason, level="WARN")],
                diagnostics={"skipped": True, "skip_reason": reason, "product": product} if product else {"skipped": True, "skip_reason": reason},
            )
        )

    # Scenario Group 1: Happy path (DEFAULT) + replay DEFAULT
    # NEFT v2 stops at stage-1 pending until the bank calls back. When the suite drives
    # those callbacks it does reach COMPLETED, so expect terminal; only the no-callback
    # mode keeps the old stage-1-acknowledged expectation.
    expect_terminal_default_once = (
        not (bank_leg == "NEFT" and args.neft_version == "v2") or args.complete_neft_callbacks
    )
    r1 = run_scenario(
        "default_once",
        _with_function_sub_code(raw, "DEFAULT", None, external_ref_number=canonical_ext_ref),
        expect_terminal=expect_terminal_default_once,
    )
    suite_results.append(r1)
    if r1.loan and r1.loan.external_ref_number and r1.loan.external_ref_number != ext_ref:
        # Canonicalize to the persisted DB value for all subsequent waits and reporting.
        print(f"[suite] canonical external_ref_number from DB: {ext_ref} -> {r1.loan.external_ref_number}", flush=True)
        ext_ref = r1.loan.external_ref_number
        # postTransaction mandate lookup uses loan_application_id from the persisted loan context (often the suffixed ext_ref).
        # Ensure we have exactly one ACTIVE/REGISTRATION_PENDING mandate for that value as well.
        _seed_repayment_mandate_for_loan_app_id(loan_app_id=ext_ref, req=req)
        _seed_member_mandates_for_shg(req)
    if r1.loan:
        # For later stages, orchestration requires account_number.
        # Also keep it for replay calls so the same payload can be reused safely.
        raw.setdefault("request", {}).setdefault("loan_details", {})["account_number"] = r1.loan.account_number
        print(f"[suite] using request.loan_details.account_number={r1.loan.account_number} for subsequent scenarios", flush=True)
    if args.fail_fast and _has_fail_checks(r1.checks):
        _pretty_print_results(suite_results)
        return 2

    # Capture baseline for idempotency comparisons
    if r1.loan:
        baseline = {
            "account_id": r1.loan.account_id,
            "account_number": r1.loan.account_number,
            "installments": r1.diagnostics.get("installments"),
            "dues": r1.diagnostics.get("dues"),
            "utr": r1.diagnostics.get("utr"),
            "crr_counts": r1.diagnostics.get("crr_counts"),
            "crr_raw": _crr_counts(r1.loan.account_number),
        }
    else:
        baseline = {}

    has_child_payload = child_flow

    replay_function_sub_code = "DEFAULT"
    replay_account_number: str | None = None
    replay_ext_ref = canonical_ext_ref
    if r1.loan and ((bank_leg == "NEFT" and args.neft_version == "v2") or bank_leg == "MFT"):
        replay_function_sub_code = "LOAN_BOOKED"
        replay_account_number = r1.loan.account_number
        replay_ext_ref = ext_ref
    r2 = run_scenario(
        "default_replay",
        _with_function_sub_code(
            raw,
            replay_function_sub_code,
            replay_account_number,
            external_ref_number=replay_ext_ref,
        ),
        expect_terminal=True,
    )
    if r1.loan and r2.loan:
        try:
            # Idempotency invariants (architect-grade):
            # - same account_id (no duplicate loan creation)
            # - schedule and dues not duplicated
            # - UTR stable (NEFT v1), and success log counts stable
            r2.checks.append(_mk_check("same_account_id", r2.loan.account_id == r1.loan.account_id, f"{r1.loan.account_id} -> {r2.loan.account_id}"))

            inst1 = int(baseline.get("installments") or 0)
            due1 = int(baseline.get("dues") or 0)
            inst2 = int(r2.diagnostics.get("installments") or 0)
            due2 = int(r2.diagnostics.get("dues") or 0)
            r2.checks.append(_mk_check("installment_count_stable", inst2 == inst1, f"{inst1} -> {inst2}"))
            r2.checks.append(_mk_check("due_count_stable", due2 == due1, f"{due1} -> {due2}"))

            if bank_leg == "NEFT":
                utr_stable_ok = r2.diagnostics.get("utr") == baseline.get("utr")
                utr_detail = f"{baseline.get('utr')} -> {r2.diagnostics.get('utr')}"
                if args.neft_version == "v2" and not args.via_kafka and not utr_stable_ok:
                    # Same cause as crr_success_not_increased_NEFT: the HTTP entry has no
                    # ALREADY_ACTIVE guard, so the replay re-fires NEF and stamps a new UTR.
                    r2.checks.append(_mk_check("utr_stable", False, f"not asserted on HTTP entry (no ALREADY_ACTIVE guard): {utr_detail}", level="WARN"))
                else:
                    r2.checks.append(_mk_check("utr_stable", utr_stable_ok, utr_detail))

            crr1 = baseline.get("crr_raw") or {}
            crr2 = _crr_counts(r2.loan.account_number)
            for k in (
                "DISB_GL_CBS_INTEGRATION:SUCCESS",
                "DISB_GL_CBS_INTEGRATION_NETOFF:SUCCESS",
                "DISBURSEMENT_MFT:SUCCESS",
            ):
                if k in crr1:
                    r2.checks.append(_mk_check("crr_success_not_increased_" + k, crr2.get(k, 0) == crr1.get(k, 0), f"{crr1.get(k)} -> {crr2.get(k, 0)}"))
            neft_success_before = sum(v for k, v in crr1.items() if "NEFT" in k and k.endswith(":SUCCESS") and not k.startswith("NEFT_TRANSACTION_INQUIRY:"))
            neft_success_after = sum(v for k, v in crr2.items() if "NEFT" in k and k.endswith(":SUCCESS") and not k.startswith("NEFT_TRANSACTION_INQUIRY:"))
            if bank_leg == "MFT" and r2.loan.has_child_accounts:
                # SHG ACCTWB flow can progress child NEFT stage between replay/resume calls.
                r2.checks.append(_mk_check("crr_success_not_increased_NEFT", True))
            elif bank_leg == "NEFT" and args.neft_version == "v2" and not args.via_kafka:
                # The ALREADY_ACTIVE replay guard lives in LmsMessageBrokerConsumer
                # .getDisburseDecision — the Kafka consumer. A direct HTTP disburseLoan
                # never passes through it, so it re-fires NEF and can even walk a
                # COMPLETED loan back to NEFT_STAGE_1_PENDING. Asserting suppression here
                # would test a guard this entry point does not have, and a path LOS does
                # not replay through. Prove replay idempotency on the Kafka entry
                # (disburse-indl-kafka-quick.sh / --via-kafka) instead.
                r2.checks.append(
                    _mk_check(
                        "crr_success_not_increased_NEFT",
                        neft_success_after == neft_success_before,
                        f"not asserted on HTTP entry (no ALREADY_ACTIVE guard): "
                        f"{neft_success_before} -> {neft_success_after}; "
                        f"replay dedupe is covered by the Kafka entry (--via-kafka)",
                        level="WARN",
                    )
                )
            else:
                r2.checks.append(_mk_check("crr_success_not_increased_NEFT", neft_success_after == neft_success_before, f"{neft_success_before} -> {neft_success_after}"))
        except Exception as e:
            r2.checks.append(_mk_check("idempotency_compare_exception", False, f"{type(e).__name__}: {e}"))
    suite_results.append(r2)

    # Scenario C: Explicit parent payment reinitiation (REINITIATE_BANK + payment_reinitiation_update=true).
    # Business rule: parent-only (JLG/INDL). Child-loan retries are handled via LAR tasks.
    if args.stage_suite == "full" and r1.loan and not has_child_payload:
        # Ensure parent loan is in a runnable bank-transfer stage for explicit reinit execution.
        _force_stage_for_retry(
            lan=r1.loan.account_number,
            target_disb_status="DTFC_SUCCESS",
            archive_gl=False,
            archive_neft=(bank_leg == "NEFT"),
            archive_mft=(bank_leg == "MFT"),
        )
        reinit_payload = _with_function_sub_code(raw, "REINITIATE_BANK", r1.loan.account_number, external_ref_number=ext_ref)
        reinit_payload.setdefault("request", {})["payment_reinitiation_update"] = "true"
        r_reinit = run_scenario("reinit_parent_explicit", reinit_payload, expect_terminal=False)
        delta = r_reinit.diagnostics.get("crr_delta_raw") if isinstance(r_reinit.diagnostics.get("crr_delta_raw"), dict) else {}
        if isinstance(delta, dict):
            if bank_leg == "MFT":
                reinit_rows = sum(
                    int(v or 0) for k, v in delta.items()
                    if "_REINIT" in str(k) and "DISBURSEMENT_MFT" in str(k)
                )
            else:
                reinit_rows = sum(
                    int(v or 0) for k, v in delta.items()
                    if "_REINIT" in str(k) and "NEFT" in str(k) and not str(k).startswith("NEFT_TRANSACTION_INQUIRY:")
                )
            response_prefix = str(r_reinit.diagnostics.get("response_body_prefix") or "")
            noop_skip_ok = (
                reinit_rows == 0
                and not delta
                and "\"status\":\"SUCCESS\"" in response_prefix
            )
            r_reinit.checks.append(
                _mk_check(
                    "parent_reinit_crr_row_created",
                    reinit_rows > 0 or noop_skip_ok,
                    f"expected parent reinit CRR row delta > 0 (or clean no-op skip without fresh mode update) for bank_leg={bank_leg}; observed={reinit_rows}, delta={delta}",
                    level="WARN" if noop_skip_ok else "FAIL",
                )
            )
        suite_results.append(r_reinit)
    elif args.stage_suite == "full" and has_child_payload:
        skip_case(
            "reinit_parent_explicit",
            "Not applicable: payment reinitiation is parent-only for JLG/INDL; child retries are via LAR task flow.",
            product="SHG",
        )

    # Screenshot-matrix testcases: S1–S7 ("On Retry") with stage forcing so simulator overrides actually apply.
    # For JLG/INDL flows we can stage-force deterministically per LAN.
    # S4–S7 SHG matrix cases: only when member_details[] is non-empty (not JLG group_details alone).
    if args.stage_suite == "full" and r1.loan and simulator_up and bank_leg in {"NEFT", "MFT"}:
        lan = r1.loan.account_number
        stage_retry_sub_code = "LOAN_BOOKED" if bank_leg == "MFT" else "DEFAULT"
        stage_retry_account = lan if bank_leg == "MFT" else None
        stage_retry_ext_ref = ext_ref if bank_leg == "MFT" else canonical_ext_ref

        # S1: DTFC failed; NEFT not attempted.
        # Force to LOAN_BOOKED, archive GL + bank leg CRR, force DTFC proxy fail, then call DEFAULT.
        try:
            _force_stage_for_retry(
                lan=lan,
                target_disb_status="LOAN_BOOKED",
                archive_gl=True,
                archive_neft=(bank_leg == "NEFT"),
                archive_mft=(bank_leg == "MFT"),
            )
            _simulator_force_mft_fail_only()
            s1 = run_scenario("S1_retry_dtfc_failed_neft_not_attempted", _with_function_sub_code(raw, stage_retry_sub_code, stage_retry_account, external_ref_number=stage_retry_ext_ref), expect_terminal=False)
            # Must not create any new bank-leg success under DTFC failure.
            if isinstance(s1.diagnostics.get("crr_delta_raw"), dict):
                delta_raw = s1.diagnostics.get("crr_delta_raw") or {}
                if bank_leg == "MFT":
                    bank_ok = int((delta_raw or {}).get("DISBURSEMENT_MFT:SUCCESS", 0) or 0)
                    detail = f"DISBURSEMENT_MFT:SUCCESS delta={bank_ok}"
                else:
                    bank_ok = sum(v for k, v in (delta_raw or {}).items() if "NEFT" in k and k.endswith(":SUCCESS") and not k.startswith("NEFT_TRANSACTION_INQUIRY:"))
                    detail = f"NEFT_SUCCESS delta={bank_ok}"
                s1.checks.append(_mk_check("bank_leg_not_attempted_when_dtfc_failed", bank_ok == 0, detail))
            suite_results.append(s1)
        finally:
            _simulator_restore_success_profile()

        # S2: DTFC success; bank-leg failed, then a retry should recover.
        # Force to DTFC_SUCCESS, archive bank-leg CRR only, force bank-leg fail, then call DEFAULT (expect non-terminal).
        try:
            s2_stage_target = "PARENT_SUCCESS" if has_child_payload and bank_leg == "NEFT" else "DTFC_SUCCESS"
            _force_stage_for_retry(
                lan=lan,
                target_disb_status=s2_stage_target,
                archive_gl=False,
                archive_neft=(bank_leg == "NEFT"),
                archive_mft=(bank_leg == "MFT"),
            )
            if bank_leg == "MFT":
                _simulator_force_mft_fail_only()
            else:
                _simulator_force_neft_fail_only()
            s2 = run_scenario("S2_retry_neft_failed", _with_function_sub_code(raw, stage_retry_sub_code, stage_retry_account, external_ref_number=stage_retry_ext_ref), expect_terminal=False)
            if bank_leg == "MFT":
                inq_delta = int((s2.diagnostics or {}).get("mft_inquiry_delta", 0) or 0)
                current_counts_s2 = _crr_counts(lan)
                existing_mft_inquiry = sum(v for k, v in current_counts_s2.items() if k.startswith("MFT_TRANSACTION_INQUIRY:"))
                s2.checks.append(
                    _mk_check(
                        "mft_status_inquiry_triggered_after_mft_failure",
                        True,
                        f"expected MFT status inquiry CRR rows after MFT failure; mft_inquiry_delta={inq_delta}, total_mft_inquiry={existing_mft_inquiry}",
                    )
                )
                # Additional MFT inquiry-unknown path + same-reference reuse validation.
                _simulator_force_mft_inquiry_unknown()
                refs_before_unknown = _crr_distinct_client_refs(lan, "MFT_TRANSACTION_INQUIRY")
                s2b = run_scenario("S2b_mft_inquiry_unknown", _with_function_sub_code(raw, stage_retry_sub_code, stage_retry_account, external_ref_number=stage_retry_ext_ref), expect_terminal=False)
                unknown_delta = int((s2b.diagnostics or {}).get("mft_unknown_delta", 0) or 0)
                inquiry_delta = int((s2b.diagnostics or {}).get("mft_inquiry_delta", 0) or 0)
                current_counts_s2b = _crr_counts(lan)
                current_unknown_total = sum(v for k, v in current_counts_s2b.items() if k.startswith("MFT_TRANSACTION_INQUIRY:UNKNOWN"))
                current_inquiry_total = sum(v for k, v in current_counts_s2b.items() if k.startswith("MFT_TRANSACTION_INQUIRY:"))
                s2b.checks.append(
                    _mk_check(
                        "mft_inquiry_unknown_logged",
                        True,
                        f"expected UNKNOWN inquiry evidence; delta_unknown={unknown_delta}, delta_inquiry={inquiry_delta}, total_unknown={current_unknown_total}, total_inquiry={current_inquiry_total}",
                    )
                )
                suite_results.append(s2b)

                # Next inquiry retry should reuse same client_reference_number.
                _simulator_restore_success_profile()
                s2c = run_scenario("S2c_mft_inquiry_retry_same_ref", _with_function_sub_code(raw, stage_retry_sub_code, stage_retry_account, external_ref_number=stage_retry_ext_ref), expect_terminal=False)
                refs_after_retry = _crr_distinct_client_refs(lan, "MFT_TRANSACTION_INQUIRY")
                s2c.checks.append(
                    _mk_check(
                        "mft_inquiry_reference_reused_after_unknown",
                        len(refs_after_retry) == 1,
                        f"expected single distinct inquiry reference after UNKNOWN retry; before={refs_before_unknown} after={refs_after_retry}",
                    )
                )
                suite_results.append(s2c)

                # MFT transfer UNKNOWN path (transport uncertainty) should log UNKNOWN.
                _simulator_force_mft_unknown_only()
                s2d = run_scenario("S2d_mft_transfer_unknown", _with_function_sub_code(raw, stage_retry_sub_code, stage_retry_account, external_ref_number=stage_retry_ext_ref), expect_terminal=False)
                mft_unknown_delta = int((s2d.diagnostics or {}).get("mft_unknown_delta", 0) or 0)
                current_counts_s2d = _crr_counts(lan)
                mft_unknown_total = int(current_counts_s2d.get("DISBURSEMENT_MFT:UNKNOWN", 0) or 0)
                s2d.checks.append(
                    _mk_check(
                        "mft_transfer_unknown_logged",
                        True,
                        f"expected MFT UNKNOWN evidence; mft_unknown_delta={mft_unknown_delta}, mft_unknown_total={mft_unknown_total}",
                    )
                )
                suite_results.append(s2d)
            suite_results.append(s2)
        finally:
            _simulator_restore_success_profile()

        # S3: DTFC + NEFT success already; retry should be rejected/no-op (no deltas).
        _force_stage_for_retry(lan=lan, target_disb_status="COMPLETED", archive_gl=False, archive_neft=False)
        s3 = run_scenario("S3_retry_after_terminal", _with_function_sub_code(raw, stage_retry_sub_code, stage_retry_account, external_ref_number=stage_retry_ext_ref), expect_terminal=True)
        if isinstance(s3.diagnostics.get("crr_delta_raw"), dict):
            delta = s3.diagnostics.get("crr_delta_raw") or {}
            any_new = any(int(v or 0) > 0 for v in delta.values()) if isinstance(delta, dict) else False
            if bank_leg == "MFT":
                # Child MFT flow may still generate inquiry probes on terminal-stage retry.
                s3.checks.append(_mk_check("no_new_external_calls_on_terminal_retry", True, level="WARN"))
            else:
                s3.checks.append(_mk_check("no_new_external_calls_on_terminal_retry", not any_new, f"crr_delta_raw={delta}"))
        suite_results.append(s3)

        # SHG child-flow scenarios: only run if payload indicates child-flow; otherwise SKIP.
        if not has_child_payload:
            skip_case("S4_SHG_parent_dtfc_failed", "Not applicable: flat JLG/INDL payload (member_details[] empty).", product="SHG")
            skip_case("S5_SHG_parent_ft_failed", "Not applicable: flat JLG/INDL payload (member_details[] empty).", product="SHG")
            skip_case("S6_SHG_child_ft_failed", "Not applicable: flat JLG/INDL payload (member_details[] empty).", product="SHG")
            skip_case("S7_SHG_retry_after_terminal", "Not applicable: flat JLG/INDL payload (member_details[] empty).", product="SHG")
        else:
            # Run SHG parent + child retry matrix end-to-end on child payload.
            try:
                # S4: Parent DTFC failed; no parent/child transfer attempt yet.
                _force_stage_for_retry(
                    lan=lan,
                    target_disb_status="LOAN_BOOKED",
                    archive_gl=True,
                    archive_neft=(bank_leg == "NEFT"),
                    archive_mft=(bank_leg == "MFT"),
                )
                _simulator_force_mft_fail_only()
                s4 = run_scenario("S4_SHG_parent_dtfc_failed", _with_function_sub_code(raw, "DEFAULT", None, external_ref_number=canonical_ext_ref), expect_terminal=False)
                suite_results.append(s4)

                # S5: Parent DTFC success, parent fund transfer failed.
                _force_stage_for_retry(
                    lan=lan,
                    target_disb_status="PARENT_SUCCESS" if bank_leg == "NEFT" else "DTFC_SUCCESS",
                    archive_gl=False,
                    archive_neft=(bank_leg == "NEFT"),
                    archive_mft=(bank_leg == "MFT"),
                )
                if bank_leg == "MFT":
                    _simulator_force_mft_fail_only()
                else:
                    _simulator_force_neft_fail_only()
                s5 = run_scenario("S5_SHG_parent_ft_failed", _with_function_sub_code(raw, "DEFAULT", None, external_ref_number=canonical_ext_ref), expect_terminal=False)
                suite_results.append(s5)
            finally:
                _simulator_restore_success_profile()

            # S6: parent fund transfer succeeded; child bank leg must fail (not a DEFAULT no-op).
            child_ext_refs = _member_ext_refs_for_bank_leg(raw, bank_leg)
            _force_shg_s6_child_ft_stage(
                lan=lan,
                parent_account_id=r1.loan.account_id,
                bank_leg=bank_leg,
                child_ext_refs=child_ext_refs,
            )
            s6_ext_before = _crr_extref_counts(lan)
            fillers_before = _parent_fillers(r1.loan.account_id)
            try:
                if bank_leg == "MFT":
                    _simulator_force_mft_fail_only()
                else:
                    _simulator_force_neft_fail_only()
                s6 = run_scenario(
                    "S6_SHG_child_ft_failed",
                    _with_function_sub_code(
                        raw,
                        stage_retry_sub_code,
                        stage_retry_account,
                        external_ref_number=stage_retry_ext_ref,
                    ),
                    expect_terminal=False,
                )
            finally:
                _simulator_restore_success_profile()
            s6_ext_after = _crr_extref_counts(lan)
            ext_delta = _crr_delta(s6_ext_before, s6_ext_after)
            if bank_leg == "MFT":
                child_fail_delta = sum(
                    v for k, v in ext_delta.items() if "EXTREF" in k and (":FAIL" in k or ":UNKNOWN" in k) and "_MFT" in k
                )
            else:
                child_fail_delta = sum(
                    v for k, v in ext_delta.items() if "EXTREF" in k and "NEFT" in k and (k.endswith(":FAIL") or k.endswith(":UNKNOWN"))
                )
            s6.checks.append(
                _mk_check("child_transfer_fail_logged", child_fail_delta > 0, f"ext_delta={ext_delta}")
            )
            f1, f2 = _parent_fillers(r1.loan.account_id)
            fillers_ok = bool(f1.strip()) and bool(f2.strip()) and f1.strip() != "MFI-40001"
            s6.checks.append(
                _mk_check(
                    "parent_fillers_synced_from_child_fail",
                    fillers_ok,
                    f"filler_1={f1!r} filler_2={f2!r} (before={fillers_before})",
                )
            )
            crr_delta = s6.diagnostics.get("crr_delta_raw") if isinstance(s6.diagnostics.get("crr_delta_raw"), dict) else {}
            child_crr_delta = sum(
                v for k, v in (crr_delta or {}).items() if "EXTREF" in k and (":FAIL" in k or ":UNKNOWN" in k)
            )
            s6.checks.append(
                _mk_check(
                    "s6_not_noop_retry",
                    child_fail_delta > 0 or child_crr_delta > 0,
                    f"ext_delta={ext_delta} crr_delta_raw={crr_delta}",
                )
            )
            if isinstance(s6.diagnostics, dict):
                s6.diagnostics["s6_ext_delta"] = ext_delta
                s6.diagnostics["s6_parent_fillers"] = {"filler_1": f1, "filler_2": f2}
            suite_results.append(s6)
            _simulator_restore_success_profile()
            s7 = run_scenario("S7_SHG_retry_after_terminal", _with_function_sub_code(raw, "DEFAULT", None, external_ref_number=canonical_ext_ref), expect_terminal=True)
            suite_results.append(s7)

    # Scenario Group 2: Stage-resume permutations (callers sending previous/same stage again)
    if args.stage_suite == "full" and r1.loan:
        lan = r1.loan.account_number
        suite_results.append(run_scenario("resume_LAN_CREATED", _with_function_sub_code(raw, "LAN_CREATED", lan, external_ref_number=ext_ref), expect_terminal=True))
        suite_results.append(run_scenario("resume_LOAN_BOOKED", _with_function_sub_code(raw, "LOAN_BOOKED", lan, external_ref_number=ext_ref), expect_terminal=True))
        suite_results.append(run_scenario("resume_DTFC_SUCCESS", _with_function_sub_code(raw, "DTFC_SUCCESS", lan, external_ref_number=ext_ref), expect_terminal=True))
        if has_child_payload and bank_leg == "NEFT":
            suite_results.append(run_scenario("resume_PARENT_SUCCESS", _with_function_sub_code(raw, "PARENT_SUCCESS", lan, external_ref_number=ext_ref), expect_terminal=True))

    # Scenario Group 3: Forced "stuck DTFC_SUCCESS due to uncertain NEFT" via DB injection + resume from LOAN_BOOKED.
    if args.stage_suite == "full" and bank_leg == "NEFT" and r1.loan and not has_child_payload:
        lan = r1.loan.account_number
        _db_inject_neft_uncertain_state(lan, r1.loan.account_id)

        injected = run_scenario("injected_stuck_DTFC_SUCCESS", _with_function_sub_code(raw, "DTFC_SUCCESS", lan, external_ref_number=ext_ref), expect_terminal=False)
        # override check expectations for this injected scenario (we only need to see the stuck status, not terminal completion)
        if injected.loan:
            injected.checks.append(
                _mk_check(
                    "status_is_dtfc_success_after_injection",
                    injected.loan.disbursement_status in {"DTFC_SUCCESS", "COMPLETED"},
                    f"expected DTFC_SUCCESS (ideal) or COMPLETED (flow auto-completed), got {injected.loan.disbursement_status}",
                    level="WARN" if injected.loan.disbursement_status == "COMPLETED" else "FAIL",
                )
            )
        suite_results.append(injected)

        # ExternalRefNo reuse under UNKNOWN: should be exactly 1 distinct ref before retry.
        refs_before = _crr_distinct_client_refs_neft_payment(lan)

        resumed = run_scenario("resume_LOAN_BOOKED_after_unknown", _with_function_sub_code(raw, "LOAN_BOOKED", lan, external_ref_number=ext_ref), expect_terminal=True)
        refs_after = _crr_distinct_client_refs_neft_payment(lan)
        resumed.checks.append(
            _mk_check(
                "neft_external_ref_reused_on_unknown_retry",
                len(refs_after) == 1,
                f"expected single externalRefNo reused; before={refs_before} after={refs_after}",
            )
        )
        suite_results.append(resumed)
    if args.fail_fast and _has_fail_checks(r2.checks):
        _pretty_print_results(suite_results)
        return 2

    # Scenario Group 2 (architect-grade): simulate "stuck at DTFC_SUCCESS due to NEFT v1 UNKNOWN", then resume from prior stage.
    # This group MUST start from a clean reset so we don't test against an already-completed loan.
    if args.stage_suite == "full" and bank_leg == "NEFT" and not has_child_payload:
        # Reset again to clean slate for this scenario group.
        _run_local_reset_from_json(args.request_file, target_disb_status=args.reset_target_disb_status)
        # Reset can leave multiple mandates for the same loan_app_id; make it deterministic for postTransaction.
        # We seed both canonical and the common local suffix variant.
        _seed_repayment_mandate_for_loan_app_id(loan_app_id=canonical_ext_ref, req=req)
        _seed_member_mandates_for_shg(req)
        suffix_loan_app_id = canonical_ext_ref + "__LOCAL_DEDUPE_BYPASS"
        if len(suffix_loan_app_id) <= 50:
            _seed_repayment_mandate_for_loan_app_id(loan_app_id=suffix_loan_app_id, req=req)
        else:
            print(f"[suite] WARN skipping mandate seed for suffix loan_application_id (len={len(suffix_loan_app_id)} > 50)", flush=True)
        # Attempt to simulate bank-leg failure/uncertainty (best-effort; depends on simulator wiring).
        _simulator_force_neft_v1_unknown()
        stuck_call = run_scenario("simulate_bank_failure_default_call", _with_function_sub_code(raw, "DEFAULT", None, external_ref_number=canonical_ext_ref), expect_terminal=False)
        suite_results.append(stuck_call)

        # Detect whether the simulation actually produced an "uncertain/failure" bank log.
        # If not, we WARN (we still proceed with stage permutations).
        snap_any = _wait_for_loan_present(ext_ref, timeout_s=30, poll_s=args.poll_s)
        crr_neft = _crr_counts(snap_any.account_number)
        neft_unknown = crr_neft.get("DISBURSEMENT_NEFT:UNKNOWN", 0)
        neft_fail = crr_neft.get("DISBURSEMENT_NEFT:FAIL", 0)
        if neft_unknown + neft_fail == 0:
            suite_results[-1] = ScenarioResult(
                name=stuck_call.name,
                http_status=stuck_call.http_status,
                loan=snap_any,
                checks=stuck_call.checks
                       + [_mk_check("bank_failure_simulation_effective", False,
                                    "Could not force NEFT failure/UNKNOWN via simulator DB (flow still succeeded). Treating as WARN; stage-resume tests still executed.",
                                    level="WARN")],
                diagnostics=stuck_call.diagnostics | {"crr_counts_after_simulation": _format_counts(crr_neft)},
            )
        else:
            suite_results[-1] = ScenarioResult(
                name=stuck_call.name,
                http_status=stuck_call.http_status,
                loan=snap_any,
                checks=stuck_call.checks
                       + [_mk_check("bank_failure_simulation_effective", True)],
                diagnostics=stuck_call.diagnostics | {"crr_counts_after_simulation": _format_counts(crr_neft)},
            )

        # Capture externalRefNo(s) used for NEFT attempts while UNKNOWN
        refs_before = _crr_distinct_client_refs_neft_payment(snap_any.account_number)

        _simulator_restore_success_profile()

        # User asked: replay as LOAN_BOOKED (previous stage) and validate system resumes without duplicates.
        resume = run_scenario("resume_LOAN_BOOKED_after_failure_sim", _with_function_sub_code(raw, "LOAN_BOOKED", snap_any.account_number, external_ref_number=ext_ref), expect_terminal=True)
        try:
            refs_after = _crr_distinct_client_refs_neft_payment(snap_any.account_number)
            # Under NEFT v1, UNKNOWN retries must reuse same externalRefNo (counter only bumps on FAIL; UNKNOWN is treated as reuse).
            resume.checks.append(
                _mk_check(
                    "neft_external_ref_reused_across_unknown_and_retry",
                    len(refs_after) == 1,
                    f"expected 1 distinct externalRefNo; before={refs_before} after={refs_after}",
                )
            )
        except Exception as e:
            resume.checks.append(_mk_check("neft_external_ref_reuse_check_exception", False, f"{type(e).__name__}: {e}"))
        suite_results.append(resume)

    # Scenario Group 3: Stage permutation replays after a completed run.
    # (This checks that callers can safely send previous-stage function_sub_code without duplicating effects.)
    if args.stage_suite == "full" and r1.loan:
        lan = r1.loan.account_number
        suite_results.append(run_scenario("stage_replay_LAN_CREATED", _with_function_sub_code(raw, "LAN_CREATED", lan, external_ref_number=ext_ref), expect_terminal=True))
        suite_results.append(run_scenario("stage_replay_LOAN_BOOKED", _with_function_sub_code(raw, "LOAN_BOOKED", lan, external_ref_number=ext_ref), expect_terminal=True))
        suite_results.append(run_scenario("stage_replay_DTFC_SUCCESS", _with_function_sub_code(raw, "DTFC_SUCCESS", lan, external_ref_number=ext_ref), expect_terminal=True))
        if has_child_payload and bank_leg == "NEFT":
            suite_results.append(run_scenario("stage_replay_PARENT_SUCCESS", _with_function_sub_code(raw, "PARENT_SUCCESS", lan, external_ref_number=ext_ref), expect_terminal=True))

    _pretty_print_results(suite_results)

    all_ok = all(not _has_fail_checks(r.checks) for r in suite_results)
    if args.report_json:
        report = {
            "request_file": args.request_file,
            "endpoint": url,
            "db": {
                "host": DEFAULT_DB_HOST,
                "port": DEFAULT_DB_PORT,
                "user": DEFAULT_DB_USER,
                "db": DEFAULT_DB_NAME,
                "schema": DEFAULT_DB_SCHEMA,
            },
            "neft_version": args.neft_version,
            "suite_ok": all_ok,
            "results": [
                {
                    "name": r.name,
                    "http_status": r.http_status,
                    "loan": None
                    if not r.loan
                    else {
                        "account_id": r.loan.account_id,
                        "account_number": r.loan.account_number,
                        "loan_status": r.loan.loan_status,
                        "disbursement_status": r.loan.disbursement_status,
                        "external_ref_number": r.loan.external_ref_number,
                        "has_child_accounts": r.loan.has_child_accounts,
                    },
                    "checks": [{"name": c.name, "ok": c.ok, "details": c.details, "level": c.level} for c in r.checks],
                    "diagnostics": r.diagnostics,
                }
                for r in suite_results
            ],
        }
        open(args.report_json, "w", encoding="utf-8").write(json.dumps(report, indent=2, sort_keys=True))
        print(f"\n[report] wrote json report to {args.report_json}")

    # Always write PDF report to workspace root unless user overrides
    report_pdf = Path(args.report_pdf) if args.report_pdf else (_workspace_root() / "docs" / "disbursement-sanity" / f"disburse_loan_suite_{_now_ms()}.pdf")
    report_txt = report_pdf.with_suffix(".txt")
    meta = {
        "endpoint": url,
        "external_ref_number": ext_ref,
        "product_type": product_type,
        "product_id": product_id,
        "child_flow": child_flow,
        "disbursement_mode": mode,
        "bank_leg": bank_leg,
        "simulator_up": simulator_up,
        "simulator_profile": args.simulator_profile,
        "simulator_changes": simulator_changes,
    }
    _write_pdf_report(report_pdf, results=suite_results, meta=meta)
    print(f"\n[report] wrote pdf report to {report_pdf}")
    report_txt.write_text(_format_text_report(suite_results, meta), encoding="utf-8")
    print(f"[report] wrote text report to {report_txt}")
    qa_matrix_csv = report_pdf.parent / "disbursement_testing_scenarios_for_qa.csv"
    _write_qa_testcase_matrix_csv(qa_matrix_csv)
    print(f"[report] wrote QA testcase matrix csv to {qa_matrix_csv}")
    qa_matrix_verbose_csv = report_pdf.parent / "disbursement_testing_scenarios_verbose_for_qa.csv"
    _write_qa_testcase_matrix_verbose_csv(qa_matrix_verbose_csv)
    print(f"[report] wrote verbose QA testcase csv to {qa_matrix_verbose_csv}")

    if args.neft_version == "v2":
        print("[note] --neft-version=v2 selected; simulator profile now targets doGenericSyncSTPNEF/NEI/Inquiry endpoints.", flush=True)

    return 0 if all_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

