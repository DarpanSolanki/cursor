#!/usr/bin/env python3
"""
build_semantics_bone.py — DOMAIN SEMANTICS + FRAMEWORK LAYER into the KG (2026-07-31).

Emits typed nodes (queryable via kg search / kg concept / kg node):
  entity      — @Entity/@Table in money repos + purpose from db-code-map (else UNKNOWN)
  txn_type    — transaction_type string literals put into EC / constants (creators)
  gl_mech     — placeholder→IAD→account / posting-rule MECHANICS (not product-specific GL codes)
  redis_key   — patterns from redis-key-registry.md
  framework   — platform-lib + substrate mechanics AS USED HERE (Spring/Hibernate/Kafka/…)
  server      — server.port from application.properties

Enriches existing scheduler nodes with chunk when discoverable (edge note only; no duplicate nodes).

Honesty: semantics not derivable from code → purpose/lifecycle UNKNOWN; never invent GL account
numbers (those live in DB product_transaction_catalogue / placeholder mappings).

Usage: build_semantics_bone.py <accumulated_raw.jsonl> <repoDir> [...]
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # sliProd


def emit(o):
    sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")


MONEY_REPOS = {
    "trustt-platform-accounting",
    "trustt-platform-payments",
    "trustt-platform-los",
    "novopay-platform-lib",
    "trustt-platform-lib",
    "trustt-platform-batch",
}

TABLE_RE = re.compile(r'@Table\s*\(\s*name\s*=\s*"([^"]+)"')
ENTITY_CLASS_RE = re.compile(r"\b(?:public\s+)?(?:final\s+)?class\s+(\w+)")
COLUMN_RE = re.compile(
    r'@Column\s*\(\s*name\s*=\s*"([^"]+)"[^)]*\)\s*(?:\n\s*@[^\n]+)*\s*(?:private|protected)\s+[\w.<>,\s]+\s+(\w+)\s*;',
    re.M,
)
COLUMN_SIMPLE = re.compile(r'@Column\s*\(\s*name\s*=\s*"([^"]+)"')
TXN_PUT_RE = re.compile(
    r'(?:executionContext|object)\.put(?:Local)?\(\s*"transaction_type"\s*,\s*"([A-Z][A-Z0-9_-]+)"\s*\)'
)
TXN_CONST_RE = re.compile(
    r'public\s+static\s+final\s+String\s+(\w*TRANSACTION_TYPE\w*)\s*=\s*"([A-Z][A-Z0-9_-]+)"'
)
TXN_STATIC_RE = re.compile(
    r'(?:private|public)\s+static\s+final\s+String\s+TRANSACTION_TYPE\s*=\s*"([A-Z][A-Z0-9_-]+)"'
)
CHUNK_CONST_RE = re.compile(
    r'(?:public\s+static\s+final\s+int\s+CHUNK_SIZE\s*=\s*(\d+)|'
    r'put\(\s*"chunk"\s*,\s*(?:Constants\.WORKER_CHUNK_SIZE|CHUNK_SIZE|(\d+))\s*\))'
)
WORKER_CHUNK_DEF = re.compile(r'WORKER_CHUNK_SIZE\s*=\s*(\d+)')
PORT_RE = re.compile(r"^server\.port\s*=\s*(\d+)", re.M)
PURPOSE_RE = re.compile(r"^## Purpose\s*\n\n(.+?)(?:\n\n|\n## )", re.S | re.M)

KNOWN_TABLE: set[str] = set()
KNOWN_SCHED: set[str] = set()
KNOWN_PROC: set[str] = set()
KNOWN_DIAG: set[str] = set()
KNOWN_CASE: set[str] = set()


def repo_name(p: str) -> str:
    for seg in os.path.abspath(p).split(os.sep):
        if seg.startswith("novopay-") or seg.startswith("trustt-"):
            return seg
    return os.path.basename(p.rstrip(os.sep))


def load_known(tmp: str) -> None:
    for line in open(tmp, encoding="utf-8", errors="replace"):
        try:
            o = json.loads(line)
        except Exception:
            continue
        if o.get("t") != "node":
            continue
        kind = o.get("kind")
        if kind == "table":
            KNOWN_TABLE.add(o["id"][len("table:") :])
        elif kind == "scheduler":
            KNOWN_SCHED.add(o["id"])
        elif kind == "processor":
            KNOWN_PROC.add(o["id"][len("processor:") :])
        elif kind == "diag":
            KNOWN_DIAG.add(o["id"])
        elif kind == "case":
            KNOWN_CASE.add(o["id"])


def load_db_code_map_purposes() -> dict[str, tuple[str, str]]:
    """table -> (purpose_one_liner, src_path)."""
    out: dict[str, tuple[str, str]] = {}
    base = ROOT / "cursor-bundle" / "brain" / "accounting" / "db-code-map" / "tables"
    if not base.is_dir():
        return out
    for md in base.glob("*.md"):
        if md.name.startswith("_"):
            continue
        tbl = md.stem
        try:
            txt = md.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = PURPOSE_RE.search(txt)
        if m:
            purpose = " ".join(m.group(1).strip().split())
            if len(purpose) > 240:
                purpose = purpose[:237] + "..."
            out[tbl] = (purpose, str(md.relative_to(ROOT)))
        else:
            # first non-empty blockquote or paragraph after title
            for line in txt.splitlines():
                line = line.strip()
                if line.startswith(">") and len(line) > 3:
                    out[tbl] = (line.lstrip("> ").strip()[:240], str(md.relative_to(ROOT)))
                    break
    return out


def emit_entities(repos: list[str], purposes: dict[str, tuple[str, str]]) -> list[str]:
    """Return UNKNOWN purpose table names."""
    unknown: list[str] = []
    seen: set[str] = set()
    for repo_dir in repos:
        repo = repo_name(repo_dir)
        if repo not in MONEY_REPOS and not repo.startswith("trustt-platform-accounting"):
            # still scan accounting + payments + los + lib
            if repo not in (
                "trustt-platform-accounting",
                "trustt-platform-payments",
                "trustt-platform-los",
                "novopay-platform-lib",
                "trustt-platform-batch",
            ):
                continue
        for jf in glob.glob(os.path.join(repo_dir, "src", "main", "java", "**", "*.java"), recursive=True):
            try:
                txt = open(jf, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            if "@Entity" not in txt or "@Table" not in txt:
                continue
            rel = os.path.relpath(jf, start=str(ROOT))
            tm = TABLE_RE.search(txt)
            if not tm:
                continue
            tbl = tm.group(1)
            if tbl in seen:
                continue
            seen.add(tbl)
            cm = ENTITY_CLASS_RE.search(txt)
            ent = cm.group(1) if cm else None
            cols = []
            for cm2 in COLUMN_SIMPLE.finditer(txt):
                cols.append(cm2.group(1))
                if len(cols) >= 24:
                    break
            # Fallback: camelCase fields when @Column(name=…) omitted (Spring default naming)
            if not cols:
                for fm in re.finditer(
                    r"(?:private|protected)\s+(?:static\s+)?(?:final\s+)?[\w.<>,\s\[\]]+\s+(\w+)\s*;",
                    txt,
                ):
                    name = fm.group(1)
                    if name in ("serialVersionUID", "log", "LOG") or name.startswith("_"):
                        continue
                    # skip nested class noise
                    cols.append(name)
                    if len(cols) >= 24:
                        break
            # Also capture @Column without name= paired with field (rare)
            for fm in re.finditer(r"@Column\b[^\n]*\n\s*(?:@[^\n]+\n\s*)*(?:private|protected)\s+[\w.<>,\s]+\s+(\w+)\s*;", txt):
                if fm.group(1) not in cols:
                    cols.append(fm.group(1))
                if len(cols) >= 24:
                    break
            if tbl in purposes:
                purpose, psrc = purposes[tbl]
                purpose_src = psrc
            else:
                purpose = "UNKNOWN — no db-code-map purpose; derive from entity fields / writers only"
                purpose_src = rel
                unknown.append(tbl)
            eid = f"entity:{tbl}"
            emit(
                {
                    "t": "node",
                    "id": eid,
                    "kind": "entity",
                    "label": tbl,
                    "repo": repo,
                    "entity": ent,
                    "role": "domain_semantics",
                    "purpose": purpose,
                    "key_columns": cols,
                    "src": rel,
                    "purpose_src": purpose_src,
                }
            )
            if tbl in KNOWN_TABLE:
                emit(
                    {
                        "t": "edge",
                        "from": eid,
                        "to": f"table:{tbl}",
                        "rel": "maps_to",
                        "note": "jpa_entity",
                        "src": rel,
                    }
                )
            # link CRUD writers already on table as lifecycle hint
            # (edges are table<-processor; agent uses kg writes)
    return unknown


def emit_txn_types(repos: list[str]) -> None:
    """Discover transaction_type string values + creator files."""
    creators: dict[str, list[tuple[str, str]]] = {}  # type -> [(repo, src)]
    for repo_dir in repos:
        repo = repo_name(repo_dir)
        if "accounting" not in repo:
            continue
        for jf in glob.glob(os.path.join(repo_dir, "src", "main", "java", "**", "*.java"), recursive=True):
            try:
                txt = open(jf, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            if "transaction_type" not in txt and "TRANSACTION_TYPE" not in txt:
                continue
            rel = os.path.relpath(jf, start=str(ROOT))
            for m in TXN_PUT_RE.finditer(txt):
                creators.setdefault(m.group(1), []).append((repo, f"{rel}:{txt[:m.start()].count(chr(10))+1}"))
            for m in TXN_CONST_RE.finditer(txt):
                creators.setdefault(m.group(2), []).append((repo, f"{rel}:{txt[:m.start()].count(chr(10))+1}"))
            for m in TXN_STATIC_RE.finditer(txt):
                creators.setdefault(m.group(1), []).append((repo, f"{rel}:{txt[:m.start()].count(chr(10))+1}"))

    # Curated contrast for the two most-confused types (code-backed)
    notes = {
        "LOAN_PREPAYMENT": (
            "Full foreclosure/prepayment posting type. Set by prepayment/foreclosure processors "
            "(e.g. PopulateAdditionalAmountAndAccountDetailsForForeclosureProcessor). "
            "Distinct from LOAN_PART-PREPAYMENT (hyphenated)."
        ),
        "LOAN_PART-PREPAYMENT": (
            "Part-prepayment posting type (literal includes hyphen). Constant "
            "LoanConstants.PART_PREPAYMENT_TRANSACTION_TYPE. Set by part-prepayment processors."
        ),
        "BILLING": "EOD / force-bill installment billing (LoanAccountBilling* / ForceBillBillingSupport).",
        "INTEREST": "Interest accrual booking / posting (InterestAccrualBooking*).",
        "DEATH_FORECLOSURE": "DCF insurance writer member settlement posting.",
        "RSCH_DEATH_FORECLOSURE": "DCF parent reschedule / part-prepayment posting from DeathForeclosureInsuranceWriter.",
    }

    for ttype, srcs in sorted(creators.items()):
        # dedupe keep first 8
        uniq = []
        seen = set()
        for repo, src in srcs:
            if src in seen:
                continue
            seen.add(src)
            uniq.append({"repo": repo, "src": src})
            if len(uniq) >= 8:
                break
        primary = uniq[0]["src"] if uniq else "build_semantics_bone.py"
        nid = f"txn_type:{ttype}"
        emit(
            {
                "t": "node",
                "id": nid,
                "kind": "txn_type",
                "label": ttype,
                "repo": uniq[0]["repo"] if uniq else "trustt-platform-accounting",
                "role": "domain_semantics",
                "note": notes.get(ttype, "Discovered from EC put / TRANSACTION_TYPE constant — verify orch + catalogue."),
                "creators": uniq,
                "src": primary,
            }
        )
        # link known creator processors by filename stem
        for u in uniq[:5]:
            stem = Path(u["src"].split(":")[0]).stem
            bean = stem[0].lower() + stem[1:] if stem else ""
            if bean in KNOWN_PROC:
                emit(
                    {
                        "t": "edge",
                        "from": f"processor:{bean}",
                        "to": nid,
                        "rel": "sets_txn_type",
                        "note": ttype,
                        "src": u["src"],
                    }
                )


def emit_gl_mechanics() -> None:
    """Code-derived posting mechanics — not product GL account numbers (DB-bound)."""
    items = [
        {
            "id": "gl_mech:placeholder_resolution",
            "label": "placeholder → IAD / GL resolution",
            "note": (
                "Product transaction catalogue maps placeholder codes to internal_account_definition "
                "and/or general_ledger codes at product setup. Runtime posting resolves placeholders "
                "via catalogue + rules — concrete account numbers are DATA not code."
            ),
            "src": "trustt-platform-accounting/src/main/java/in/novopay/accounting/product/loan/processors/ValidateLoanTransactionPlaceholders.java:136",
            "unknown": (
                "Which GL account a given placeholder hits for a product/scheme — UNKNOWN without DB "
                "(product_transaction_catalogue / placeholder_master rows)."
            ),
        },
        {
            "id": "gl_mech:debit_credit_placeholders",
            "label": "debit/credit account placeholders on rules",
            "note": (
                "AccountingRulesConstants defines DEBIT_ACCOUNT_PLACEHOLDER / CREDIT_ACCOUNT_PLACEHOLDER "
                "keys used when authoring transaction_accounting_rule rows."
            ),
            "src": "trustt-platform-accounting/src/main/java/in/novopay/accounting/accountingrules/constant/AccountingRulesConstants.java:26",
            "unknown": "Per-rule debit/credit GL pairs — UNKNOWN without DB rule rows.",
        },
        {
            "id": "gl_mech:function_code_vs_gl",
            "label": "function_code is orch Control — not a GL account",
            "note": (
                "EC function_code (DEFAULT/APPROVE/REJECT/RESUBMIT) gates orchestration <Control> branches. "
                "It is NOT a GL function/account code. Probe 'function_code F → which GL' is a category error "
                "unless product data literally uses placeholder 'F' (not found as a code constant)."
            ),
            "src": "trustt-platform-accounting/src/main/java/in/novopay/accounting/common/AccountingConstants.java:60",
            "unknown": "Whether any product maps placeholder code literally 'F' — UNKNOWN (check placeholder_master in env DB).",
        },
        {
            "id": "gl_mech:ref_codes",
            "label": "additional_amount_details reference codes (PRIN_AMT, INT_AMT, …)",
            "note": "Posting amount legs keyed by ref codes (PRIN_AMT, INT_AMT, POS, BPI_AMT, …) — see skill gl-and-placeholders.md.",
            "src": ".cursor/skills/accounting-knowledge/gl-and-placeholders.md:14",
            "unknown": None,
        },
        {
            "id": "gl_mech:child_cg_prefix",
            "label": "child GL code CG prefix",
            "note": "Child loan partition gl_code uses CG + base; parent uses base only (ExecuteTransactionRulesProcessor).",
            "src": ".cursor/skills/accounting-knowledge/gl-and-placeholders.md:5",
            "unknown": None,
        },
    ]
    for it in items:
        emit(
            {
                "t": "node",
                "id": it["id"],
                "kind": "gl_mech",
                "label": it["label"],
                "repo": "trustt-platform-accounting",
                "role": "domain_semantics",
                "note": it["note"],
                "unknown": it.get("unknown"),
                "src": it["src"],
            }
        )


def emit_batch_enrichment(repos: list[str]) -> None:
    """Attach chunk notes to existing scheduler nodes; emit batch_cfg when chunk found."""
    worker_default = None
    for repo_dir in repos:
        if "accounting" not in repo_name(repo_dir):
            continue
        for jf in glob.glob(
            os.path.join(repo_dir, "src", "main", "java", "**", "Constants.java"), recursive=True
        ):
            try:
                txt = open(jf, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            m = WORKER_CHUNK_DEF.search(txt)
            if m:
                worker_default = int(m.group(1))
                emit(
                    {
                        "t": "node",
                        "id": "framework:batch.worker_chunk_default",
                        "kind": "framework",
                        "label": "Constants.WORKER_CHUNK_SIZE",
                        "repo": repo_name(repo_dir),
                        "role": "framework_batch",
                        "note": f"Default parallel worker chunk size = {worker_default}",
                        "src": f"{os.path.relpath(jf, ROOT)}:{txt[:m.start()].count(chr(10))+1}",
                    }
                )
                break

    for repo_dir in repos:
        repo = repo_name(repo_dir)
        if "accounting" not in repo:
            continue
        for jf in glob.glob(os.path.join(repo_dir, "src", "main", "java", "**", "*Config*.java"), recursive=True):
            try:
                txt = open(jf, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            if "CHUNK_SIZE" not in txt and '"chunk"' not in txt:
                continue
            rel = os.path.relpath(jf, start=str(ROOT))
            chunk_val = None
            m = re.search(r"CHUNK_SIZE\s*=\s*(\d+)", txt)
            if m:
                chunk_val = int(m.group(1))
            elif "Constants.WORKER_CHUNK_SIZE" in txt and worker_default:
                chunk_val = worker_default
            # derive job name candidates from class
            cm = ENTITY_CLASS_RE.search(txt)
            cls = cm.group(1) if cm else Path(jf).stem
            # try to find matching scheduler
            candidates = []
            for stem in (
                cls.replace("BatchConfigService", "")
                .replace("BatchJobConfig", "")
                .replace("ConfigService", "")
                .replace("Config", ""),
                cls,
            ):
                for cand in (f"scheduler:{stem}", f"scheduler:{stem[0].lower()+stem[1:]}" if stem else ""):
                    if cand and cand in KNOWN_SCHED:
                        candidates.append(cand)
            # also JobBuilder name
            for jm in re.finditer(r'JobBuilder\s*\(\s*"([^"]+)"', txt):
                sid = f"scheduler:{jm.group(1)}"
                if sid in KNOWN_SCHED:
                    candidates.append(sid)
            if not candidates and chunk_val is None:
                continue
            bid = f"batch_cfg:{cls}"
            emit(
                {
                    "t": "node",
                    "id": bid,
                    "kind": "batch_cfg",
                    "label": cls,
                    "repo": repo,
                    "role": "domain_semantics",
                    "chunk": chunk_val,
                    "skip_retry": "UNKNOWN — skipLimit/retryLimit not found as constants in this file; check CustomStepBuilder / job params",
                    "note": f"chunk={chunk_val if chunk_val is not None else 'UNKNOWN'}; skip/retry UNKNOWN unless configured in shared batch infra",
                    "src": rel,
                }
            )
            for sid in candidates[:3]:
                emit(
                    {
                        "t": "edge",
                        "from": sid,
                        "to": bid,
                        "rel": "has_batch_cfg",
                        "note": f"chunk={chunk_val}",
                        "src": rel,
                    }
                )


def emit_redis_keys() -> None:
    path = ROOT / "cursor-bundle" / "brain" / "platform" / "redis-key-registry.md"
    if not path.is_file():
        return
    txt = path.read_text(encoding="utf-8", errors="replace")
    # table rows: | key | TTL | ...
    row = re.compile(
        r"\|\s*`([^`|]+)`\s*\|\s*([YNyn]|Default|—|-)\s*\|([^|]*)\|([^|]*)\|"
    )
    # looser: | pattern | TTL | value | purpose |
    row2 = re.compile(r"\|\s*([^|]+?)\s*\|\s*(Y|N|Default|Y / varies|—)\s*\|\s*([^|]*)\|\s*([^|]*)\|")
    section = "unknown"
    n = 0
    for line in txt.splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
            continue
        m = row2.match(line)
        if not m:
            continue
        key = m.group(1).strip().strip("`")
        if key.lower().startswith("key pattern") or key.startswith("---") or not key:
            continue
        ttl = m.group(2).strip()
        ttl_notes = m.group(3).strip()
        purpose = m.group(4).strip()
        safe = re.sub(r"[^A-Za-z0-9_.+-]+", "_", key)[:80]
        nid = f"redis_key:{safe}"
        emit(
            {
                "t": "node",
                "id": nid,
                "kind": "redis_key",
                "label": key,
                "repo": section,
                "role": "framework_redis",
                "ttl": ttl,
                "ttl_notes": ttl_notes,
                "note": purpose,
                "src": f"cursor-bundle/brain/platform/redis-key-registry.md#{section}",
            }
        )
        n += 1
        if n >= 80:
            break


def emit_framework() -> None:
    """Substrate mechanics with file:line provenance + links to known defect classes."""
    items = [
        {
            "id": "framework:spring.txn.processor_orchestrator",
            "label": "Spring txn boundaries in orchestrated Request",
            "note": (
                "ProcessorOrchestrator uses @Transactional(REQUIRES_NEW, READ_COMMITTED) for processor "
                "execution paths; XML <Transaction> blocks force PROPAGATION_REQUIRES_NEW via "
                "PlatformTransactionManager. Orchestration owns boundaries — avoid nested @Transactional "
                "in processors unless intentional."
            ),
            "src": "novopay-platform-lib/infra-navigation/src/main/java/in/novopay/infra/navigation/orchestrator/ProcessorOrchestrator.java:58",
            "explains": ["diag"],  # linked below if present
        },
        {
            "id": "framework:hibernate.autoflush_after_cas",
            "label": "Hibernate auto-flush after CAS is dangerous",
            "note": (
                "After ChildClmtStateMachineService/LoanAccountStateMachineService.transition (or "
                "patchJsonFields), NEVER mutate the same managed entity with setters. Outer "
                "disburseLoan persistence context auto-flushes stale in-memory state (no @PreUpdate on "
                "AbstractBaseEntity) and can revert the CAS. CAS is the sole writer of those columns."
            ),
            "src": "cursor-bundle/memory/feedback_no_inmem_mutation_after_cas.md:12",
            "explains_case": True,
        },
        {
            "id": "framework:kafka.consumer_wiring",
            "label": "Kafka consumer wiring (NovopayMessageBrokerConsumer)",
            "note": (
                "Accounting consumers implement NovopayMessageBrokerConsumer (infra-message-broker) and "
                "are registered via messagebroker XML — not @KafkaListener concurrency annotations in "
                "service code. Explicit concurrency / DLQ / maxPollRecords often ABSENT at consumer class "
                "(see GAP-065). Retry semantics: at-least-once + app-level Redis locks / status gates."
            ),
            "src": "trustt-platform-accounting/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java:37",
            "unknown": "Per-topic concurrency, DLQ topic names, Spring Kafka retry backoff — UNKNOWN without messagebroker XML + broker config for the env.",
        },
        {
            "id": "framework:platform.service_orchestrator",
            "label": "ServiceOrchestrator lifecycle",
            "note": (
                "HTTP → ServiceGatewayController → RequestProcessorImpl → ServiceOrchestrator walks "
                "orchestration XML (validators/processors/APIs/controls). EC put vs putLocal; internal "
                "calls via CallInternalOrchestrationProcessor with explicit txn flag."
            ),
            "src": "novopay-platform-lib/infra-navigation/src/main/java/in/novopay/infra/navigation/orchestrator/ServiceOrchestrator.java:1",
        },
        {
            "id": "framework:http.no_circuit_breaker",
            "label": "NovopayHttpAPIClient — no retry/circuit breaker",
            "note": "Outbound internal HTTP has no retry/circuit breaker (GAP High). Transient failures can leave cross-service partial progress.",
            "src": "novopay-platform-lib/infra-http-client/src/main/java/in/novopay/infra/api/client/NovopayHttpAPIClient.java:54",
        },
        {
            "id": "framework:redis.cache_client",
            "label": "Redis via NovopayCacheClient / RedisCacheClient",
            "note": "infra-cache wraps Redis; 4-arg set may omit TTL (keys persist). flushDb() is High risk. See redis_key:* nodes.",
            "src": "novopay-platform-lib/infra-cache/src/main/java/in/novopay/infra/cache/RedisCacheClient.java:164",
        },
        {
            "id": "framework:elastic.module",
            "label": "Elasticsearch via infra-essentials-elasticsearch",
            "note": "Module present in platform-lib; usage is service-specific. Do not assume all services index to Elastic.",
            "src": "novopay-platform-lib/infra-essentials-elasticsearch",
            "unknown": "Per-service index names / query sites — UNKNOWN without targeted service scan (not fully enumerated this bone).",
        },
        {
            "id": "framework:batch.force_async_skip",
            "label": "Batch force_async + SkipListener Future unwrap",
            "note": (
                "batch_job_parameter.force_async=TRUE uses AsyncItemWriter; SkipListener receives Future not item. "
                "BatchWriterSkipItemSupport.resolveSkipItem required."
            ),
            "src": ".cursor/platform-lib.md:26",
        },
    ]
    for it in items:
        emit(
            {
                "t": "node",
                "id": it["id"],
                "kind": "framework",
                "label": it["label"],
                "repo": "novopay-platform-lib" if "platform-lib" in it["src"] or it["src"].startswith("novopay") else "trustt-platform-accounting",
                "role": "framework_layer",
                "note": it["note"],
                "unknown": it.get("unknown"),
                "src": it["src"],
            }
        )
        # wire explains → known diags/cases by keyword search in ids
        if it.get("explains_case"):
            for cid in KNOWN_CASE:
                cl = cid.lower()
                if any(k in cl for k in ("clmt", "autoflush", "cas_race", "state_machine", "4c339282f")):
                    emit(
                        {
                            "t": "edge",
                            "from": it["id"],
                            "to": cid,
                            "rel": "explains",
                            "note": "framework_defect_class",
                            "src": it["src"],
                        }
                    )
                    break
            for did in KNOWN_DIAG:
                dl = did.lower()
                # Avoid false positives like CollectorCash* matching "cas"
                if any(k in dl for k in ("autoflush", "clmt_race", "cas_transition", "inmem_mutation", "neft_v2_child")):
                    emit(
                        {
                            "t": "edge",
                            "from": it["id"],
                            "to": did,
                            "rel": "explains",
                            "note": "framework_defect_class",
                            "src": it["src"],
                        }
                    )
                    break
            # always link memory feedback as doc if present later via docs builder
            emit(
                {
                    "t": "edge",
                    "from": it["id"],
                    "to": "table:loan_account_events_queue",
                    "rel": "constrains",
                    "note": "no_inmem_mutation_after_cas",
                    "src": it["src"],
                }
            )

    # platform-lib file → blast warning node for impact
    emit(
        {
            "t": "node",
            "id": "framework:platform_lib.blast_radius",
            "kind": "framework",
            "label": "platform-lib change blast radius",
            "repo": "novopay-platform-lib",
            "role": "framework_layer",
            "note": (
                "Any change under novopay-platform-lib affects all services scanning in.novopay "
                "(orchestration, cache, HTTP client, Kafka base, batch skip). Prefer impact on "
                "framework:* + service:* dependents; HIGH RISK for money paths."
            ),
            "src": ".cursor/platform-lib.md:54",
        }
    )


def emit_servers(repos: list[str]) -> None:
    for repo_dir in repos:
        repo = repo_name(repo_dir)
        for prop in glob.glob(os.path.join(repo_dir, "**", "application.properties"), recursive=True):
            if "/build/" in prop or "/test/" in prop:
                continue
            try:
                txt = open(prop, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            m = PORT_RE.search(txt)
            if not m:
                continue
            rel = os.path.relpath(prop, start=str(ROOT))
            port = m.group(1)
            emit(
                {
                    "t": "node",
                    "id": f"server:{repo}",
                    "kind": "server",
                    "label": f"{repo}:{port}",
                    "repo": repo,
                    "role": "framework_server",
                    "port": int(port),
                    "note": f"server.port={port} from application.properties; Tomcat threadpool UNKNOWN unless server.tomcat.* set (often Boot defaults).",
                    "src": f"{rel}:{txt[:m.start()].count(chr(10))+1}",
                }
            )
            emit(
                {
                    "t": "edge",
                    "from": f"service:{repo}",
                    "to": f"server:{repo}",
                    "rel": "listens_on",
                    "note": f"port={port}",
                    "src": rel,
                }
            )
            break  # first props file per repo


def emit_unknown_index(unknown_tables: list[str]) -> None:
    emit(
        {
            "t": "node",
            "id": "semantics:unknown_index",
            "kind": "diag",
            "label": "UNKNOWN domain semantics index",
            "class": "unknown_semantics",
            "repo": "workspace",
            "role": "honesty",
            "note": (
                f"{len(unknown_tables)} money @Entity tables lack db-code-map purpose. "
                "Also: product-specific GL accounts; Kafka DLQ/concurrency; Tomcat pools; "
                "per-job skip/retry when not in Config. See UNKNOWN list in semantics bone report."
            ),
            "unknown_tables_sample": unknown_tables[:40],
            "src": "cursor-bundle/kg/bin/build_semantics_bone.py",
        }
    )


def main():
    if len(sys.argv) < 3:
        print("usage: build_semantics_bone.py <raw.jsonl> <repo>...", file=sys.stderr)
        sys.exit(2)
    tmp = sys.argv[1]
    repos = sys.argv[2:]
    load_known(tmp)
    purposes = load_db_code_map_purposes()
    unknown = emit_entities(repos, purposes)
    emit_txn_types(repos)
    emit_gl_mechanics()
    emit_batch_enrichment(repos)
    emit_redis_keys()
    emit_framework()
    emit_servers(repos)
    emit_unknown_index(unknown)


if __name__ == "__main__":
    main()
