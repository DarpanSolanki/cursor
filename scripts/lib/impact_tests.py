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
FLOW_COV = ROOT / "scripts/testing/flow_coverage.json"
INVARIANTS_CASE = "flowtest.invariants_universal"
SMOKE_READ_CASE = "accounting.read_smoke"
# L2 speed doctrine — wall estimates (seconds) when registry ship_baseline missing
_WALL_FULL_FLOW = 90
_WALL_SMOKE = 20
_WALL_HEALTH = 8
_WALL_INVARIANTS = 15

# Dirty-tree noise — must not expand blast radius (G1 evidence: settings.gradle ×17 repos).
_NOISE_FRAGMENTS = (
    "/settings.gradle",
    "/logs/",
    "commits_with_files_",
    "/archieve/scripts/",
    "/sli/archieve/",
    ".csv",
    "aepsBioAuthRequest.xml",
    "QA_Authorization_Cache.txt",
    "application/dist/application.properties",
)

_REPLAY_AXIS_FRAGMENTS = (
    "clientreferencededup",
    "dedup",
    "callback",
    "replay",
    "idempoten",
    "stan",
    "messagebroker",
    "kafkaconsumer",
    "lmsmessagebroker",
)

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


def _is_noise_path(rel: str) -> bool:
    s = rel.replace("\\", "/").lower()
    return any(f.lower() in s for f in _NOISE_FRAGMENTS)


def _repo_of(rel: str) -> str:
    s = rel.replace("\\", "/")
    if s.startswith("trustt-") or s.startswith("novopay-"):
        return s.split("/", 1)[0]
    return ""


def _scope_out_cases() -> set[str]:
    """Registry cases for flows permanently scope=out (penal cut + domain scope=out)."""
    out: set[str] = set()
    if FLOW_COV.is_file():
        try:
            data = json.loads(FLOW_COV.read_text(encoding="utf-8"))
            for row in data.get("flows") or []:
                if (row.get("scope") or "").lower() == "out":
                    key = row.get("registry")
                    if key:
                        out.add(str(key))
        except Exception:
            pass
    try:
        from accounting_flow_domains import load_domains, domain_cases  # noqa: WPS433

        reg = load_registry()
        for did, meta in load_domains().items():
            if (meta.get("scope") or "").lower() != "out":
                continue
            for phase in ("impact", "deep", "release"):
                for cid in domain_cases(did, phase=phase, reg=reg):
                    out.add(cid)
    except Exception:
        pass
    return out


def _filter_changed_paths(paths: list[str], *, pending_anchor: list[str] | None = None) -> list[str]:
    """Drop noise; when pending anchor exists, only keep dirty from touched repos."""
    anchor = pending_anchor or []
    anchor_repos = {_repo_of(p) for p in anchor if _repo_of(p)}
    filtered: list[str] = []
    for p in paths:
        if _is_noise_path(p) and p not in anchor:
            continue
        if anchor_repos and _repo_of(p) and _repo_of(p) not in anchor_repos:
            continue
        filtered.append(p)
    return filtered


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

    pending_anchor = list(out) if from_pending and out else []

    # Always union dirty trees (human edits regardless of author) — scoped to pending repos when anchored.
    for repo in [ROOT, *sorted(ROOT.glob("trustt-*")), *sorted(ROOT.glob("novopay-*"))]:
        if not (repo / ".git").is_dir():
            continue
        repo_name = "" if repo == ROOT else f"{repo.name}/"
        if pending_anchor and repo != ROOT and repo_name.rstrip("/") not in {
            _repo_of(p) for p in pending_anchor
        }:
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
    return _filter_changed_paths(out, pending_anchor=pending_anchor or None)


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
            # SU-IMPACT-002: never silent-skip — map to health.<svc> or count as missing
            svc = api.split(":", 1)[-1].strip().lower().replace("_", "")
            health_id = None
            for cid, meta in (reg or {}).items():
                if not cid.startswith("health.") or not isinstance(meta, dict):
                    continue
                if svc and svc in cid.lower().replace("_", "").replace("-", ""):
                    health_id = cid
                    break
            if health_id and health_id not in seen:
                seen.add(health_id)
                cases.append(
                    {
                        "case": health_id,
                        "api": api,
                        "why": (fl.get("why") or [f"topic-consumer→{health_id}"])[0],
                        "why_all": fl.get("why") or [],
                        "tables": fl.get("tables") or [],
                        "role": "topic_consumer_health",
                    }
                )
            else:
                missing.append(
                    {
                        "api": api,
                        "why": fl.get("why") or [f"topic-consumer unmapped:{api}"],
                        "tables": fl.get("tables") or [],
                    }
                )
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


