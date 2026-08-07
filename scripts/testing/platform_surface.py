#!/usr/bin/env python3
"""Map the platform's other surfaces: events, schedules, data, errors, GL rules, processors.

`platform_api_map.py` maps what a caller can invoke. That is one way into the system and not
the one most incidents arrive through — a stuck flow is usually a Kafka consumer that swallowed
a message, a batch that ran at 2am, a table whose writer nobody could name, or an error code
with no home. Those surfaces were only ever reachable by grep.

Every fact comes from the KG, which already indexes all five; nothing here re-derives them
from source. Six bulk queries against `kg.db` replace what would otherwise be thousands of
subprocess calls, so a full sweep is under a second and the maps can be regenerated whenever
the code moves rather than aging into fiction.

    platform_surface.py              write all five maps + the reference
    platform_surface.py --events     topics, their producers and consumers
    platform_surface.py --schedules  what runs unattended, and what it triggers
    platform_surface.py --data       every table, and the APIs that write it
    platform_surface.py --errors     every code, its throw sites and the flows that raise it
    platform_surface.py --gl         double-entry posting rules and what selects them
    platform_surface.py --processors which flows each processor runs in
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sqlite3

ROOT = pathlib.Path(__file__).resolve().parents[2]
FLOW = ROOT / "cursor-bundle" / "flow-test"
KGDB = ROOT / "cursor-bundle" / "kg" / "data" / "kg.db"
DOC = ROOT / ".cursor" / "platform-surface-map.md"

EVENTS = FLOW / "platform_events.jsonl"
SCHEDULES = FLOW / "platform_schedulers.jsonl"
DATA = FLOW / "platform_tables.jsonl"
ERRORS = FLOW / "platform_errors.jsonl"
GLRULES = FLOW / "platform_gl_rules.jsonl"
PROCESSORS = FLOW / "platform_processors.jsonl"


def connect() -> sqlite3.Connection:
    if not KGDB.is_file():
        raise SystemExit(f"KG not built: {KGDB}")
    return sqlite3.connect(f"file:{KGDB}?mode=ro", uri=True)


def bare(node_id: str) -> str:
    return node_id.split(":", 1)[1] if ":" in node_id else node_id


def api_of(node_id: str) -> tuple[str, str]:
    repo, _, api = bare(node_id).partition("/")
    return (repo, api) if api else ("", repo)


def request_tables(con: sqlite3.Connection) -> tuple[dict, dict]:
    """Which APIs write and read each table — the reverse of the API map's footprint."""
    writers: dict[str, set] = collections.defaultdict(set)
    readers: dict[str, set] = collections.defaultdict(set)
    rows = con.execute(
        """SELECT e1.src_id, e2.rel, n.label FROM edges e1
           JOIN edges e2 ON e2.src_id = e1.dst_id
           JOIN nodes n ON n.id = e2.dst_id
           WHERE e1.rel='invokes' AND e2.rel IN ('reads','writes','deletes')
             AND n.kind='table' AND e1.src_id LIKE 'request:%'""")
    for rid, rel, table in rows:
        repo, api = api_of(rid)
        (readers if rel == "reads" else writers)[table].add(f"{repo}/{api}")
    return writers, readers


def events(con: sqlite3.Connection) -> list[dict]:
    consumers: dict[str, set] = collections.defaultdict(set)
    services: dict[str, set] = collections.defaultdict(set)
    emitters: dict[str, set] = collections.defaultdict(set)
    for src, rel, dst in con.execute(
            "SELECT src_id, rel, dst_id FROM edges WHERE dst_id LIKE 'topic:%'"):
        topic = bare(dst)
        if rel == "emits":
            emitters[topic].add(bare(src))
        elif src.startswith("service:"):
            services[topic].add(bare(src))
        else:
            consumers[topic].add(bare(src))
    topics = con.execute(
        "SELECT label, repo, json FROM nodes WHERE kind='topic' ORDER BY label").fetchall()
    out = []
    for t, repo, blob in topics:
        meta = {}
        try:
            meta = json.loads(blob or "{}")
        except json.JSONDecodeError:
            pass
        out.append({"topic": t, "repo": repo,
                    "consumer_services": sorted(services[t]),
                    "consumer_classes": sorted(consumers[t]),
                    "emitted_by": sorted(emitters[t]),
                    "producer_site": meta.get("src"),
                    "producer_method": meta.get("note"),
                    "literal": bool(re.fullmatch(r"[a-z][a-z0-9_]{4,}", t or "")),
                    "orphan": not (services[t] or consumers[t])})
    return out


