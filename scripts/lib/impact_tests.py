#!/usr/bin/env python3
"""Dynamic impact-tests resolver — git diff → KG blast radius → registry cases + WHY.

Source of truth: live KG (writes siblings, topic consumers, processor→request).
Static seed/override: scripts/lib/change_test_map.json (does not replace KG).
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))

KG_DB = ROOT / "cursor-bundle/kg/data/kg.db"
REGISTRY = ROOT / "scripts/testing/registry.json"
PROPOSALS = ROOT / "scripts/testing/registry-proposals.json"
PENDING = ROOT / ".cursor/.pending-ship-work.json"
RAN_FILE = ROOT / ".cursor/.impact-tests-ran.json"
WAIVER_LOG = ROOT / ".cursor/.impact-tests-waivers.log"
FINDINGS = ROOT / "cursor-bundle/memory/self-upgrade-findings.json"
BACKLOG = ROOT / "scripts/workspace-backlog.json"

try:
    from change_test_map import api_from_class_stem, api_from_path  # noqa: E402
except ImportError:  # pragma: no cover
    api_from_class_stem = None  # type: ignore
    api_from_path = None  # type: ignore


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _norm_api(req_id: str) -> str:
    """request:repo/apiName or bare api → apiName."""
    s = req_id
    if s.startswith("request:"):
        s = s.split(":", 1)[1]
    if "/" in s:
        s = s.rsplit("/", 1)[-1]
    return s


def _to_rel(path: str) -> str:
    p = Path(path)
    if p.is_absolute():
        try:
            return str(p.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
        except ValueError:
            return str(p).replace("\\", "/")
    return path.replace("\\", "/").lstrip("./")


def collect_changed_paths(
    *,
    range_spec: str | None = None,
    from_pending: bool = True,
    paths: list[str] | None = None,
) -> list[str]:
    """Default: pending-ship files ∪ dirty git trees. --range uses git diff."""
    out: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        rel = _to_rel(raw)
        if not rel or rel in seen:
            return
        if rel.startswith("scripts/scratch/") or "/__pycache__/" in rel:
            return
        seen.add(rel)
        out.append(rel)

    if paths:
        for p in paths:
            add(p)
        return out

    if range_spec:
        # workspace root + each service repo
        for repo in [ROOT, *sorted(ROOT.glob("trustt-*")), *sorted(ROOT.glob("novopay-*"))]:
            if not (repo / ".git").is_dir():
                continue
            r = subprocess.run(
                ["git", "-C", str(repo), "diff", "--name-only", range_spec],
                capture_output=True,
                text=True,
                check=False,
            )
            prefix = "" if repo == ROOT else f"{repo.name}/"
            for line in r.stdout.splitlines():
                if line.strip():
                    add(prefix + line.strip())
        return out

    if from_pending and PENDING.is_file():
        try:
            pend = json.loads(PENDING.read_text(encoding="utf-8"))
            for f in pend.get("files") or []:
                add(f)
        except Exception:
            pass

    # Always union dirty trees (human edits regardless of author)
    for repo in [ROOT, *sorted(ROOT.glob("trustt-*")), *sorted(ROOT.glob("novopay-*"))]:
        if not (repo / ".git").is_dir():
            continue
        for args in (
            ["git", "-C", str(repo), "diff", "--name-only", "HEAD"],
            ["git", "-C", str(repo), "diff", "--name-only", "--cached"],
            ["git", "-C", str(repo), "ls-files", "--others", "--exclude-standard"],
        ):
            r = subprocess.run(args, capture_output=True, text=True, check=False)
            prefix = "" if repo == ROOT else f"{repo.name}/"
            for line in r.stdout.splitlines():
                if line.strip():
                    add(prefix + line.strip())
        # unpushed commits on tracking branch
        r = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "@{upstream}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if r.returncode == 0 and r.stdout.strip():
            up = r.stdout.strip()
            d = subprocess.run(
                ["git", "-C", str(repo), "diff", "--name-only", f"{up}...HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
            prefix = "" if repo == ROOT else f"{repo.name}/"
            for line in d.stdout.splitlines():
                if line.strip():
                    add(prefix + line.strip())
    return out


def _kg() -> sqlite3.Connection | None:
    if not KG_DB.is_file():
        return None
    try:
        return sqlite3.connect(f"file:{KG_DB}?mode=ro", uri=True)
    except sqlite3.Error:
        return None


def path_to_nodes(path: str, conn: sqlite3.Connection | None) -> list[dict]:
    """Map a changed file to KG node ids + seed apis."""
    rel = _to_rel(path)
    s = rel.replace("\\", "/")
    low = s.lower()
    nodes: list[dict] = []
    stem = Path(s).stem

    def add(nid: str, kind: str, how: str) -> None:
        nodes.append({"id": nid, "kind": kind, "via": how, "file": rel})

    # Processor.java
    if stem.endswith("Processor") and s.endswith(".java"):
        bean = stem[0].lower() + stem[1:]
        add(f"processor:{bean}", "processor", "class_stem")

    # Batch / writer — seed override then class map
    if any(stem.endswith(x) for x in ("BatchService", "ItemWriter", "ConfigService", "Writer")):
        api = None
        if api_from_class_stem:
            api = api_from_class_stem(stem)
        if not api and api_from_path:
            api = api_from_path(s)
        if api:
            add(f"request:{api}", "request", "change_test_map_seed")
            # Prefer repo-scoped request if present in KG
            if conn:
                row = conn.execute(
                    "SELECT id FROM nodes WHERE id LIKE ? OR (kind='request' AND label=?)",
                    (f"%/{api}", api),
                ).fetchone()
                if row:
                    nodes[-1]["id"] = row[0]

    # Orchestration XML — Request names
    if s.endswith(".xml") and "orchestration" in low:
        try:
            text = (ROOT / s).read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r'<Request\s+name="([^"]+)"', text):
                add(f"request:{m.group(1)}", "request", "orch_xml")
            for m in re.finditer(r'<Processor\s+bean="([^"]+)"', text):
                add(f"processor:{m.group(1)}", "processor", "orch_xml")
        except OSError:
            pass

    # MessageBroker / kafka — topic hints from filename/path
    if "messagebroker" in low or "kafka" in low:
        if conn:
            for row in conn.execute(
                "SELECT id FROM nodes WHERE kind='topic' AND ("
                "id LIKE '%disburse%' OR id LIKE '%notification%' OR id LIKE '%collection%')"
            ).fetchall()[:8]:
                add(row[0], "topic", "messagebroker_path")

    # Seed path→api override
    if api_from_path:
        hint = api_from_path(s)
        if hint and not any(n["id"].endswith(hint) or n["id"] == f"request:{hint}" for n in nodes):
            add(f"request:{hint}", "request", "change_test_map_path")

    return nodes


def blast_flows(nodes: list[dict], conn: sqlite3.Connection | None) -> list[dict]:
    """Expand nodes → flows via invokes + shared WRITE tables + topic consumers."""
    flows: dict[str, dict] = {}

    def add_flow(req_id: str, why: str, tables: list[str] | None = None) -> None:
        api = _norm_api(req_id)
        if not api:
            return
        key = api
        if key not in flows:
            flows[key] = {
                "api": api,
                "request_id": req_id if req_id.startswith("request:") else f"request:{api}",
                "why": [],
                "tables": [],
            }
        if why not in flows[key]["why"]:
            flows[key]["why"].append(why)
        for t in tables or []:
            if t not in flows[key]["tables"]:
                flows[key]["tables"].append(t)

    if not conn:
        for n in nodes:
            if n["kind"] == "request":
                add_flow(n["id"], f"{n['file']} → {n['id']} ({n['via']})")
        return list(flows.values())

    for n in nodes:
        nid = n["id"]
        file_why = f"{n['file']} → {nid} ({n['via']})"

        if n["kind"] == "request":
            add_flow(nid, file_why)
            # also expand write-set siblings
            api = _norm_api(nid)
            # resolve full request id
            row = conn.execute(
                "SELECT id FROM nodes WHERE kind='request' AND (id=? OR id LIKE ? OR label=?)",
                (nid if nid.startswith("request:") else f"request:{api}", f"%/{api}", api),
            ).fetchone()
            rid = row[0] if row else (nid if nid.startswith("request:") else f"request:{api}")
            # processors invoked
            procs = [
                r[0]
                for r in conn.execute(
                    "SELECT dst_id FROM edges WHERE src_id=? AND rel='invokes'", (rid,)
                ).fetchall()
            ]
            for proc in procs:
                _expand_proc_writes(conn, proc, flows, file_why)

        elif n["kind"] == "processor":
            add_flow_from_proc = conn.execute(
                "SELECT src_id FROM edges WHERE dst_id=? AND rel='invokes'", (nid,)
            ).fetchall()
            for (rid,) in add_flow_from_proc:
                add_flow(rid, f"{file_why} → invokes → {_norm_api(rid)}")
            _expand_proc_writes(conn, nid, flows, file_why)

        elif n["kind"] == "topic":
            consumers = conn.execute(
                "SELECT src_id FROM edges WHERE dst_id=? AND rel='consumes'", (nid,)
            ).fetchall()
            for (svc,) in consumers:
                add_flow(
                    f"topic-consumer:{svc}",
                    f"{file_why} → consumes → {svc}",
                )
            # Also find requests linked to topic via emits if any
            emitters = conn.execute(
                "SELECT src_id FROM edges WHERE dst_id=? AND rel='emits'", (nid,)
            ).fetchall()
            for (src,) in emitters:
                if src.startswith("request:"):
                    add_flow(src, f"{file_why} ← emits ← {_norm_api(src)}")

    return list(flows.values())


def _expand_proc_writes(
    conn: sqlite3.Connection,
    proc_id: str,
    flows: dict,
    base_why: str,
) -> None:
    tables = [
        r[0]
        for r in conn.execute(
            "SELECT dst_id FROM edges WHERE src_id=? AND rel='writes'", (proc_id,)
        ).fetchall()
    ]
    for tab in tables:
        # sibling processors that write same table → their requesting flows
        sib_procs = [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT src_id FROM edges WHERE dst_id=? AND rel='writes'", (tab,)
            ).fetchall()
        ]
        for sp in sib_procs:
            reqs = conn.execute(
                "SELECT DISTINCT src_id FROM edges WHERE dst_id=? AND rel='invokes'", (sp,)
            ).fetchall()
            tname = tab.split(":", 1)[-1]
            for (rid,) in reqs:
                api = _norm_api(rid)
                why = (
                    f"{base_why} → writes {tname} → sibling {_norm_api(sp) if sp.startswith('processor') else sp} "
                    f"→ flow {api}"
                )
                if api not in flows:
                    flows[api] = {"api": api, "request_id": rid, "why": [], "tables": []}
                if why not in flows[api]["why"]:
                    flows[api]["why"].append(why)
                if tname not in flows[api]["tables"]:
                    flows[api]["tables"].append(tname)


def load_registry() -> dict:
    if not REGISTRY.is_file():
        return {}
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def cases_for_flows(flows: list[dict], reg: dict | None = None) -> tuple[list[dict], list[dict]]:
    """Map flows → registry cases; return (cases_with_why, missing_flow_stubs)."""
    reg = reg if reg is not None else load_registry()
    by_api: dict[str, list[str]] = {}
    for cid, meta in reg.items():
        if cid.startswith("_") or not isinstance(meta, dict):
            continue
        api = meta.get("api") or meta.get("batch_job_name")
        if api:
            by_api.setdefault(str(api), []).append(cid)

    cases: list[dict] = []
    missing: list[dict] = []
    seen: set[str] = set()
    for fl in flows:
        api = fl["api"]
        if api.startswith("topic-consumer:"):
            # service-level topic hit — try health/config cases later
            continue
        cids = by_api.get(api) or []
        if not cids:
            missing.append(
                {
                    "api": api,
                    "why": fl.get("why") or [],
                    "tables": fl.get("tables") or [],
                }
            )
            continue
        for cid in cids:
            if cid in seen:
                continue
            seen.add(cid)
            cases.append(
                {
                    "case": cid,
                    "api": api,
                    "why": (fl.get("why") or [f"api={api}"])[0],
                    "why_all": fl.get("why") or [],
                    "tables": fl.get("tables") or [],
                    "role": "changed_or_impacted",
                }
            )
    return cases, missing


def draft_missing_stubs(missing: list[dict]) -> list[dict]:
    """Auto-draft registry proposal stubs for impacted flows with no case."""
    if not missing:
        return []
    data = {"version": 1, "updated": _utc(), "proposals": []}
    if PROPOSALS.is_file():
        try:
            data = json.loads(PROPOSALS.read_text(encoding="utf-8"))
        except Exception:
            pass
    known = {p.get("id") for p in data.get("proposals") or []}
    drafted = []
    for m in missing:
        api = m["api"]
        pid = f"impact.stub.{api}"
        if pid in known:
            continue
        stub = {
            "id": pid,
            "status": "draft",
            "source": "impact_tests",
            "api": api,
            "title": f"Impact stub — no registry case for impacted flow {api}",
            "why": (m.get("why") or [""])[0],
            "tables": m.get("tables") or [],
            "created_at": _utc(),
            "note": "Auto-drafted by impact_tests; promote to registry.json with real asserts.",
        }
        data.setdefault("proposals", []).append(stub)
        drafted.append(stub)
        known.add(pid)
    if drafted:
        data["updated"] = _utc()
        PROPOSALS.parent.mkdir(parents=True, exist_ok=True)
        PROPOSALS.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return drafted


def acceptance_guards(flows: list[dict], cases: list[dict]) -> list[str]:
    """Money-domain acceptance case ids when touched tables look money."""
    money_tabs = {
        "transaction_master",
        "account_entry",
        "client_reference_number",
        "loan_account",
        "loan_account_due_details",
        "loan_transactions",
    }
    touched = {t for f in flows for t in (f.get("tables") or [])}
    if not touched & money_tabs:
        return []
    # Prefer cases already selected that have smoke_tier money; else note guard
    reg = load_registry()
    guards = []
    for c in cases:
        meta = reg.get(c["case"]) or {}
        if meta.get("smoke_tier") == "money" or meta.get("verify_mode"):
            guards.append(c["case"])
    return list(dict.fromkeys(guards))


def build_plan(
    *,
    range_spec: str | None = None,
    from_pending: bool = True,
    paths: list[str] | None = None,
    draft_stubs: bool = True,
) -> dict:
    changed = collect_changed_paths(
        range_spec=range_spec, from_pending=from_pending, paths=paths
    )
    conn = _kg()
    nodes: list[dict] = []
    for p in changed:
        nodes.extend(path_to_nodes(p, conn))
    # dedupe nodes
    seen_n: set[str] = set()
    uniq_nodes = []
    for n in nodes:
        key = f"{n['id']}|{n['file']}"
        if key in seen_n:
            continue
        seen_n.add(key)
        uniq_nodes.append(n)

    flows = blast_flows(uniq_nodes, conn)
    if conn:
        conn.close()

    cases, missing = cases_for_flows(flows)
    stubs = draft_missing_stubs(missing) if draft_stubs else []
    guards = acceptance_guards(flows, cases)

    # Order: money guards first, then alphabetical
    case_ids = [c["case"] for c in cases]
    ordered = list(dict.fromkeys(guards + case_ids))

    q_files = []
    try:
        from query_plan_gate import collect_query_touches

        q_files = [t["file"] for t in collect_query_touches(changed)]
    except Exception:
        q_files = []

    plan = {
        "built_at": _utc(),
        "source": "impact_tests_dynamic_kg",
        "seed_layer": "change_test_map.json (override only)",
        "files": changed,
        "nodes": uniq_nodes,
        "flows": flows,
        "cases": cases,
        "ordered_cases": ordered,
        "missing_flows": missing,
        "drafted_stubs": [s["id"] for s in stubs],
        "acceptance_guards": guards,
        "why_lines": [f"{c['case']}: {c['why']}" for c in cases],
        "query_touched": bool(q_files),
        "query_files": q_files,
    }
    if q_files:
        plan["why_lines"] = [
            f"query-plan-gate: {len(q_files)} query file(s) — run bash scripts/bin/query-plan-gate.sh"
        ] + list(plan["why_lines"])
    return plan


def mark_ran(plan: dict) -> None:
    RAN_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ran_at": _utc(),
        "files": plan.get("files") or [],
        "ordered_cases": plan.get("ordered_cases") or [],
        "fingerprint": _files_fp(plan.get("files") or []),
    }
    RAN_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _files_fp(files: list[str]) -> str:
    import hashlib

    h = hashlib.sha256()
    for f in sorted(files):
        h.update(f.encode())
        p = ROOT / f
        if p.is_file():
            st = p.stat()
            h.update(f"{st.st_size}:{int(st.st_mtime)}".encode())
    return h.hexdigest()[:16]


def impact_ran_satisfied(files: list[str] | None = None) -> tuple[bool, str]:
    """True if impact plan was run this session for current file set."""
    if not RAN_FILE.is_file():
        return False, "no .impact-tests-ran.json"
    try:
        data = json.loads(RAN_FILE.read_text(encoding="utf-8"))
    except Exception:
        return False, "corrupt impact-tests-ran"
    want = files
    if want is None and PENDING.is_file():
        try:
            want = json.loads(PENDING.read_text(encoding="utf-8")).get("files") or []
        except Exception:
            want = []
    want = want or []
    if not want:
        # no pending files — treat as N/A satisfied for workspace-only
        return True, "no pending ship files"
    fp = _files_fp(want)
    if data.get("fingerprint") != fp:
        return False, f"fingerprint mismatch (ran={data.get('fingerprint')} now={fp})"
    # freshness: same calendar day / 12h window
    ran_at = data.get("ran_at") or ""
    if ran_at < _utc()[:10]:  # crude: require same UTC day or newer stamp within session
        # allow if ran_at within last 12 hours
        try:
            from datetime import datetime, timezone, timedelta

            t = datetime.strptime(ran_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - t > timedelta(hours=12):
                return False, f"impact run stale ({ran_at})"
        except Exception:
            pass
    return True, f"ok ran_at={ran_at} cases={len(data.get('ordered_cases') or [])}"


def log_waiver(reason: str, actor: str = "agent") -> None:
    WAIVER_LOG.parent.mkdir(parents=True, exist_ok=True)
    with WAIVER_LOG.open("a", encoding="utf-8") as f:
        f.write(f"{_utc()} actor={actor} reason={reason}\n")


def format_banner(plan: dict) -> str:
    lines = [
        "===== IMPACT PLAN =====",
        f"built_at={plan.get('built_at')} source={plan.get('source')}",
        f"files={len(plan.get('files') or [])} flows={len(plan.get('flows') or [])} "
        f"cases={len(plan.get('ordered_cases') or [])} missing={len(plan.get('missing_flows') or [])}",
    ]
    # Prefer case WHY; always include at least one WHY per flow for provenance
    printed = 0
    for w in plan.get("why_lines") or []:
        lines.append(f"  WHY {w}")
        printed += 1
        if printed >= 40:
            break
    if plan.get("query_touched"):
        lines.append(
            f"  QUERY_GATE query_touched=yes files={len(plan.get('query_files') or [])} "
            f"(run: bash scripts/bin/query-plan-gate.sh)"
        )
    if printed < 20:
        for fl in plan.get("flows") or []:
            for w in fl.get("why") or []:
                lines.append(f"  WHY flow={fl.get('api')}: {w}")
                printed += 1
                if printed >= 40:
                    break
            if printed >= 40:
                break
    for m in (plan.get("missing_flows") or [])[:10]:
        lines.append(f"  MISSING_CASE api={m.get('api')} (stub draftable)")
    if plan.get("drafted_stubs"):
        lines.append(f"  stubs_drafted={plan['drafted_stubs']}")
    if not plan.get("files"):
        lines.append("  (no dirty/pending paths — empty plan)")
    lines.append("===== END IMPACT PLAN =====")
    return "\n".join(lines)


# --- Self-upgrade findings → backlog ---


def record_finding(
    finding_id: str,
    title: str,
    *,
    sot_entry: str,
    auto_safe: bool = True,
    draft_plan: str = "",
) -> dict:
    """SoT finding → self-upgrade findings + backlog item."""
    data = {"version": 1, "findings": []}
    if FINDINGS.is_file():
        try:
            data = json.loads(FINDINGS.read_text(encoding="utf-8"))
        except Exception:
            pass
    existing = {f.get("id") for f in data.get("findings") or []}
    item = {
        "id": finding_id,
        "title": title,
        "sot": sot_entry,
        "status": "open",
        "auto_safe": auto_safe,
        "draft_plan": draft_plan,
        "created_at": _utc(),
        "oldest_at": _utc(),
    }
    if finding_id not in existing:
        data.setdefault("findings", []).append(item)
        FINDINGS.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    bl = {"version": 1, "items": []}
    if BACKLOG.is_file():
        try:
            bl = json.loads(BACKLOG.read_text(encoding="utf-8"))
        except Exception:
            pass
    bids = {x.get("id") for x in bl.get("items") or []}
    if finding_id not in bids:
        bl.setdefault("items", []).append(
            {
                "id": finding_id,
                "title": title,
                "status": "open",
                "auto_safe": auto_safe,
                "perf": False,
                "source": "self_upgrade",
                "draft_plan": draft_plan or sot_entry,
                "created_at": _utc(),
            }
        )
        bl["updated"] = _utc()[:10]
        BACKLOG.write_text(json.dumps(bl, indent=2) + "\n", encoding="utf-8")
    return item


def mark_finding_done(finding_id: str, note: str = "") -> None:
    if FINDINGS.is_file():
        data = json.loads(FINDINGS.read_text(encoding="utf-8"))
        for f in data.get("findings") or []:
            if f.get("id") == finding_id:
                f["status"] = "done"
                f["done_at"] = _utc()
                f["note"] = note
        FINDINGS.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    if BACKLOG.is_file():
        bl = json.loads(BACKLOG.read_text(encoding="utf-8"))
        for x in bl.get("items") or []:
            if x.get("id") == finding_id:
                x["status"] = "done"
                x["done_date"] = _utc()[:10]
                x["note"] = note
        BACKLOG.write_text(json.dumps(bl, indent=2) + "\n", encoding="utf-8")


def self_report_unincorporated() -> str:
    open_n = 0
    oldest = None
    if FINDINGS.is_file():
        data = json.loads(FINDINGS.read_text(encoding="utf-8"))
        for f in data.get("findings") or []:
            if f.get("status") == "open":
                open_n += 1
                oa = f.get("oldest_at") or f.get("created_at")
                if oldest is None or (oa and oa < oldest):
                    oldest = oa
    age = "n/a"
    if oldest:
        try:
            from datetime import datetime, timezone

            t = datetime.strptime(oldest, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            age = f"{(datetime.now(timezone.utc) - t).days}d"
        except Exception:
            age = oldest
    return f"unincorporated findings: {open_n} (oldest age {age})"


def main() -> int:
    ap = argparse.ArgumentParser(description="Dynamic impact-tests plan (KG blast radius)")
    ap.add_argument("--range", dest="range_spec", default=None, help="git diff range e.g. origin/main...HEAD")
    ap.add_argument("--path", action="append", default=[], help="Explicit path(s)")
    ap.add_argument("--from-pending", action="store_true", default=True)
    ap.add_argument("--no-pending", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--banner", action="store_true")
    ap.add_argument("--mark-ran", action="store_true")
    ap.add_argument("--check-ran", action="store_true")
    ap.add_argument("--no-stubs", action="store_true")
    ap.add_argument("--waiver", default="", help="Log explicit waiver reason and exit 0")
    args = ap.parse_args()

    if args.waiver:
        log_waiver(args.waiver)
        print(f"impact-tests WAIVER logged: {args.waiver}")
        return 0

    if args.check_ran:
        ok, msg = impact_ran_satisfied()
        print(msg)
        return 0 if ok else 1

    plan = build_plan(
        range_spec=args.range_spec,
        from_pending=not args.no_pending,
        paths=args.path or None,
        draft_stubs=not args.no_stubs,
    )
    if args.mark_ran:
        mark_ran(plan)
    if args.json:
        print(json.dumps(plan, indent=2))
    else:
        print(format_banner(plan))
        if args.mark_ran:
            print(f"marked ran → {RAN_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