def flow_case_coverage_ok(flows: list[dict], cases: list[dict], missing: list[dict]) -> tuple[bool, str]:
    """SU-IMPACT-002 invariant: every non-empty flow set must resolve to cases and/or missing.

    Note: one flow may map to many cases, so equality is on flow coverage, not counts.
    """
    if not flows:
        return True, "no flows"
    covered_apis = {c.get("api") for c in cases} | {m.get("api") for m in missing}
    flow_apis = {f.get("api") for f in flows}
    uncovered = sorted(a for a in flow_apis if a and a not in covered_apis)
    if uncovered:
        return False, f"uncovered flows={uncovered[:8]}"
    return True, f"flows={len(flow_apis)} covered via cases={len(cases)} missing={len(missing)}"


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


def _money_path_touched(changed: list[str], flows: list[dict], cases: list[dict]) -> bool:
    if acceptance_guards(flows, cases):
        return True
    blob = " ".join(p.replace("\\", "/").lower() for p in changed)
    return any(
        tok in blob
        for tok in (
            "/loan/",
            "foreclos",
            "disburse",
            "transaction",
            "posting",
            "scripts/testing/flowtest",
            "scripts/dcf_",
            "scripts/dpic/",
        )
    )


def _replay_axis_flags(changed: list[str]) -> dict[str, str]:
    blob = " ".join(p.replace("\\", "/").lower() for p in changed)
    flags: dict[str, str] = {}
    if any(f in blob for f in _REPLAY_AXIS_FRAGMENTS):
        flags["replay_dedup_callback"] = "NOT-EXERCISED"
    return flags


def _exclude_scope_out(case_ids: list[str]) -> tuple[list[str], list[str]]:
    out_cases = _scope_out_cases()
    if not out_cases:
        return case_ids, []
    kept, dropped = [], []
    for cid in case_ids:
        if cid in out_cases:
            dropped.append(cid)
        else:
            kept.append(cid)
    return kept, dropped


def _flow_is_sibling_only(fl: dict) -> bool:
    whys = fl.get("why") or fl.get("why_all") or []
    if not whys:
        return False
    return all("→ sibling" in w or "sibling processor" in w for w in whys)


def _direct_apis_from_nodes(
    nodes: list[dict], flows: list[dict], changed: list[str] | None = None
) -> set[str]:
    """Apis tied to changed files (non-sibling KG expansion)."""
    direct: set[str] = set()
    for fl in flows:
        if not _flow_is_sibling_only(fl):
            direct.add(str(fl.get("api") or ""))
    for n in nodes:
        if n.get("kind") == "request" and n.get("via") in (
            "orch_xml",
            "change_test_map_seed",
            "change_test_map_path",
        ):
            direct.add(_norm_api(n["id"]))
    if changed and api_from_path:
        for p in changed:
            hint = api_from_path(p)
            if hint:
                direct.add(hint)
    return {a for a in direct if a}


def _foreclosure_path_touch(changed: list[str]) -> bool:
    blob = " ".join(p.replace("\\", "/").lower() for p in (changed or []))
    return any(
        tok in blob
        for tok in (
            "forcebill",
            "foreclos",
            "/loan/foreclosure",
            "loanprepayment",
            "individualchildloanforeclosure",
        )
    )


def _case_wall_s(cid: str, reg: dict) -> int:
    meta = reg.get(cid) or {}
    bl = meta.get("ship_baseline") or {}
    if bl.get("wall_s"):
        return int(bl["wall_s"])
    if cid == INVARIANTS_CASE:
        return _WALL_INVARIANTS
    if cid == SMOKE_READ_CASE:
        return _WALL_SMOKE
    if cid.startswith("health."):
        return _WALL_HEALTH
    if cid.startswith("dcf."):
        return 600
    if meta.get("type") == "flow":
        return _WALL_FULL_FLOW
    return _WALL_SMOKE


# Representative-variant pick order inside a prefix family (A1 SU-TIER-VARIANT)
_DCF_REPRESENTATIVE_ORDER = (
    "dcf.group_parent_last_child_e2e",  # canonical money e2e + ship_baseline
    "dcf.force_bill_crn_sim",  # ForceBill CRN uniqueness
    "dcf.vikram_fc_rstcre_dfc_e2e",  # cross-path FC→RSTCRE→DFC
    "dcf.principal_split_sim",
    "dcf.group_parent_last_child_e2e_clean",
)