def schedules(con: sqlite3.Connection) -> list[dict]:
    triggers: dict[str, set] = collections.defaultdict(set)
    cfg: dict[str, set] = collections.defaultdict(set)
    for src, rel, dst in con.execute(
            "SELECT src_id, rel, dst_id FROM edges WHERE src_id LIKE 'scheduler:%'"):
        name = bare(src)
        if rel == "triggers" and dst.startswith("request:"):
            triggers[name].add(bare(dst))
        elif rel == "has_batch_cfg":
            cfg[name].add(bare(dst))
    rows = con.execute(
        "SELECT label, repo, json FROM nodes WHERE kind='scheduler' ORDER BY label").fetchall()
    out = []
    for label, repo, blob in rows:
        meta = {}
        try:
            meta = json.loads(blob or "{}")
        except json.JSONDecodeError:
            pass
        src = meta.get("src") or ""
        out.append({"scheduler": label, "repo": repo,
                    "triggers": sorted(triggers[label]),
                    "batch_config": sorted(cfg[label]),
                    "cron": meta.get("cron") or meta.get("schedule"),
                    "src": src,
                    "from_doc": src.endswith(".md"),
                    "unmapped": not triggers[label]})
    return out


def schema_index() -> dict[str, dict]:
    """The live column shape, from the schema oracle rather than re-derived here.

    `cursor-bundle/schema/tables.jsonl` already carries columns, FKs and indexes for 878
    tables. Joining it means one lookup answers both what is in a table and who writes it,
    and the column names stay resolvable — `40-knowledge-upkeep.md` forbids naming a column
    from memory, and this is where the answer lives.
    """
    path = ROOT / "cursor-bundle" / "schema" / "tables.jsonl"
    if not path.is_file():
        return {}
    out: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        cols = row.get("columns") or []
        out.setdefault(row["table"], {
            "schema": row.get("schema"),
            "column_count": len(cols),
            "primary_key": [c["name"] for c in cols if c.get("pk")],
            "columns": [c["name"] for c in cols],
            "foreign_keys": len(row.get("fks") or []),
            "indexes": len(row.get("indexes") or []),
        })
    return out


def data(con: sqlite3.Connection) -> list[dict]:
    writers, readers = request_tables(con)
    entity: dict[str, set] = collections.defaultdict(set)
    for src, dst in con.execute(
            "SELECT src_id, dst_id FROM edges WHERE rel='maps_to' AND dst_id LIKE 'table:%'"):
        entity[bare(dst)].add(bare(src))
    rows = con.execute(
        "SELECT label, repo FROM nodes WHERE kind='table' ORDER BY label").fetchall()
    schema = schema_index()
    known = set()
    out = []
    for t, repo in rows:
        known.add(t)
        shape = schema.get(t) or {}
        out.append({"table": t, "repo": repo,
                    "schema": shape.get("schema"),
                    "entities": sorted(entity[t]),
                    "written_by": sorted(writers[t]),
                    "read_by": sorted(readers[t]),
                    "writer_count": len(writers[t]),
                    "column_count": shape.get("column_count"),
                    "primary_key": shape.get("primary_key") or [],
                    "columns": shape.get("columns") or [],
                    "foreign_keys": shape.get("foreign_keys"),
                    "indexes": shape.get("indexes"),
                    "in_local_schema": t in schema,
                    "valid_name": bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", t or "")),
                    "no_known_writer": not writers[t]})
    for t, shape in sorted(schema.items()):
        if t in known:
            continue
        out.append({"table": t, "repo": None, "schema": shape["schema"],
                    "entities": [], "written_by": [], "read_by": [],
                    "writer_count": 0, "column_count": shape["column_count"],
                    "primary_key": shape["primary_key"], "columns": shape["columns"],
                    "foreign_keys": shape["foreign_keys"], "indexes": shape["indexes"],
                    "in_local_schema": True, "valid_name": True,
                    "no_known_writer": True})
    return sorted(out, key=lambda r: r["table"])


