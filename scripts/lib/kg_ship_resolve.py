#!/usr/bin/env python3
"""Resolve changed file paths → apiName(s) via KG + grep (smart ship-loop targeting)."""
from __future__ import annotations

import re
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KG_DB = ROOT / "cursor-bundle/kg/data/kg.db"

_LIB = str(ROOT / "scripts/lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from change_test_map import api_from_class_stem, api_from_path  # noqa: E402

# Path segment → primary sanity api when KG/grep yields nothing (last resort).
# Never invent disburseLoan for unrelated MessageBroker / generic accounting paths.
# More-specific needles first (penal before interest; notifications before generic).
DOMAIN_PRIMARY_API: tuple[tuple[str, str], ...] = (
    ("loaninstallmentduenotification", "loanInstallmentDueNotificationJob"),
    ("loaninstallmentbouncenotification", "loanInstallmentBounceNotificationJob"),
    ("/batchnew/notifications/", "loanInstallmentDueNotificationJob"),
    ("penalinterestaccrualcalculation", "penalInterestAccrualCalculation"),
    ("penalinterestaccrualbooking", "penalInterestAccrualBooking"),
    ("/batchnew/penal/", "penalInterestAccrualCalculation"),
    ("loanadvancerepayment", "loanAdvanceRepayment"),
    ("interestaccrualbooking", "interestAccrualPosting"),
    ("interestaccrualposting", "interestAccrualPosting"),
    ("interestaccrualcalculation", "interestAccrualCalculation"),
    ("/batchnew/interest/", "interestAccrualCalculation"),
    ("/loan/disbursement/", "disburseLoan"),
    ("/disbursement/", "disburseLoan"),
    ("/foreclos/", "fetchLoanForeclosureSimulationDetails"),
    ("/prepayment/", "createPrepaymentDetails"),
    ("/repayment/", "loanRepayment"),
    ("/repay/", "loanRepayment"),
    ("/interest/accrual", "interestAccrualCalculation"),
    # Trailing slash required: bare "/dpi" matched scripts/dpic/ and dpi-*.md
    # → false getLoanAccountOverviewDetails and lagged harness impact mapping.
    ("/batchnew/dpi/", "getLoanAccountOverviewDetails"),
    ("/dpi/", "getLoanAccountOverviewDetails"),
    ("/billing/", "dpiBilling"),
)

# Prefer these when multiple requests share a util (bank-call util → disburse first).
API_PRIORITY: tuple[str, ...] = (
    "disburseLoan",
    "loanRepayment",
    "fetchLoanForeclosureSimulationDetails",
    "createPrepaymentDetails",
    "getLoanAccountOverviewDetails",
    "getLoanAccountBPIAmount",
    "getLoanAccountSummaryDetails",
)


def _kg_conn() -> sqlite3.Connection | None:
    if not KG_DB.is_file():
        return None
    try:
        return sqlite3.connect(KG_DB)
    except sqlite3.Error:
        return None


def _repo_dir(repo: str) -> Path | None:
    d = ROOT / repo
    return d if (d / ".git").is_dir() or (d / "src").is_dir() else None


def processor_bean_from_java_name(class_name: str) -> str:
    if class_name.endswith("Processor"):
        return class_name[0].lower() + class_name[1:]
    return ""


def requests_for_processor_bean(bean: str, conn: sqlite3.Connection | None = None) -> list[str]:
    if not bean:
        return []
    own = conn is None
    if own:
        conn = _kg_conn()
    if not conn:
        return []
    pid = f"processor:{bean}"
    rows = conn.execute(
        "SELECT src_id FROM edges WHERE dst_id=? AND src_id LIKE 'request:%' AND rel='invokes'",
        (pid,),
    ).fetchall()
    if own:
        conn.close()
    return sorted({_normalize_api_name(r[0].split(":", 1)[1]) for r in rows})


def _normalize_api_name(name: str) -> str:
    """KG sometimes stores request labels as repo/apiName — ship cases need bare apiName."""
    n = (name or "").strip()
    if n.startswith("request:"):
        n = n.split(":", 1)[1]
    if "/" in n:
        n = n.rsplit("/", 1)[-1]
    return n


def requests_for_batch_job(job_name: str, conn: sqlite3.Connection | None = None) -> list[str]:
    """Return apiName only when KG knows the batch job — never invent from a class stem."""
    if not job_name:
        return []
    own = conn is None
    if own:
        conn = _kg_conn()
    if not conn:
        return []
    nid = f"batch_job:{job_name}"
    row = conn.execute("SELECT id FROM nodes WHERE id=? OR label=?", (nid, job_name)).fetchone()
    if own:
        conn.close()
    return [job_name] if row else []


def _grep_java_referencing(class_name: str, repo_dir: Path) -> list[str]:
    src = repo_dir / "src/main/java"
    if not src.is_dir():
        return []
    # `rg` may be absent (or only a shell function, which subprocess cannot see);
    # fall back to POSIX grep so ship-path resolution never hard-fails on tooling.
    for argv in (["rg", "-l", class_name, str(src)],
                 ["grep", "-rl", class_name, str(src)]):
        try:
            out = subprocess.run(argv, capture_output=True, text=True, check=False)
            break
        except FileNotFoundError:
            continue
    else:
        return []
    beans: list[str] = []
    for line in out.stdout.strip().splitlines():
        if not line:
            continue
        stem = Path(line).stem
        bean = processor_bean_from_java_name(stem)
        if bean:
            beans.append(bean)
    return sorted(set(beans))


def _orchestration_processors_in_file(path: Path) -> list[str]:
    """Return processor bean names only (not Request names)."""
    if path.suffix != ".xml" or "orchestration" not in str(path):
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    beans: list[str] = []
    for m in re.finditer(r'<Processor\s+bean="([^"]+)"', text):
        beans.append(m.group(1))
    return sorted(set(beans))


def _orchestration_request_names_in_file(path: Path) -> list[str]:
    """Return Request name= apiNames from orchestration XML."""
    if path.suffix != ".xml" or "orchestration" not in str(path):
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    names: list[str] = []
    for m in re.finditer(r'<Request\s+name="([^"]+)"', text):
        names.append(m.group(1))
    return sorted(set(names))


def _domain_hint_api(path: str) -> str | None:
    mapped = api_from_path(path)
    if mapped:
        return mapped
    s = path.replace("\\", "/").lower()
    # Workspace harness/docs are not service code — never invent apiNames from
    # path needles (scripts/dpic matched "/dpi" → overview API).
    if s.startswith(("scripts/", ".cursor/", "cursor-bundle/", "system_brain/", "docs/")):
        return None
    for needle, api in DOMAIN_PRIMARY_API:
        if needle in s:
            return api
    return None


def _batch_api_for_stem(stem: str, path: str) -> str | None:
    """Resolve ItemWriter/BatchService stem → known apiName (map + registry), else domain hint."""
    mapped = api_from_class_stem(stem)
    if mapped:
        return mapped
    return _domain_hint_api(path)


def _rank_apis(apis: list[str]) -> list[str]:
    order = {a: i for i, a in enumerate(API_PRIORITY)}
    return sorted(apis, key=lambda a: (order.get(a, 999), a))


def resolve_apis_for_path(path: str) -> list[str]:
    """KG + grep: map one changed path to affected request apiName(s)."""
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / path
    s = str(p)
    apis: set[str] = set()

    # Repo-relative for grep (dirs only — not novopay-service.sh / *.md)
    repo = None
    for part in p.parts:
        if (part.startswith("novopay-") or part.startswith("trustt-")) and "." not in part:
            repo = part
            break
    repo_dir = _repo_dir(repo) if repo else None

    stem = p.stem
    conn = _kg_conn()

    # *Processor.java
    bean = processor_bean_from_java_name(stem)
    if bean:
        apis.update(requests_for_processor_bean(bean, conn))

    # *BatchService / *ItemWriter / *Consumer — map to known apiName; never invent class stem
    batch_resolved = False
    for suffix in ("BatchService", "ItemWriter", "ConfigService", "Consumer"):
        if stem.endswith(suffix):
            mapped = _batch_api_for_stem(stem, s)
            if mapped:
                apis.add(mapped)
                apis.update(requests_for_batch_job(mapped, conn))
                batch_resolved = True
            break

    # Util / service / bank-call — grep → processors → requests
    # Skip when batch stem already mapped (grep finds sibling processors with KG repo/api labels)
    if repo_dir and stem not in (bean,) and not batch_resolved:
        for ref_bean in _grep_java_referencing(stem, repo_dir):
            apis.update(requests_for_processor_bean(ref_bean, conn))

    # Orchestration XML — Request names are apiNames; processor beans → requests via KG
    for req in _orchestration_request_names_in_file(p):
        apis.add(req)
    for b in _orchestration_processors_in_file(p):
        apis.update(requests_for_processor_bean(b, conn))

    # MessageBroker / consumer config — only map when domain path is known.
    # NEVER default to disburseLoan (that hung KB/SMS pushes on disburse-quick E2E).
    if "MessageBroker" in stem or p.name == "MessageBroker.xml":
        hint = _domain_hint_api(s)
        if hint:
            apis.add(hint)
        elif "trustt-platform-notifications" in s.replace("\\", "/") or "novopay-platform-notifications" in s.replace(
            "\\", "/"
        ):
            # SMS consumer throughput pairs with due-notification producer path
            apis.add("loanInstallmentDueNotificationJob")
        # accounting MessageBroker without domain hint: leave unresolved (no invented api)

    if conn:
        conn.close()

    if not apis:
        hint = _domain_hint_api(s)
        if hint:
            apis.add(hint)

    cleaned = [_normalize_api_name(a) for a in apis if a]
    cleaned = [a for a in cleaned if a]
    return _rank_apis(list(dict.fromkeys(cleaned)))


def resolve_apis_for_paths(paths: list[str]) -> list[str]:
    out: list[str] = []
    for p in paths:
        for api in resolve_apis_for_path(p):
            if api not in out:
                out.append(api)
    return _rank_apis(out)