def _apply_representative_variants(
    full_cases: list[str],
    *,
    prefix: str = "dcf.",
    max_full: int = 3,
) -> tuple[list[str], list[str], list[str]]:
    """Keep ≤max_full representatives full; demote same-prefix siblings to smoke.

    Catch-power: one canonical e2e + ForceBill-specific sim + one cross-path cover
    the money write shapes; remaining variants share GL/invariants so smoke catches
    product imbalance without 12× full wall.
    """
    family = [c for c in full_cases if c.startswith(prefix)]
    if len(family) <= max_full:
        return full_cases, [], []
    preferred = [c for c in _DCF_REPRESENTATIVE_ORDER if c in family]
    keep: list[str] = []
    for c in preferred:
        if c not in keep:
            keep.append(c)
        if len(keep) >= max_full:
            break
    for c in family:
        if len(keep) >= max_full:
            break
        if c not in keep:
            keep.append(c)
    demote = [c for c in family if c not in keep]
    keep_set = set(keep)
    new_full = [c for c in full_cases if not c.startswith(prefix) or c in keep_set]
    lines = [
        f"TIER variant-full {c}: representative of {prefix}* family ({len(family)}→{len(keep)})"
        for c in keep
    ] + [
        f"TIER variant-smoke {c}: same-family sibling of representatives (invariant-smoke)"
        for c in demote
    ]
    return new_full, demote, lines


def _apply_selection_tiering(
    ordered: list[str],
    *,
    cases: list[dict],
    domain_added: list[str],
    nodes: list[dict],
    flows: list[dict],
    changed: list[str],
    reg: dict,
) -> tuple[list[str], list[str], dict]:
    """L2: direct-impact → full run; sibling write blast → invariants + read_smoke."""
    direct_apis = _direct_apis_from_nodes(nodes, flows, changed)
    fc_touch = _foreclosure_path_touch(changed)
    case_tier: dict[str, str] = {}
    for c in cases:
        case_tier[c["case"]] = (
            "smoke" if _flow_is_sibling_only({"why_all": c.get("why_all") or [c.get("why", "")]}) else "full"
        )

    tier_lines: list[str] = []
    full_cases: list[str] = []
    skipped_smoke: list[str] = []

    for cid in ordered:
        if cid in (INVARIANTS_CASE, SMOKE_READ_CASE):
            continue
        meta = reg.get(cid) or {}
        api = str(meta.get("api") or "")
        tier = case_tier.get(cid)
        if tier == "smoke" and fc_touch and (
            cid.startswith("foreclosure.")
            or cid.startswith("dcf.")
            or cid.startswith("flowtest.loan_prepayment")
        ):
            tier = "full"
        if tier is None:
            if api in direct_apis:
                tier = "full"
            elif fc_touch and any(
                tok in cid
                for tok in (
                    "foreclosure.",
                    "dcf.",
                    "flowtest.loan_prepayment",
                    "flowtest.loan_prepayment_fc",
                )
            ):
                tier = "full"
            elif cid in domain_added:
                tier = "smoke"
            elif cid.startswith("health.") or cid == SMOKE_READ_CASE:
                tier = "smoke"
            else:
                tier = "smoke"
        why = case_tier.get(cid) and "KG case map" or f"api={api or 'domain'}"
        if tier == "full":
            if cid not in full_cases:
                full_cases.append(cid)
                tier_lines.append(f"TIER full {cid}: direct-impact ({why})")
        else:
            skipped_smoke.append(cid)
            tier_lines.append(f"TIER smoke-skip {cid}: sibling/domain blast ({why})")

    # A1: within dcf.* full set, keep ≤3 representatives; demote rest to smoke
    full_cases, demoted_variants, variant_lines = _apply_representative_variants(full_cases)
    for c in demoted_variants:
        if c not in skipped_smoke:
            skipped_smoke.append(c)
    tier_lines.extend(variant_lines)

    smoke_exec: list[str] = []
    if skipped_smoke:
        if INVARIANTS_CASE in reg:
            smoke_exec.append(INVARIANTS_CASE)
        if SMOKE_READ_CASE in reg:
            smoke_exec.append(SMOKE_READ_CASE)
        tier_lines.append(
            f"TIER smoke-exec {smoke_exec}: invariant-guarded smoke replaces "
            f"{len(skipped_smoke)} sibling/domain cases"
        )

    final: list[str] = []
    for cid in [INVARIANTS_CASE] + full_cases + smoke_exec:
        if not cid or cid in final:
            continue
        if (reg.get(cid) or {}).get("quarantine"):
            continue
        final.append(cid)

    wall_full = sum(_case_wall_s(c, reg) for c in full_cases)
    wall_smoke = sum(_case_wall_s(c, reg) for c in smoke_exec)
    # invariants counted once (may already be in smoke_exec or prepended)
    inv_extra = 0 if INVARIANTS_CASE in smoke_exec or INVARIANTS_CASE in full_cases else _case_wall_s(
        INVARIANTS_CASE, reg
    )
    wall_naive = sum(
        _case_wall_s(c, reg)
        for c in ordered
        if c and not (reg.get(c) or {}).get("quarantine")
    )
    stats = {
        "full_count": len(full_cases),
        "smoke_skip_count": len(skipped_smoke),
        "smoke_exec_count": len(smoke_exec),
        "variant_demoted": len(demoted_variants),
        "wall_full_s": wall_full,
        "wall_smoke_s": wall_smoke,
        "wall_planned_s": wall_full + wall_smoke + inv_extra,
        "wall_naive_full_s": wall_naive,
        "wall_saved_pct": (
            round(100.0 * (1.0 - (wall_full + wall_smoke + inv_extra) / wall_naive), 1)
            if wall_naive
            else 0.0
        ),
    }
    return final, tier_lines, stats