def call_graph(con: sqlite3.Connection) -> dict[str, set]:
    """Which flows each flow invokes, by full `repo/api` key."""
    by_name: dict[str, set] = collections.defaultdict(set)
    for rid, in con.execute("SELECT id FROM nodes WHERE kind='request'"):
        by_name[bare(rid).split("/", 1)[-1]].add(bare(rid))
    graph: dict[str, set] = collections.defaultdict(set)
    for src, dst in con.execute(
            "SELECT src_id, dst_id FROM edges WHERE rel='calls' "
            "AND src_id LIKE 'request:%' AND dst_id LIKE 'request:%'"):
        graph[bare(src)].add(bare(dst))
    for src, dst in con.execute(
            "SELECT src_id, dst_id FROM edges WHERE rel='calls_api' AND src_id LIKE 'request:%'"):
        graph[bare(src)] |= by_name.get(bare(dst), set())
    return graph


def errors(con: sqlite3.Connection) -> list[dict]:
    thrown: dict[str, set] = collections.defaultdict(set)
    for rid, code in con.execute(
            """SELECT e1.src_id, n.label FROM edges e1
               JOIN edges e2 ON e2.src_id = e1.dst_id
               JOIN nodes n ON n.id = e2.dst_id
               WHERE e1.rel='invokes' AND e2.rel='throws' AND n.kind='error'
                 AND e1.src_id LIKE 'request:%'"""):
        repo, api = api_of(rid)
        thrown[code].add(f"{repo}/{api}")

    graph = call_graph(con)
    callers_of: dict[str, set] = collections.defaultdict(set)
    for src, targets in graph.items():
        for dst in targets:
            callers_of[dst].add(src)
    inherited: dict[str, set] = collections.defaultdict(set)
    for code, direct in thrown.items():
        seen, queue = set(direct), list(direct)
        while queue:
            flow = queue.pop()
            for caller in callers_of.get(flow, ()):
                if caller not in seen:
                    seen.add(caller)
                    inherited[code].add(caller)
                    queue.append(caller)
    rows = con.execute(
        "SELECT label, json FROM nodes WHERE kind='error' ORDER BY label").fetchall()
    out = []
    for label, blob in rows:
        meta = {}
        try:
            meta = json.loads(blob or "{}")
        except json.JSONDecodeError:
            pass
        ctx = [k for k in (meta.get("ctx_keys") or "").split(",") if k][:24]
        out.append({"code": label, "throw_site": meta.get("src"),
                    "sites": meta.get("sites"),
                    "branches": [b for b in (meta.get("branches") or "").split(",") if b],
                    "context_keys": ctx,
                    "raised_by": sorted(thrown[label]),
                    "surfaces_in": sorted(inherited[label]),
                    "unreachable_from_any_api": not (thrown[label] or inherited[label])})
    return out


def gl_rules(con: sqlite3.Connection) -> list[dict]:
    """The double-entry posting rules, and the processors that select each transaction type.

    A GL question is always two questions — which legs does this transaction post, and what
    code decides it is that transaction. The KG holds both as `gl_rule` nodes and
    `sets_txn_type` edges; nothing joined them.
    """
    setters: dict[str, set] = collections.defaultdict(set)
    for src, dst in con.execute(
            "SELECT src_id, dst_id FROM edges WHERE rel='sets_txn_type'"):
        setters[bare(dst)].add(bare(src))
    rows = con.execute(
        "SELECT label, repo, json FROM nodes WHERE kind='gl_rule' ORDER BY label").fetchall()
    out = []
    for label, repo, blob in rows:
        try:
            meta = json.loads(blob or "{}")
        except json.JSONDecodeError:
            continue
        txn = meta.get("txn_type") or ""
        is_rule = meta.get("rule_id") is not None
        out.append({"rule": label, "repo": repo, "is_posting_rule": is_rule,
                    "txn_type": txn, "txn_sub_type": meta.get("txn_sub_type"),
                    "sequence": meta.get("sequence"), "rule_id": meta.get("rule_id"),
                    "reference_code": meta.get("reference_code"),
                    "debit_placeholder": meta.get("debit_placeholder"),
                    "credit_placeholder": meta.get("credit_placeholder"),
                    "selected_by": sorted(setters.get(txn, ())),
                    "half_defined": is_rule and not (meta.get("debit_placeholder")
                                                     and meta.get("credit_placeholder"))})
    return out


