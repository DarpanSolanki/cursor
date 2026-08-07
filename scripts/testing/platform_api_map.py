#!/usr/bin/env python3
"""Map every platform API as it actually is, across every service repo, and store it.

`transaction_map.py` did this for 24 accounting loan transactions and proved the shape is
right. The platform has ~1875 requests across 15 repos, and the same six artefacts own the
same six facts in every one of them, so the only thing that was accounting-specific was the
hardcoded repo name.

Each fact is read from the artefact that owns it, never inferred:

  request / response shape   the JTF templates the service ships
  mandatory + allowed values orchestration `<Validators>`
  processor order            orchestration `<Processors>`, `<Control>` branches marked
  cross-service calls        KG `calls` edges, repo-qualified
  error codes                KG `throws` edges from the processors that run
  tables read / written      KG CRUD edges, the same 1-hop join `kg crud` prints

Speed matters because a map nobody can regenerate goes stale and then lies. Two decisions
keep a full sweep near a minute rather than an hour: repos are parsed in parallel (the work
is per-repo and shares nothing), and every KG fact for all 1875 requests comes from four
bulk queries against `kg.db` instead of 1875 `kg` subprocesses.

    platform_api_map.py                 map every repo, write the artefacts
    platform_api_map.py --repo NAME     one repo
    platform_api_map.py --api NAME      one API, full detail
    platform_api_map.py --summary       coverage of the map itself, per repo
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import pathlib
import re
import sqlite3
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
FLOW = ROOT / "cursor-bundle" / "flow-test"
OUT = FLOW / "platform_api_map.jsonl"
DOC = ROOT / ".cursor" / "platform-api-map.md"
KGDB = ROOT / "cursor-bundle" / "kg" / "data" / "kg.db"

sys.path.insert(0, str(ROOT / "cursor-bundle" / "kg" / "bin"))

_REQUEST = re.compile(r'<Request\s+name="([^"]+)"', re.I)
_PROCESSOR = re.compile(r'<Processor[^>]*\bbean="([^"]+)"', re.I)
_VALIDATOR = re.compile(r'<Validator\s+bean="([^"]+)"(.*?)</Validator>', re.I | re.S)
_IPARAM = re.compile(r'<IParam\b([^>]*)/?>', re.I)
_ATTR = re.compile(r'(\w+)="([^"]*)"')
_CONTROL = re.compile(r'<Control[^>]*pattern="([^"]*)"[^>]*value="([^"]*)"', re.I)
_ERRCODE = re.compile(r'errorCode="([A-Za-z]{2,8}-\d+|\d+)"')

_META = {"class", "type"}
CONTROL_FIELDS = ("function_code", "function_sub_code", "run_mode")

_MUTATES = re.compile(r"^(create|update|delete|approve|submit|cancel|assign|post|process|"
                      r"upload|generate|reverse|waive|disburse|repay|close|initiate|link|"
                      r"save|add|remove|modify|transfer|settle|book|allocate)", re.I)


def service_repos() -> list[pathlib.Path]:
    seen: dict[str, pathlib.Path] = {}
    for pattern in ("trustt-*", "novopay-*"):
        for path in sorted(ROOT.glob(pattern)):
            if (path / ".git").is_dir():
                seen.setdefault(path.name, path)
    return list(seen.values())


def request_sites(repo: pathlib.Path) -> dict[str, tuple[str, int, str]]:
    from _contract_scan import orchestration_xmls
    sites: dict[str, tuple[str, int, str]] = {}
    for raw in orchestration_xmls(str(repo)):
        path = pathlib.Path(raw)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        matches = list(_REQUEST.finditer(text))
        for i, m in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            line = text.count("\n", 0, m.start()) + 1
            rel = str(path.relative_to(ROOT)) if path.is_absolute() else raw
            sites.setdefault(m.group(1), (rel, line, text[m.start():end]))
    return sites


def template_index(repo: pathlib.Path, kind: str) -> dict[str, pathlib.Path]:
    root = repo / "deploy" / "application" / "templates" / kind
    suffix = f"_{kind}Template.json"
    if not root.is_dir():
        return {}
    return {p.name[: -len(suffix)]: p for p in root.rglob(f"*{suffix}")
            if p.name.endswith(suffix)}


def walk(node: dict, prefix: str = "") -> list[str]:
    """Flatten a JTF template into the JSON paths the message really has.

    A container repeats its own name to hold the element shape, so emitting it literally
    yields `account_overview_list.account_overview_list.…`, which matches nothing. The
    repeated key is the shape, not a path segment; an `ARR` becomes `[0]`.
    """
    out: list[str] = []
    for name, child in node.items():
        if name in _META or not isinstance(child, dict):
            continue
        segment = f"{name}[0]" if str(child.get("type")).upper() == "ARR" else name
        path = f"{prefix}.{segment}" if prefix else segment
        inner = child.get(name) if isinstance(child.get(name), dict) else child
        grand = {k: v for k, v in inner.items() if k not in _META and isinstance(v, dict)}
        if grand:
            out.extend(walk(inner, path))
        else:
            out.append(path)
    return out


def contract_from_template(path: pathlib.Path | None, api: str) -> list[str]:
    if path is None:
        return []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, RecursionError):
        return []
    body = doc.get(api)
    try:
        return walk(body if isinstance(body, dict) else doc)
    except RecursionError:
        return []


def validator_contract(block: str) -> tuple[list[str], dict[str, str]]:
    required: list[str] = []
    allowed: dict[str, str] = {}
    for bean, body in _VALIDATOR.findall(block):
        for raw in _IPARAM.findall(body):
            attrs = dict(_ATTR.findall(raw))
            field = attrs.get("fieldName")
            if not field:
                continue
            if bean == "mandatoryFieldValidator":
                required.append(field)
            elif bean == "patternFieldValidator" and attrs.get("pattern"):
                allowed[field] = attrs["pattern"].split("|")[0]
    return sorted(dict.fromkeys(required)), allowed


def parse_repo(name: str) -> list[dict]:
    repo = ROOT / name
    sites = request_sites(repo)
    req_idx = template_index(repo, "request")
    resp_idx = template_index(repo, "response")
    rows = []
    for api in sorted(set(sites) | set(req_idx)):
        site = sites.get(api)
        block = site[2] if site else ""
        required, allowed = validator_contract(block) if block else ([], {})
        rows.append({
            "api": api,
            "repo": name,
            "orchestration": f"{site[0]}:{site[1]}" if site else None,
            "request_template": str(req_idx[api].relative_to(ROOT)) if api in req_idx else None,
            "response_template": str(resp_idx[api].relative_to(ROOT)) if api in resp_idx else None,
            "headers": {k: allowed[k] for k in CONTROL_FIELDS if k in allowed},
            "mandatory_fields": required,
            "allowed_values": {k: v for k, v in allowed.items() if k not in CONTROL_FIELDS},
            "request_fields": contract_from_template(req_idx.get(api), api),
            "response_fields": contract_from_template(resp_idx.get(api), api),
            "processors": _PROCESSOR.findall(block) if block else [],
            "control_branches": [f"{p} = {v}" for p, v in _CONTROL.findall(block)][:12],
            "orch_error_codes": sorted(set(_ERRCODE.findall(block))),
            "mutating": bool(_MUTATES.match(api)),
        })
    return rows


def kg_facts() -> dict[str, dict]:
    """Every KG fact for every request, in four queries rather than 1875 subprocesses."""
    if not KGDB.is_file():
        return {}
    con = sqlite3.connect(f"file:{KGDB}?mode=ro", uri=True)
    facts: dict[str, dict] = {}

    def slot(rid: str) -> dict:
        return facts.setdefault(rid, {"tables_written": set(), "tables_read": set(),
                                      "error_codes": set(), "cross_service_apis": set(),
                                      "internal_apis": set()})

    crud = """SELECT e1.src_id, e2.rel, n.label FROM edges e1
              JOIN edges e2 ON e2.src_id = e1.dst_id
              JOIN nodes n ON n.id = e2.dst_id
              WHERE e1.rel='invokes' AND e2.rel IN ('reads','writes','deletes')
                AND n.kind='table'"""
    for rid, rel, table in con.execute(crud):
        s = slot(rid)
        (s["tables_read"] if rel == "reads" else s["tables_written"]).add(table)

    throws = """SELECT e1.src_id, n.label FROM edges e1
                JOIN edges e2 ON e2.src_id = e1.dst_id
                JOIN nodes n ON n.id = e2.dst_id
                WHERE e1.rel='invokes' AND e2.rel='throws' AND n.kind='error'"""
    for rid, code in con.execute(throws):
        slot(rid)["error_codes"].add(code)

    for rid, dst in con.execute(
            "SELECT src_id, dst_id FROM edges WHERE rel='calls' AND src_id LIKE 'request:%'"):
        s = slot(rid)
        src_repo = rid.split(":", 1)[1].split("/", 1)[0]
        if dst.startswith("request:"):
            target = dst.split(":", 1)[1]
            dst_repo, _, api = target.partition("/")
            (s["internal_apis"] if dst_repo == src_repo
             else s["cross_service_apis"]).add(api if dst_repo == src_repo else target)

    for rid, dst in con.execute(
            "SELECT src_id, dst_id FROM edges WHERE rel='calls_api' AND src_id LIKE 'request:%'"):
        slot(rid)["internal_apis"].add(dst.split(":", 1)[1])

    con.close()
    return {k: {f: sorted(v) for f, v in val.items()} for k, val in facts.items()}


def inherited_errors() -> dict[str, list[str]]:
    """Codes a flow can return because something it calls throws them.

    `134207` is thrown in `ExecuteTransactionRulesProcessor` under `postTransaction`, and
    `accounting-134207-placeholder-iad.md` documents it arriving on `disburseLoan` — which
    calls `postTransaction`. A one-hop index says disburseLoan cannot raise it, and that is
    wrong in the exact case the runbook exists for.
    """
    if not KGDB.is_file():
        return {}
    con = sqlite3.connect(f"file:{KGDB}?mode=ro", uri=True)
    by_name: dict[str, set] = {}
    for rid, in con.execute("SELECT id FROM nodes WHERE kind='request'"):
        by_name.setdefault(rid.split("/")[-1], set()).add(rid)
    graph: dict[str, set] = {}
    for src, dst in con.execute(
            "SELECT src_id, dst_id FROM edges WHERE rel='calls' "
            "AND src_id LIKE 'request:%' AND dst_id LIKE 'request:%'"):
        graph.setdefault(src, set()).add(dst)
    for src, dst in con.execute(
            "SELECT src_id, dst_id FROM edges WHERE rel='calls_api' AND src_id LIKE 'request:%'"):
        graph.setdefault(src, set()).update(by_name.get(dst.split(":", 1)[1], ()))
    direct: dict[str, set] = {}
    for rid, code in con.execute(
            """SELECT e1.src_id, n.label FROM edges e1
               JOIN edges e2 ON e2.src_id = e1.dst_id
               JOIN nodes n ON n.id = e2.dst_id
               WHERE e1.rel='invokes' AND e2.rel='throws' AND n.kind='error'
                 AND e1.src_id LIKE 'request:%'"""):
        direct.setdefault(rid, set()).add(code)
    con.close()

    out: dict[str, set] = {}
    for start in graph:
        seen, queue, codes = {start}, [start], set()
        while queue:
            node = queue.pop()
            for nxt in graph.get(node, ()):
                if nxt not in seen:
                    seen.add(nxt)
                    codes |= direct.get(nxt, set())
                    queue.append(nxt)
        if codes:
            out[start.split(":", 1)[1]] = codes - direct.get(start, set())
    return {k: sorted(v) for k, v in out.items() if v}


def callers() -> dict[str, list[str]]:
    """Who calls each API — the reverse of `cross_service_apis`.

    `api-contract-safety.md` opens with "find all callers", and until now that meant a
    repo-wide grep for the API name across fifteen repos. The KG already holds the edge; it
    was only ever stored in the forward direction.
    """
    if not KGDB.is_file():
        return {}
    con = sqlite3.connect(f"file:{KGDB}?mode=ro", uri=True)
    rev: dict[str, set] = {}
    for src, dst in con.execute(
            "SELECT src_id, dst_id FROM edges WHERE rel='calls' "
            "AND src_id LIKE 'request:%' AND dst_id LIKE 'request:%'"):
        rev.setdefault(dst.split("/")[-1], set()).add(src.split(":", 1)[1])
    for src, dst in con.execute(
            "SELECT src_id, dst_id FROM edges WHERE rel='calls_api' AND src_id LIKE 'request:%'"):
        rev.setdefault(dst.split(":", 1)[1], set()).add(src.split(":", 1)[1])
    con.close()
    return {k: sorted(v) for k, v in rev.items()}


def ui_reachable() -> set[str]:
    """APIs the webapp calls. What is not here is backend-only, whoever else may call it."""
    if not KGDB.is_file():
        return set()
    con = sqlite3.connect(f"file:{KGDB}?mode=ro", uri=True)
    rows = con.execute("SELECT dst_id FROM edges WHERE rel='ui_calls'").fetchall()
    con.close()
    return {r[0].split("/")[-1].split(":", 1)[-1] for r in rows}


EMPTY = {"tables_written": [], "tables_read": [], "error_codes": [],
         "cross_service_apis": [], "internal_apis": []}

REGISTRY_CACHE = FLOW / "api_registry.json"
RECONCILE = FLOW / "api_registry_reconciliation.json"

SERVICE_REPO = {
    "ACCOUNTING": "trustt-platform-accounting", "ACTOR": "trustt-platform-actor",
    "LOS": "trustt-platform-los", "PAYMENTS": "trustt-platform-payments",
    "TASK": "trustt-platform-task", "REPORTING": "trustt-platform-reporting",
    "MASTERDATA": "trustt-platform-masterdata-management",
    "AUTHORIZATION": "trustt-platform-authorization",
    "NOTIFICATIONS": "trustt-platform-notifications", "BRE": "trustt-platform-bre",
    "BATCH": "trustt-platform-batch", "APPROVAL": "trustt-platform-approval",
    "DMS": "trustt-platform-dms", "AUDIT": "trustt-platform-audit",
    "API-GATEWAY": "trustt-platform-api-gateway",
}

_REGROW = re.compile(r"^([A-Z0-9-]+)\|(\w+)\|([tf])\|(\d*)$")


def api_registry() -> dict[str, dict]:
    """`platform_master.api_master` — which service the gateway routes each API to.

    This is the runtime authority, and it disagrees with the code in both directions, which
    is the interesting part: APIs registered with no implementation in this workspace, and
    APIs served by a repo that the registry never learned about.

    Read from the local DB when it is up, then cached, so the map still regenerates when it
    is not. Read-only, localhost only.
    """
    import subprocess
    sql = ("select s.name||'|'||a.name||'|'||case when a.audit_req_resp then 't' else 'f' end"
           "||'|'||coalesce(a.api_rate_limit,0) "
           "from platform_master.api_master a "
           "join platform_master.service_master s on s.id = a.service_master_id")
    rows: dict[str, dict] = {}
    try:
        proc = subprocess.run(["bash", str(ROOT / "scripts/db-local.sh"), "--sql", sql],
                              cwd=str(ROOT), capture_output=True, text=True, timeout=60)
        for line in proc.stdout.splitlines():
            m = _REGROW.match(line.strip())
            if m:
                service, api, audit, limit = m.groups()
                rows[api] = {"registry_service": service, "audited": audit == "t",
                             "rate_limit": int(limit or 0)}
    except (OSError, subprocess.TimeoutExpired):
        rows = {}
    if rows:
        REGISTRY_CACHE.parent.mkdir(parents=True, exist_ok=True)
        REGISTRY_CACHE.write_text(json.dumps(rows, indent=1, sort_keys=True), encoding="utf-8")
        return rows
    if REGISTRY_CACHE.is_file():
        return json.loads(REGISTRY_CACHE.read_text(encoding="utf-8"))
    return {}


def reconcile(rows: list[dict], registry: dict[str, dict]) -> dict:
    """Where the registry and the code disagree — in both directions."""
    served = {r["api"] for r in rows}
    by_api: dict[str, list[str]] = {}
    for r in rows:
        by_api.setdefault(r["api"], []).append(r["repo"])
    unimplemented: dict[str, list[str]] = {}
    misrouted = []
    for api, meta in registry.items():
        expected = SERVICE_REPO.get(meta["registry_service"])
        if api not in served:
            unimplemented.setdefault(meta["registry_service"], []).append(api)
        elif expected and expected not in by_api[api]:
            misrouted.append({"api": api, "registry_service": meta["registry_service"],
                              "served_by": by_api[api]})
    return {
        "registered": len(registry),
        "served": len(served),
        "registered_and_served": len(served & set(registry)),
        "registered_not_served": {k: sorted(v) for k, v in sorted(unimplemented.items())},
        "served_not_registered": sorted(served - set(registry)),
        "served_by_unexpected_repo": sorted(misrouted, key=lambda m: m["api"]),
    }


def build(repos: list[str] | None = None, quiet: bool = False) -> list[dict]:
    names = repos or [p.name for p in service_repos()]
    rows: list[dict] = []
    started = time.time()
    workers = min(len(names), (os.cpu_count() or 4))
    with cf.ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(parse_repo, n): n for n in names}
        for done in cf.as_completed(futures):
            name = futures[done]
            try:
                got = done.result()
            except Exception as exc:
                if not quiet:
                    print(f"  !! {name}: {type(exc).__name__}: {exc}", flush=True)
                continue
            rows.extend(got)
            if not quiet and got:
                print(f"  {len(got):5} {name}  ({time.time()-started:.1f}s)", flush=True)

    facts = kg_facts()
    registry = api_registry()
    ui = ui_reachable()
    called_by = callers()
    via_calls = inherited_errors()
    for row in rows:
        row["ui_reachable"] = row["api"] in ui
        row["called_by"] = called_by.get(row["api"], [])
        row["error_codes_via_calls"] = via_calls.get(f"{row['repo']}/{row['api']}", [])
        rid = f"request:{row['repo']}/{row['api']}"
        got = facts.get(rid) or EMPTY
        row.update(got)
        row["error_codes"] = sorted(set(got["error_codes"]) | set(row["orch_error_codes"]))
        row.pop("orch_error_codes")
        meta = registry.get(row["api"])
        row["registered"] = meta is not None
        row["registry_service"] = meta["registry_service"] if meta else None
        row["audited"] = meta["audited"] if meta else None
    rows.sort(key=lambda r: (r["repo"], r["api"]))
    return rows


def summarise(rows: list[dict]) -> str:
    by_repo: dict[str, list[dict]] = {}
    for r in rows:
        by_repo.setdefault(r["repo"], []).append(r)
    fields = [("orchestration", lambda r: r["orchestration"]),
              ("request", lambda r: r["request_template"]),
              ("response", lambda r: r["response_template"]),
              ("procs", lambda r: r["processors"]),
              ("tables", lambda r: r["tables_written"] or r["tables_read"]),
              ("errors", lambda r: r["error_codes"]),
              ("calls", lambda r: r["cross_service_apis"] or r["internal_apis"]),
              ("routed", lambda r: r.get("registered")),
              ("ui", lambda r: r.get("ui_reachable")),
              ("callers", lambda r: r.get("called_by"))]
    head = f"{'repo':40} {'apis':>5} " + " ".join(f"{n:>9}" for n, _ in fields)
    out = [head, "-" * len(head)]
    for repo in sorted(by_repo):
        rs = by_repo[repo]
        cells = " ".join(f"{sum(1 for r in rs if fn(r)):>9}" for _, fn in fields)
        out.append(f"{repo:40} {len(rs):>5} {cells}")
    cells = " ".join(f"{sum(1 for r in rows if fn(r)):>9}" for _, fn in fields)
    out.append("-" * len(head))
    out.append(f"{'TOTAL':40} {len(rows):>5} {cells}")
    return "\n".join(out)


def markdown(rows: list[dict]) -> str:
    by_repo: dict[str, list[dict]] = {}
    for r in rows:
        by_repo.setdefault(r["repo"], []).append(r)
    out = ["# Platform API map (generated — do not hand-edit)",
           "",
           "`python3 scripts/testing/platform_api_map.py` regenerates this from every service",
           "repo's orchestration, its shipped JTF templates and the KG. These APIs run in",
           "production; this records what they are, not what they should be.",
           "",
           "**Control fields are headers**, never body: `function_code`, `function_sub_code`,",
           "`run_mode`. Sent in the body the gateway answers `11008 Invalid run_mode`.",
           "",
           "Per-API detail — request/response field paths, processor order, control branches —",
           "is in `cursor-bundle/flow-test/platform_api_map.jsonl`, one JSON object per API.",
           "",
           "## Reach", "", "```", summarise(rows), "```", "",
           "`callers` answers the first line of the contract-safety checklist — *find all",
           "callers* — without a fifteen-repo grep. The most-depended-on APIs, by number of",
           "distinct calling flows:", "",
           "| API | served by | called by |",
           "|-----|-----------|----------:|"]
    hot = sorted(rows, key=lambda r: -len(r.get("called_by") or []))[:15]
    out += [f"| `{r['api']}` | {r['repo'].replace('trustt-platform-','')} | "
            f"{len(r['called_by'])} |" for r in hot if r.get("called_by")]
    out += ["",
            "Changing one of these is a platform event, not a service change. The callers are",
            "listed per API in the jsonl, repo-qualified.", "",
           "`routed` = the API is in `platform_master.api_master`, the registry the gateway",
           "routes on. The two disagree in both directions and the disagreement is recorded in",
           "`cursor-bundle/flow-test/api_registry_reconciliation.json`:",
           "",
           "- **registered, not served here** — mostly other product lines (AEPS, BillPay,",
           "  bank-in-a-box). They exist only in the `api_master` seed migration, in no repo's",
           "  orchestration. Absence here is not a defect; it means the code lives elsewhere.",
           "- **served, not registered** — reachable in orchestration but not routed by the",
           "  gateway. Internal-only flows and batch entry points, called service-to-service.",
           ""]
    for repo in sorted(by_repo):
        rs = by_repo[repo]
        writes = sorted({t for r in rs for t in r["tables_written"]})
        crossing = [r for r in rs if r["cross_service_apis"]]
        out += [f"## {repo}", "",
                f"- **APIs:** {len(rs)} ({sum(1 for r in rs if r['mutating'])} mutating, "
                f"{sum(1 for r in rs if not r['mutating'])} read/inquiry)",
                f"- **Tables written:** {len(writes)}"
                + (f" — {', '.join('`'+t+'`' for t in writes[:14])}"
                   + (f" (+{len(writes)-14} more)" if len(writes) > 14 else "")
                   if writes else ""),
                f"- **APIs calling another service:** {len(crossing)}"]
        targets = sorted({t.split("/")[0] for r in rs for t in r["cross_service_apis"]})
        if targets:
            out.append(f"- **Depends on:** {', '.join('`'+t+'`' for t in targets)}")
        busiest = sorted(rs, key=lambda r: -len(r["processors"]))[:5]
        if busiest and busiest[0]["processors"]:
            out.append("- **Largest flows:** " + ", ".join(
                f"`{r['api']}` ({len(r['processors'])})" for r in busiest if r["processors"]))
        out.append("")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo")
    ap.add_argument("--api")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.api:
        rows = [r for r in build(quiet=True) if r["api"] == args.api]
        print(json.dumps(rows, indent=1))
        return 0 if rows else 1

    print("mapping platform APIs (parallel by repo):", flush=True)
    rows = build([args.repo] if args.repo else None)

    if args.json:
        print(json.dumps(rows, indent=1))
        return 0

    print()
    print(summarise(rows))

    if args.summary or args.repo:
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fh:
        fh.write("# Platform API map — orchestration + JTF templates + KG. Generated.\n")
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    DOC.write_text(markdown(rows), encoding="utf-8")

    rec = reconcile(rows, api_registry())
    RECONCILE.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    unimpl = sum(len(v) for v in rec["registered_not_served"].values())
    print(f"\nregistry: {rec['registered']} routed · {rec['registered_and_served']} of them served here")
    print(f"  {unimpl:5} registered with no implementation in this workspace")
    print(f"  {len(rec['served_not_registered']):5} served but not routed by the gateway")
    print(f"  {len(rec['served_by_unexpected_repo']):5} served by a repo the registry does not name")
    print(f"\n  → {OUT.relative_to(ROOT)}\n  → {DOC.relative_to(ROOT)}\n  → {RECONCILE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