def domain_mandatory_cases(
    changed: list[str], flows: list[dict], cases: list[dict]
) -> tuple[list[str], list[str]]:
    """Mandatory suite: accounting money domains + LMS-wide service health/impact.

    Accounting paths use accounting_flow_domains.json. Non-accounting LMS repos
    (LOS, payments, actor, …) use lms_service_domains.json → health.* cases.
    Quarantined registry cases are excluded. Fail-closed via ship-loop ordered_cases.
    """
    try:
        from accounting_flow_domains import resolve_accounting_domain_cases  # noqa: WPS433
    except ImportError:
        resolve_accounting_domain_cases = None  # type: ignore
    try:
        from lms_service_domains import resolve_lms_service_cases  # noqa: WPS433
    except ImportError:
        resolve_lms_service_cases = None  # type: ignore

    reg = load_registry()
    apis = {str(f.get("api") or "") for f in flows if f.get("api")}
    for c in cases:
        if c.get("api"):
            apis.add(str(c["api"]))
    blob = " ".join(p.replace("\\", "/").lower() for p in changed)
    moneyish = bool(acceptance_guards(flows, cases))
    for c in cases:
        meta = reg.get(c["case"]) or {}
        if meta.get("smoke_tier") == "money":
            moneyish = True
            break
    tier = "money" if moneyish else "service"
    base = [c["case"] for c in cases if not (reg.get(c["case"]) or {}).get("quarantine")]
    merged = list(base)
    added: list[str] = []

    # Accounting money domains only when an accounting/dpic/dcf path is touched.
    # LOS …/disbursement/… maps to disburseLoan via change_test_map — that must NOT
    # pull the full DCF/FC mandatory suite (lms_service_domains covers health.los).
    acct_path_touch = any(
        any(tok in p.replace("\\", "/").lower() for tok in (
            "accounting", "scripts/dpic/", "scripts/dcf_", "scripts/foreclosure",
            "scripts/testing/flowtest",
        ))
        for p in changed
    )
    if resolve_accounting_domain_cases and acct_path_touch:
        acct = resolve_accounting_domain_cases(
            blob, apis, merged, tier=tier, reg=reg, paths=changed
        )
        for cid in acct:
            if cid not in merged and not (reg.get(cid) or {}).get("quarantine"):
                merged.append(cid)
                if cid not in base:
                    added.append(cid)

    if resolve_lms_service_cases:
        lms_merged, lms_added = resolve_lms_service_cases(changed, merged, reg=reg)
        for cid in lms_added:
            if cid not in added:
                added.append(cid)
        merged = lms_merged

    return merged, added