def processors(con: sqlite3.Connection) -> list[dict]:
    """Every processor, and the flows that would change if you edited it.

    Editing a processor is the most common change in this workspace and the one whose blast
    radius is least visible: `populateUserDetails` runs in 124 flows across four services.
    The KG stores the edge as flow -> processor, so the reuse count only appears if you
    invert it.
    """
    used_by: dict[str, set] = collections.defaultdict(set)
    for src, dst in con.execute(
            "SELECT src_id, dst_id FROM edges WHERE rel='invokes' AND dst_id LIKE 'processor:%'"):
        used_by[bare(dst)].add(bare(src))
    touches: dict[str, dict] = collections.defaultdict(
        lambda: {"reads": set(), "writes": set(), "throws": set(), "calls": set()})
    for src, rel, dst in con.execute(
            "SELECT src_id, rel, dst_id FROM edges WHERE src_id LIKE 'processor:%' "
            "AND rel IN ('reads','writes','deletes','throws','calls')"):
        key = "writes" if rel in ("writes", "deletes") else rel
        touches[bare(src)][key].add(bare(dst))
    rows = con.execute(
        "SELECT label, repo, json FROM nodes WHERE kind='processor' ORDER BY label").fetchall()
    out = []
    for label, repo, blob in rows:
        try:
            meta = json.loads(blob or "{}")
        except json.JSONDecodeError:
            meta = {}
        flows = sorted(used_by.get(label, ()))
        t = touches.get(label) or {"reads": (), "writes": (), "throws": (), "calls": ()}
        repos = sorted({f.split("/")[0] for f in flows})
        out.append({"processor": label, "repo": repo, "src": meta.get("src"),
                    "used_by_flows": flows, "flow_count": len(flows),
                    "spans_repos": repos, "shared": len(repos) > 1,
                    "writes": sorted(t["writes"]), "reads": sorted(t["reads"]),
                    "throws": sorted(t["throws"]), "calls": sorted(t["calls"]),
                    "money_writer": bool(t["writes"])})
    return out


