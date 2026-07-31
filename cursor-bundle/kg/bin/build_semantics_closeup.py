#!/usr/bin/env python3
"""
build_semantics_closeup.py — fold DB/config-derived semantics (2026-07-31 close-up).

Reads curated dump cursor-bundle/kg/curated/semantics_closeup.jsonl (from local DB)
plus live config/code scans. Emits:
  gl_rule, txn_type (DB reconcile), framework config (Kafka/Tomcat/skip),
  entity purpose backfill (money-core), batch_cfg↔scheduler merge fixes.

Usage: build_semantics_closeup.py <accumulated_raw.jsonl> <repoDir> [...]
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CURATED = ROOT / "cursor-bundle" / "kg" / "curated" / "semantics_closeup.jsonl"


def emit(o):
    sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")


KNOWN_TXN: set[str] = set()
KNOWN_SCHED: set[str] = set()
KNOWN_BATCH: set[str] = set()
KNOWN_ENTITY: dict[str, dict] = {}
CRUD_WRITES: dict[str, set[str]] = {}  # table -> processors
CRUD_READS: dict[str, set[str]] = {}


def load_known(tmp: str) -> None:
    for line in open(tmp, encoding="utf-8", errors="replace"):
        try:
            o = json.loads(line)
        except Exception:
            continue
        if o.get("t") != "node":
            continue
        kind, nid = o.get("kind"), o.get("id", "")
        if kind == "txn_type":
            KNOWN_TXN.add(nid[len("txn_type:") :])
        elif kind == "scheduler":
            KNOWN_SCHED.add(nid)
        elif kind == "batch_cfg":
            KNOWN_BATCH.add(nid)
        elif kind == "entity":
            KNOWN_ENTITY[nid[len("entity:") :]] = o
    # edges for CRUD
    for line in open(tmp, encoding="utf-8", errors="replace"):
        try:
            o = json.loads(line)
        except Exception:
            continue
        if o.get("t") != "edge":
            continue
        rel, fr, to = o.get("rel"), o.get("from", ""), o.get("to", "")
        if to.startswith("table:") and fr.startswith("processor:"):
            tbl = to[len("table:") :]
            if rel == "writes":
                CRUD_WRITES.setdefault(tbl, set()).add(fr[len("processor:") :])
            elif rel == "reads":
                CRUD_READS.setdefault(tbl, set()).add(fr[len("processor:") :])


# Money-core tables touched by suite/flows (purpose backfill target ~50)
MONEY_CORE = [
    "loan_account", "loan_due_details", "loan_installment_details", "interest_accrual_details",
    "penal_interest_accrual_details", "loan_account_billing_details", "transaction_master",
    "transaction_details", "transaction_partition_details", "transaction_catalogue",
    "transaction_accounting_rule", "placeholder_master", "internal_account_definition",
    "internal_account", "general_ledger", "child_general_ledger", "account", "account_balance",
    "loan_account_payments_details", "loan_disbursement_transaction", "loan_account_events_queue",
    "client_request_response_log", "prepayment_details", "loan_account_part_prepayment_details",
    "death_foreclosure_details", "loan_account_closure_details", "loan_account_derived_fields",
    "product_transaction_catalogue__placeholder__iad", "product__transaction_catalogue",
    "loan_product", "product_scheme", "loan_repayment_schedule_details", "waiver_details",
    "waiver__loan_due_details", "loan_account_charge_details", "loan_disbursement_mode_details",
    "loan_account_excess_amount_refund_details", "loan_account_restructuring_details",
    "loan_account_rebooking_details", "loan_provisioning_details", "asset_criteria_slabs",
    "loan_product_asset_criteria", "trial_balance", "repayment_mandate_details",
    "repayment_account_details", "loan_due_details__loan_account_payments_details",
    "loan_due_details__repayment_transaction", "transaction_metadata", "transaction_reversal_details",
    "loan_account_nominee_details", "presentation_bounce_charge_details",
]


def emit_curated() -> set[str]:
    """Return DB txn types seen."""
    db_types: set[str] = set()
    meta_path = CURATED.with_suffix('.meta.json')
    if meta_path.is_file():
        try:
            db_types |= set(json.loads(meta_path.read_text()).get('db_txn_types') or [])
        except Exception:
            pass
    if not CURATED.is_file():
        emit({
            "t": "node", "id": "diag:semantics_closeup_missing_dump", "kind": "diag",
            "label": "semantics_closeup.jsonl missing", "class": "unknown_semantics",
            "note": "Run close-up dump against local DB to refresh curated/semantics_closeup.jsonl",
            "src": "build_semantics_closeup.py",
        })
        return db_types
    for line in CURATED.open(encoding="utf-8"):
        try:
            o = json.loads(line)
        except Exception:
            continue
        if o.get("t") in ("node", "edge"):
            # fix verifies edges to point at concrete rules when possible
            if o.get("t") == "edge" and o.get("rel") == "verifies" and str(o.get("to", "")).endswith("#"):
                continue  # skip broken prefix edges
            emit(o)
            if o.get("t") == "node" and o.get("kind") == "gl_rule" and o.get("txn_type"):
                db_types.add(o["txn_type"])
    return db_types


def reconcile_txn_types(db_types: set[str]) -> None:
    code_only = sorted(KNOWN_TXN - db_types)
    db_only = sorted(db_types - KNOWN_TXN)
    for t in db_only:
        emit({
            "t": "node", "id": f"txn_type:{t}", "kind": "txn_type", "label": t,
            "repo": "trustt-platform-accounting", "role": "domain_semantics",
            "note": "DB-only — present in transaction_catalogue(+rules) local dump; no EC put/constant discovered in bone scan",
            "origin": "db", "src": "mfi_accounting.transaction_catalogue (semantics_closeup dump)",
        })
    for t in code_only:
        emit({
            "t": "node", "id": f"txn_type_flag:code_only:{t}", "kind": "txn_type", "label": f"CODE_ONLY {t}",
            "repo": "trustt-platform-accounting", "role": "reconcile",
            "note": "Code/constant-derived txn_type not found in local transaction_catalogue rules dump — may be unused, env-specific, or catalogue-only without rules",
            "origin": "code_only", "src": "build_semantics_closeup.py reconcile",
        })
    emit({
        "t": "node", "id": "txn_reconcile:summary", "kind": "diag", "label": "txn_type DB vs code reconcile",
        "class": "reconcile", "repo": "workspace",
        "note": f"db_types={len(db_types)} code_types={len(KNOWN_TXN)} db_only={db_only} code_only={code_only}",
        "src": "build_semantics_closeup.py",
    })


def emit_kafka_config() -> None:
    mb = ROOT / "trustt-platform-accounting" / "deploy" / "application" / "messagebroker" / "MessageBroker.xml"
    if not mb.is_file():
        return
    txt = mb.read_text(encoding="utf-8", errors="replace")
    # No DLQ / retry tags in consumer blocks
    for m in re.finditer(
        r"<Consumer>\s*<consumersGroupIdPrefix>([^<]+)</consumersGroupIdPrefix>\s*"
        r"<topicPrefix>([^<]+)</topicPrefix>\s*"
        r"<pollTime>([^<]+)</pollTime>\s*"
        r"<numberOfThreads>([^<]+)</numberOfThreads>\s*"
        r"<bean>([^<]+)</bean>\s*</Consumer>",
        txt,
        re.S,
    ):
        group, topic, poll, threads, bean = (x.strip() for x in m.groups())
        nid = f"framework:kafka.consumer:{bean}"
        emit({
            "t": "node", "id": nid, "kind": "framework", "label": f"Kafka consumer {bean}",
            "repo": "trustt-platform-accounting", "role": "framework_kafka",
            "topic_prefix": topic, "group_prefix": group, "poll_time_ms": poll,
            "number_of_threads": threads,
            "note": (
                f"MessageBroker.xml: topicPrefix={topic} groupPrefix={group} "
                f"pollTime={poll} numberOfThreads={threads}. "
                "No DLQ topic, no consumer retry/backoff tags in this XML (producer has optional retryBackOffMs only). "
                "Env suffix appended at runtime to prefixes."
            ),
            "dlq": "ABSENT_IN_CONFIG",
            "retry_backoff": "ABSENT_IN_CONSUMER_CONFIG",
            "env": "local_xml",
            "src": f"trustt-platform-accounting/deploy/application/messagebroker/MessageBroker.xml:{txt[:m.start()].count(chr(10))+1}",
        })
    emit({
        "t": "node", "id": "framework:kafka.dlq_absent_accounting", "kind": "framework",
        "label": "Accounting Kafka DLQ absent in MessageBroker.xml",
        "repo": "trustt-platform-accounting", "role": "framework_kafka",
        "note": "No dead-letter / DLQ consumer or producer config in accounting MessageBroker.xml — failure handling is app-level (status gates / Redis locks).",
        "src": "trustt-platform-accounting/deploy/application/messagebroker/MessageBroker.xml",
        "env": "local_xml",
    })


def emit_tomcat() -> None:
    """server.tomcat.* overrides vs Boot defaults."""
    found_override = False
    for prop in glob.glob(str(ROOT / "trustt-platform-*" / "src" / "main" / "resources" / "application.properties")):
        try:
            txt = open(prop, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if "server.tomcat" in txt:
            found_override = True
            rel = os.path.relpath(prop, ROOT)
            for line in txt.splitlines():
                if line.strip().startswith("server.tomcat"):
                    emit({
                        "t": "node", "id": f"framework:tomcat:{rel}:{line.split('=',1)[0].strip()}",
                        "kind": "framework", "label": line.strip(),
                        "repo": rel.split("/")[0], "role": "framework_server",
                        "note": "Explicit server.tomcat.* override", "src": rel, "env": "app_props",
                    })
    if not found_override:
        emit({
            "t": "node", "id": "framework:tomcat.boot_defaults", "kind": "framework",
            "label": "Tomcat thread pool = Spring Boot defaults",
            "repo": "workspace", "role": "framework_server",
            "note": (
                "No server.tomcat.max-threads / threads-max / accept-count found in trustt-platform-*/src/main/resources/application.properties. "
                "Embedded Tomcat uses Spring Boot defaults (historically max-threads≈200 unless version differs). "
                "server.port alone is set per service (see server:* nodes)."
            ),
            "src": "build_semantics_closeup.py scan application.properties",
            "env": "boot_defaults",
        })


def emit_skip_retry() -> None:
    """Infra skipLimit + jobs that set faultTolerant."""
    csb = ROOT / "novopay-platform-lib" / "infra-batch" / "src" / "main" / "java" / "in" / "novopay" / "infra" / "batch" / "builder" / "CustomStepBuilder.java"
    if csb.is_file():
        txt = csb.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"skipLimit\(Integer\.MAX_VALUE\)", txt)
        line = txt[: m.start()].count("\n") + 1 if m else 131
        emit({
            "t": "node", "id": "framework:batch.skipLimit_max", "kind": "framework",
            "label": "CustomStepBuilder skipLimit=Integer.MAX_VALUE when faultTolerant",
            "repo": "novopay-platform-lib", "role": "framework_batch",
            "note": (
                "When jobConfigParameters.faultTolerant=true, worker steps use "
                "faultTolerant().skip(Exception.class).skipLimit(Integer.MAX_VALUE). "
                "retryLimit not set on CustomStepBuilder path (ParallelRemoteBatchJob has retryLimit(3) separately)."
            ),
            "skip_limit": "Integer.MAX_VALUE",
            "retry_limit": "ABSENT_ON_CUSTOM_STEP (see ParallelRemoteBatchJob=3)",
            "src": f"novopay-platform-lib/infra-batch/.../CustomStepBuilder.java:{line}",
        })
    pr = ROOT / "novopay-platform-lib" / "infra-batch" / "src" / "main" / "java" / "in" / "novopay" / "infra" / "batch" / "service" / "ParallelRemoteBatchJob.java"
    if pr.is_file():
        txt = pr.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"retryLimit\((\d+)\)", txt)
        if m:
            emit({
                "t": "node", "id": "framework:batch.retryLimit_remote", "kind": "framework",
                "label": f"ParallelRemoteBatchJob retryLimit={m.group(1)}",
                "repo": "novopay-platform-lib", "role": "framework_batch",
                "retry_limit": int(m.group(1)),
                "src": f"novopay-platform-lib/infra-batch/.../ParallelRemoteBatchJob.java:{txt[:m.start()].count(chr(10))+1}",
            })
    # Jobs enabling faultTolerant
    for jf in glob.glob(str(ROOT / "trustt-platform-accounting" / "src" / "main" / "java" / "**" / "*Config*.java"), recursive=True):
        try:
            txt = open(jf, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if 'put("faultTolerant"' not in txt and "put(\"faultTolerant\"" not in txt and "faultTolerant\", true" not in txt:
            if "faultTolerant\", true" not in txt and 'faultTolerant", true' not in txt:
                continue
        if "faultTolerant" not in txt or "true" not in txt:
            continue
        if not re.search(r'faultTolerant"\s*,\s*true', txt):
            continue
        rel = os.path.relpath(jf, ROOT)
        cls = Path(jf).stem
        bid = f"batch_cfg:{cls}"
        emit({
            "t": "node", "id": bid, "kind": "batch_cfg", "label": cls,
            "repo": "trustt-platform-accounting", "role": "domain_semantics",
            "fault_tolerant": True,
            "skip_limit": "Integer.MAX_VALUE (via CustomStepBuilder)",
            "retry_limit": "see framework:batch.retryLimit_remote if remote parallel",
            "note": "faultTolerant=true → skipLimit MAX_VALUE; chunk may be WORKER_CHUNK_SIZE",
            "src": rel,
        })


def merge_batch_scheduler() -> None:
    """Link batch_cfg ↔ scheduler by normalized job name; avoid duplicate identities."""
    # For each batch_cfg, try scheduler with Job suffix / camelCase
    for bid in list(KNOWN_BATCH):
        cls = bid.split(":", 1)[-1]
        stem = re.sub(
            r"(BatchConfigService|BatchJobConfig|ConfigService|JobConfig|Config)$",
            "",
            cls,
        )
        cands = [
            f"scheduler:{stem}",
            f"scheduler:{stem}Job",
            f"scheduler:{stem[0].lower()+stem[1:]}" if stem else "",
            f"scheduler:{stem[0].lower()+stem[1:]}Job" if stem else "",
        ]
        for sid in cands:
            if sid and sid in KNOWN_SCHED:
                emit({
                    "t": "edge", "from": sid, "to": bid, "rel": "has_batch_cfg",
                    "note": "closeup_merge", "src": "build_semantics_closeup.py",
                })
                break


def purpose_backfill() -> None:
    """Backfill UNKNOWN purposes for money-core from CRUD usage evidence."""
    for tbl in MONEY_CORE:
        ent = KNOWN_ENTITY.get(tbl)
        if not ent:
            continue
        purpose = ent.get("purpose") or ""
        if purpose and not purpose.startswith("UNKNOWN"):
            continue
        writers = sorted(CRUD_WRITES.get(tbl, []))[:8]
        readers = sorted(CRUD_READS.get(tbl, []))[:8]
        if not writers and not readers:
            continue
        bits = []
        if writers:
            bits.append("written by " + ", ".join(writers[:5]))
        if readers:
            bits.append("read by " + ", ".join(readers[:5]))
        new_purpose = (
            f"Money-core usage: {'; '.join(bits)}. "
            f"(purpose backfilled from CRUD edges 2026-07-31; refine via db-code-map when available)"
        )
        emit({
            "t": "node", "id": f"entity:{tbl}", "kind": "entity", "label": tbl,
            "repo": ent.get("repo") or "trustt-platform-accounting",
            "entity": ent.get("entity"), "role": "domain_semantics",
            "purpose": new_purpose,
            "key_columns": ent.get("key_columns") or [],
            "src": ent.get("src") or "build_semantics_closeup.py",
            "purpose_src": "CRUD edges + money-core backfill",
            "purpose_backfill": True,
        })


def fix_activation_anchors_note() -> None:
    emit({
        "t": "node", "id": "framework:lib_path_anchor", "kind": "framework",
        "label": "platform-lib checkout path = novopay-platform-lib",
        "repo": "novopay-platform-lib", "role": "framework_layer",
        "note": (
            "Workspace checkout directory is novopay-platform-lib (not trustt-platform-lib). "
            "KG service id may still be trustt-platform-lib alias; provenance paths must use novopay-platform-lib/…"
        ),
        "src": "novopay-platform-lib/",
    })


def main():
    if len(sys.argv) < 2:
        print("usage: build_semantics_closeup.py <raw.jsonl> [repos...]", file=sys.stderr)
        sys.exit(2)
    tmp = sys.argv[1]
    load_known(tmp)
    db_types = emit_curated()
    reconcile_txn_types(db_types)
    emit_kafka_config()
    emit_tomcat()
    emit_skip_retry()
    merge_batch_scheduler()
    purpose_backfill()
    fix_activation_anchors_note()


if __name__ == "__main__":
    main()