def build_plan(
    *,
    range_spec: str | None = None,
    from_pending: bool = True,
    paths: list[str] | None = None,
    draft_stubs: bool = False,
) -> dict:
    changed = collect_changed_paths(
        range_spec=range_spec, from_pending=from_pending, paths=paths
    )
    conn = _kg()
    nodes: list[dict] = []
    for p in changed:
        nodes.extend(path_to_nodes(p, conn))
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
    cov_ok, cov_msg = flow_case_coverage_ok(flows, cases, missing)
    reg = load_registry()
    cases = [c for c in cases if not (reg.get(c["case"]) or {}).get("quarantine")]
    stubs = draft_missing_stubs(missing) if draft_stubs else []
    guards = acceptance_guards(flows, cases)
    domain_ordered, domain_added = domain_mandatory_cases(changed, flows, cases)

    case_ids = [c["case"] for c in cases]
    ordered = [
        c
        for c in dict.fromkeys(guards + domain_ordered + case_ids)
        if not (reg.get(c) or {}).get("quarantine")
    ]
    money_touch = _money_path_touched(changed, flows, cases)
    if money_touch and INVARIANTS_CASE in (reg or {}) and INVARIANTS_CASE not in ordered:
        ordered.insert(0, INVARIANTS_CASE)
    ordered, scope_dropped = _exclude_scope_out(ordered)
    replay_axes = _replay_axis_flags(changed)
    ordered, tier_lines, tier_stats = _apply_selection_tiering(
        ordered,
        cases=cases,
        domain_added=domain_added,
        nodes=uniq_nodes,
        flows=flows,
        changed=changed,
        reg=reg,
    )

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
        "domain_layer": (
            "accounting_flow_domains.json + lms_service_domains.json "
            "(mandatory LMS money + non-money service health)"
        ),
        "files": changed,
        "nodes": uniq_nodes,
        "flows": flows,
        "cases": cases,
        "ordered_cases": ordered,
        "missing_flows": missing,
        "flow_coverage_ok": cov_ok,
        "flow_coverage_msg": cov_msg,
        "drafted_stubs": [s["id"] for s in stubs],
        "acceptance_guards": guards,
        "domain_mandatory_added": domain_added,
        "scope_out_dropped": scope_dropped,
        "invariants_mandatory": money_touch,
        "reality_axes": replay_axes,
        "selection_tier_lines": tier_lines,
        "selection_tier_stats": tier_stats,
        "why_lines": [f"{c['case']}: {c['why']}" for c in cases]
        + [f"{cid}: domain_mandatory_suite" for cid in domain_added],
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
    cov_ok = plan.get("flow_coverage_ok")
    if cov_ok is not None:
        lines.append(
            f"  FLOW_CASE_COVERAGE {'OK' if cov_ok else 'FAIL'} {plan.get('flow_coverage_msg')}"
        )
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
    if plan.get("domain_mandatory_added"):
        lines.append(
            f"  DOMAIN_MANDATORY +{len(plan['domain_mandatory_added'])} "
            f"({', '.join(plan['domain_mandatory_added'][:12])}"
            f"{'…' if len(plan['domain_mandatory_added']) > 12 else ''})"
        )
    if plan.get("invariants_mandatory"):
        lines.append(f"  INVARIANTS_MANDATORY {INVARIANTS_CASE} (money-path universal layer)")
    if plan.get("scope_out_dropped"):
        lines.append(
            f"  SCOPE_OUT dropped={plan['scope_out_dropped'][:8]}"
            f"{'…' if len(plan['scope_out_dropped']) > 8 else ''}"
        )
    for axis, status in (plan.get("reality_axes") or {}).items():
        lines.append(f"  REALITY_AXIS {axis}={status}")
    stats = plan.get("selection_tier_stats") or {}
    if stats:
        lines.append(
            f"  SELECTION_TIER full={stats.get('full_count')} smoke_skip={stats.get('smoke_skip_count')} "
            f"smoke_exec={stats.get('smoke_exec_count')} "
            f"variant_demoted={stats.get('variant_demoted', 0)} "
            f"wall_planned={stats.get('wall_planned_s')}s "
            f"wall_naive_full={stats.get('wall_naive_full_s')}s "
            f"wall_saved={stats.get('wall_saved_pct', 0)}% "
            f"(serial-suite estimate — not parallel wall)"
        )
    for tl in (plan.get("selection_tier_lines") or [])[:25]:
        lines.append(f"  {tl}")
    if len(plan.get("selection_tier_lines") or []) > 25:
        lines.append(f"  … +{len(plan['selection_tier_lines']) - 25} tier lines")
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
    ap.add_argument(
        "--draft-stubs",
        action="store_true",
        help="Opt-in: write impact.stub.* drafts into registry-proposals.json (default OFF — was flooding dirty tree)",
    )
    ap.add_argument(
        "--no-stubs",
        action="store_true",
        help="Deprecated no-op (stubs already off by default)",
    )
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
        draft_stubs=bool(args.draft_stubs),
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