def write(path: pathlib.Path, header: str, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(f"# {header}\n")
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def markdown(ev: list[dict], sc: list[dict], da: list[dict], er: list[dict],
             gl: list[dict], pr: list[dict]) -> str:
    orphan = [e for e in ev if e["orphan"]]
    unmapped = [s for s in sc if s["unmapped"]]
    nowriter = [d for d in da if d["no_known_writer"]]
    unreach = [e for e in er if e["unreachable_from_any_api"]]
    busiest = sorted(da, key=lambda d: -d["writer_count"])[:12]
    byrepo = collections.Counter(s["repo"] for s in sc)

    out = ["# Platform surface map (generated — do not hand-edit)", "",
           "`python3 scripts/testing/platform_surface.py` regenerates this from the KG.",
           "Companion to `.cursor/platform-api-map.md`, which maps what a caller can invoke;",
           "this maps the four surfaces incidents actually arrive through.", "",
           "| Surface | Mapped | Detail |",
           "|---------|-------:|--------|",
           f"| Kafka topics | {len(ev)} | `cursor-bundle/flow-test/platform_events.jsonl` |",
           f"| Schedulers | {len(sc)} | `cursor-bundle/flow-test/platform_schedulers.jsonl` |",
           f"| Tables | {len(da)} | `cursor-bundle/flow-test/platform_tables.jsonl` |",
           f"| Error codes | {len(er)} | `cursor-bundle/flow-test/platform_errors.jsonl` |",
           "",
           "## Events", "",
           f"- **{len(ev)} topics**, {len(ev) - len(orphan)} with a known consumer.",
           f"- **{len(orphan)} with no consumer indexed** — either produced for an external",
           "  system, or a message going nowhere. `events.md` requires a consumer and a failure",
           "  posture in the same change set, so these are worth a look, not an alarm:",
           ""]
    out += [f"  - `{e['topic']}` — produced at `{e['producer_site'] or '?'}`"
            for e in orphan[:20]]
    if len(orphan) > 20:
        out.append(f"  - …and {len(orphan)-20} more")
    nonliteral = [e for e in ev if not e["literal"]]
    fromdoc = [s for s in unmapped if s["from_doc"]]
    if nonliteral:
        out += ["",
                f"**Indexing artefact, not a topic:** {len(nonliteral)} entr(y/ies) came from a "
                "variable rather than a literal — "
                + ", ".join(f"`{e['topic']}`" for e in nonliteral[:6])
                + ". The producer passes the topic name in, so the KG recorded the parameter.",
                "Unknown, not orphan."]
    out += ["", "## Schedules", "",
            f"- **{len(sc)} schedulers** across {len(byrepo)} repos: "
            + ", ".join(f"{r.replace('trustt-platform-','')} {n}"
                        for r, n in byrepo.most_common(8)),
            f"- **{len(unmapped)} trigger no request the KG can name.** {len(fromdoc)} of those",
            "  come from `.cursor/scheduler-registry.md` rather than code — documented names,",
            f"  not indexed beans. The other {len(unmapped)-len(fromdoc)}:", ""]
    out += [f"  - `{s['scheduler']}` — `{s['src'] or '?'}`"
            for s in unmapped if not s["from_doc"]]
    out += ["",
            "## Data", "",
            f"- **{len(da)} tables**, {len(da) - len(nowriter)} with an API that writes them.",
            f"- **{sum(1 for d in da if d['in_local_schema'])} carry their live column shape**",
            "  — columns, primary key, FK and index counts — joined from the schema oracle",
            "  (`cursor-bundle/schema/tables.jsonl`) rather than re-derived. Resolve a column",
            "  here before naming it: `40-knowledge-upkeep.md` treats a column written from",
            "  memory as a guess.",
            f"- **{sum(1 for d in da if not d['in_local_schema'])} are known to the KG but "
            "absent from the local DB.** That is train divergence, not proof the table does",
            "  not exist — say which branch you read.",
            f"- **{len(nowriter)} have no writer reachable from any API** — written by a batch",
            "  writer, a migration, or nothing at all."]
    unnamed = [d for d in da if not d["valid_name"]]
    if unnamed:
        out.append(f"- **{len(unnamed)} "
                   f"{'is' if len(unnamed) == 1 else 'are'} not a table name at all** "
                   f"({', '.join(repr(d['table']) for d in unnamed[:4])}) — a DAO call the KG "
                   "could not resolve. Flagged rather than dropped or counted as a table.")
    out += ["- Most-written tables (writer count is a blast-radius proxy):", ""]
    out += [f"  - `{d['table']}` — {d['writer_count']} APIs, {d['column_count'] or '?'} columns"
            for d in busiest]
    out += ["", "## Errors", "",
            f"- **{len(er)} codes** indexed with their throw site and branches.",
            f"- **{len(er) - len(unreach)} are reachable from a mapped API**; the remaining",
            f"  {len(unreach)} are thrown from batch writers, consumers and platform-lib —",
            "  reachable in production, just not via an orchestration entry point.",
            "- `kg_error <code>` returns the throw sites, the ExecutionContext keys the message",
            "  template needs, and prior fixes for ~160 tokens. Use it before grepping.", ""]

    posting = [g for g in gl if g["is_posting_rule"]]
    types = collections.Counter(g["txn_type"] for g in posting if g["txn_type"])
    half = [g for g in posting if g["half_defined"]]
    out += ["## GL posting rules", "",
            f"- **{len(posting)} posting rules** across **{len(types)} transaction types**"
            + (f" ({len(gl)-len(posting)} further `gl_rule` nodes are cross-check entries, "
               "not rules)." if len(gl) > len(posting) else "."),
            "  Each names its",
            "  leg sequence, `reference_code`, and the debit/credit placeholders that resolve",
            "  to internal accounts through `product_transaction_catalogue__placeholder__iad`.",
            (f"- **{len(half)} post a single side** — normal where the counter-leg comes from "
             "a fallback placeholder, but the first thing to check when a posting lands nowhere."
             if half else
             "- **Every rule names both a debit and a credit placeholder.** A rule with one "
             "side is the first thing to check when a posting lands nowhere; there are none."),
            "- `selected_by` names the processor whose `sets_txn_type` chooses the type, so a",
            "  GL question resolves in one hop instead of two searches.", "",
            "| Transaction type | rules |", "|---|---:|"]
    out += [f"| `{t}` | {n} |" for t, n in types.most_common(12)]

    shared = [p for p in pr if p["shared"]]
    writers = [p for p in pr if p["money_writer"]]
    hot = sorted(pr, key=lambda p: -p["flow_count"])[:12]
    out += ["", "## Processors", "",
            f"- **{len(pr)} processors**, {len(shared)} of them running in flows across more",
            "  than one repo. Editing a shared processor is a cross-service change whether or",
            "  not the diff says so.",
            f"- **{len(writers)} write to a table** — the set where `no-flow-break-impact-check`",
            "  and the money gates apply.",
            "- Most-reused, by number of distinct flows that invoke them:", "",
            "| Processor | flows | repos | writes |", "|---|---:|---:|---:|"]
    out += [f"| `{p['processor']}` | {p['flow_count']} | {len(p['spans_repos'])} | "
            f"{len(p['writes'])} |" for p in hot]
    out += ["",
            "`dummyProcessor` tops that list at 327 flows and is exactly what it sounds like —",
            "reuse count alone is not risk. Read the `writes` column beside it.", ""]
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--events", action="store_true")
    ap.add_argument("--schedules", action="store_true")
    ap.add_argument("--data", action="store_true")
    ap.add_argument("--errors", action="store_true")
    ap.add_argument("--gl", action="store_true")
    ap.add_argument("--processors", action="store_true")
    args = ap.parse_args()

    con = connect()
    ev, sc, da, er = events(con), schedules(con), data(con), errors(con)
    gl, pr = gl_rules(con), processors(con)
    con.close()

    picked = (args.events or args.schedules or args.data or args.errors or args.gl
              or args.processors)
    if picked:
        for flag, rows in ((args.events, ev), (args.schedules, sc),
                           (args.data, da), (args.errors, er), (args.gl, gl),
                           (args.processors, pr)):
            if flag:
                print(json.dumps(rows, indent=1))
        return 0

    write(EVENTS, "Kafka topics — producers, consumers. From the KG. Generated.", ev)
    write(SCHEDULES, "Schedulers — what runs unattended and what it triggers. Generated.", sc)
    write(DATA, "Tables — the APIs that write and read each one. Generated.", da)
    write(ERRORS, "Error codes — throw sites, branches, raising flows. Generated.", er)
    write(GLRULES, "GL posting rules — legs, placeholders, selecting processors. Generated.", gl)
    write(PROCESSORS, "Processors — the flows each one runs in, and what it touches. Generated.", pr)
    DOC.write_text(markdown(ev, sc, da, er, gl, pr), encoding="utf-8")

    print(f"platform surface mapped")
    print(f"  {len(ev):5} topics      ({sum(1 for e in ev if e['orphan'])} with no consumer)")
    print(f"  {len(sc):5} schedulers  ({sum(1 for s in sc if s['unmapped'])} trigger no named request)")
    print(f"  {len(da):5} tables      ({sum(1 for d in da if d['no_known_writer'])} with no API writer)")
    print(f"  {len(er):5} error codes ({sum(1 for e in er if e['unreachable_from_any_api'])} not reachable from an API)")
    posting = [g for g in gl if g['is_posting_rule']]
    print(f"  {len(posting):5} GL rules    ({len({g['txn_type'] for g in posting})} transaction types)")
    print(f"  {len(pr):5} processors  ({sum(1 for p in pr if p['shared'])} shared across repos)")
    for path in (EVENTS, SCHEDULES, DATA, ERRORS, GLRULES, PROCESSORS, DOC):
        print(f"  → {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
