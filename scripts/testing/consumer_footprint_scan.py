#!/usr/bin/env python3
"""Recover a Kafka consumer's table footprint statically, past the message-broker boundary.

The knowledge graph models `consumer:<bean>` only as `topic -> consumes -> consumer`. It has
no `writes`/`reads` edge from any consumer node, so every table a consumer persists is either
absent from `kg writes` or — worse — answered with the API/batch writers of that table, none of
which is the consumer. GAP-098 measured 3/12 correctly attributed, 4 tables with zero writers
and 7 misattributed.

Three consumer shapes; only two are the gap:

  1  Consumer -> ServiceOrchestrator.executeProcessors / callInternalAPI("<request>")
     Already correct: the KG edge is keyed on the Request name, not the caller. SKIPPED.
  2  Consumer -> Processor.execute() directly, bypassing the orchestrator.
  3  Consumer -> Service/DAO/Repository .save()/.saveAll()/.update*() directly.

The wiring is convention, so it is walkable:

  deploy/application/messagebroker/MessageBroker.xml   <bean> -> @Component("<bean>") class
  computeRecords(records, tenant)                      the single entry point
  @Autowired field types                               the outward hops
  write-verb call on a *DAOService/*Repository/*Service -> entity @Table   (the write)

    consumer_footprint_scan.py                  scan every repo, print the pattern split
    consumer_footprint_scan.py --repo los       one repo
    consumer_footprint_scan.py --bean NAME      one consumer, with per-table evidence
    consumer_footprint_scan.py --curated-preview   the edges emission would write
    consumer_footprint_scan.py --registry-drift    XML vs .cursor/event-registry.md
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[2]


def rel_to_root(path: pathlib.Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


SCRATCH = ROOT / "scripts" / "scratch" / "consumer-scan"
KG_DB = ROOT / "cursor-bundle" / "kg" / "data" / "kg.db"
EVENT_REGISTRY = ROOT / ".cursor" / "event-registry.md"

sys.path.insert(0, str(ROOT / "scripts" / "testing"))
from batch_footprint_scan import _SHARED_BEANS, dao_to_entity, entity_tables

PATTERN_ORCHESTRATED = "orchestrated"
PATTERN_PROCESSOR = "processor_direct"
PATTERN_DAO = "dao_direct"
PATTERN_NONE = "no_write_found"

# LOS is out of testing scope by user direction 2026-08-08; its 68 edges are the largest
# block but none of them write an accounting table.
OUT_OF_SCOPE_REPOS = {"trustt-platform-los"}


def classify_pattern(events, writes):
    """A consumer that also writes directly is not `orchestrated`, whatever it did first.

    Taking `events[0]` discarded three consumers whose walk happened to reach a
    `callInternalAPI` before their own `saveAll` — a silent under-count, not a wrong edge.
    Orchestrated is the skip verdict, so it may only stand when nothing was written directly.
    """
    if not events:
        return PATTERN_NONE
    if writes:
        for event in events:
            if event["kind"] in (PATTERN_DAO, PATTERN_PROCESSOR):
                return event["kind"]
    return events[0]["kind"]

_COMPONENT = re.compile(r'@Component\s*\(\s*"([^"]+)"\s*\)')
_FIELD = re.compile(r"(?:^|[;{}])\s*(?:@\w+(?:\([^)]*\))?\s*)*"
                    r"(?:private|protected|public)?\s*(?:static\s+)?(?:final\s+)?"
                    r"([A-Z]\w*)(?:<[^;=()]*>)?\s+(\w+)\s*[;=]", re.M)
_CALL = re.compile(r"\b(\w+)\s*\.\s*(\w+)\s*\(")
_BARE_CALL = re.compile(r"(?<![\w.])(\w+)\s*\(")
_ORCHESTRATED = re.compile(r"\b(?:executeProcessors|callInternalAPI)\s*\(")

_WRITE_VERB = re.compile(r"^(save\w*|persist\w*|insert\w*|update\w*|upsert\w*|merge\w*"
                         r"|batchUpdate\w*|bulkUpdate\w*)$")
_DELETE_VERB = re.compile(r"^(delete\w*|softDelete\w*|remove\w*)$")
_DECL_TAIL = re.compile(r"\s*(?:throws\s+[\w\s,.]+)?\s*")
_DECL_HEAD = re.compile(r"(?:[\w>\]]|\)|@\w+)\s+$|^\s*$")
_MODIFYING = re.compile(r"@Modifying")
_PROCESSOR_CLASS = re.compile(r"@Processor\b|extends\s+AbstractProcessor")
_SQL_WRITE = re.compile(r"\b(?:update|insert\s+into|delete\s+from)\s+([a-z_][a-z0-9_.]*)", re.I)
_DAO_SUFFIX = ("DAOService", "DaoService", "Repository", "Service")
_PERSISTENCE_TYPES = {"EntityManager"}
_JAVA_BUILTINS = {"Map", "List", "Set", "String", "Optional", "Collection", "Queue",
                  "StringBuilder", "Iterator", "ObjectMapper", "HashMap", "ArrayList"}
_PROCESSOR_ENTRY = {"execute", "process", "processSynchronously"}
_MAX_DEPTH = 6


def repos_with_consumers() -> dict[str, list[pathlib.Path]]:
    out: dict[str, list[pathlib.Path]] = {}
    for xml in sorted(ROOT.glob("trustt-platform-*/deploy/application/**/MessageBroker.xml")):
        if "<bean>" not in xml.read_text(encoding="utf-8", errors="replace"):
            continue
        out.setdefault(xml.relative_to(ROOT).parts[0], []).append(xml)
    return out


def parse_consumers(xml_paths: list[pathlib.Path]) -> list[dict]:
    rows: list[dict] = []
    for xml in xml_paths:
        try:
            root = ET.fromstring(xml.read_text(encoding="utf-8", errors="replace"))
        except ET.ParseError:
            continue
        for node in root.findall("Consumer"):
            bean = (node.findtext("bean") or "").strip()
            if not bean:
                continue
            rows.append({
                "bean": bean,
                "topic_prefix": (node.findtext("topicPrefix") or "").strip(),
                "group_prefix": (node.findtext("consumersGroupIdPrefix") or "").strip(),
                "xml": rel_to_root(xml),
            })
    return rows


def class_index(java_root: pathlib.Path) -> dict[str, pathlib.Path]:
    out: dict[str, pathlib.Path] = {}
    for path in java_root.rglob("*.java"):
        out.setdefault(path.stem, path)
    return out


def bean_index(java_root: pathlib.Path) -> dict[str, pathlib.Path]:
    out: dict[str, pathlib.Path] = {}
    for path in java_root.rglob("*.java"):
        stem = path.stem
        out.setdefault(stem[0].lower() + stem[1:], path)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for name in _COMPONENT.findall(text):
            out[name] = path
    return out


_ENTITY_NAME = re.compile(r'@Entity\s*\(\s*name\s*=\s*"([a-z][a-z0-9_]*)"')


def table_map(java_root: pathlib.Path) -> dict[str, str]:
    out = entity_tables(java_root)
    for path in java_root.rglob("*.java"):
        if path.stem in out:
            continue
        m = _ENTITY_NAME.search(path.read_text(encoding="utf-8", errors="replace"))
        if m:
            out[path.stem] = m.group(1)
    return out


def dao_entities(java_root: pathlib.Path, tables: dict[str, str]) -> dict[str, str]:
    out = dict(dao_to_entity(java_root))
    known = set(tables)
    for path in java_root.rglob("*.java"):
        stem = path.stem
        if stem in out or not stem.endswith(_DAO_SUFFIX):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        names = {n for n in re.findall(r"\b([A-Z]\w*)\b", text) if n in known and n != stem}
        if not names:
            continue
        base = stem
        for suffix in _DAO_SUFFIX:
            base = base.replace(suffix, "")
        base = base.lower()
        exact = sorted(n for n in names if n.lower().removesuffix("entity") == base)
        if exact:
            out[stem] = exact[0]
        elif len(names) == 1:
            out[stem] = next(iter(names))
    return out


def field_types(text: str) -> dict[str, str]:
    return {name: typ for typ, name in _FIELD.findall(text)}


def method_bodies(text: str, name: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for m in re.finditer(r"\b" + re.escape(name) + r"\s*\(", text):
        idx = text.find(")", m.end() - 1)
        depth = 1
        i = m.end()
        while i < len(text) and depth:
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
                idx = i
            i += 1
        brace = text.find("{", idx)
        semi = text.find(";", idx)
        if brace < 0 or (0 <= semi < brace):
            continue
        if not _DECL_TAIL.fullmatch(text[idx + 1:brace]):
            continue
        head = text[max(0, m.start() - 60):m.start()]
        if head.rstrip().endswith((".", "=", "(", ",", "&", "|", "!", "return", "new")):
            continue
        if not _DECL_HEAD.search(head):
            continue
        depth = 0
        j = brace
        while j < len(text):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out.append((brace + 1, text[brace + 1:j]))
    return out


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


class Walker:
    def __init__(self, java_root: pathlib.Path, index: dict[str, pathlib.Path],
                 tables: dict[str, str], daos: dict[str, str]):
        self.root = java_root
        self.index = index
        self.tables = tables
        self.daos = daos
        self.cache: dict[pathlib.Path, str] = {}

    def read(self, path: pathlib.Path) -> str:
        if path not in self.cache:
            self.cache[path] = path.read_text(encoding="utf-8", errors="replace")
        return self.cache[path]

    def is_processor(self, typ: str) -> bool:
        path = self.index.get(typ)
        if path is None:
            return False
        text = self.read(path)
        return bool(_PROCESSOR_CLASS.search(text))

    def modifying_query(self, path: pathlib.Path, method: str) -> tuple[str, str] | None:
        text = self.read(path)
        for m in re.finditer(r"\b" + re.escape(method) + r"\s*\([^;{]*\)\s*;", text):
            head = text[max(0, m.start() - 600):m.start()]
            block = head.rsplit(";", 1)[-1]
            if not _MODIFYING.search(block):
                continue
            sql = _SQL_WRITE.search(block)
            if not sql:
                continue
            verb = "deletes" if block.lower().find("delete from") >= 0 else "writes"
            return verb, sql.group(1).split(".")[-1]
        return None

    def walk(self, path: pathlib.Path, method: str, depth: int, seen: set,
             events: list, writes: dict, unresolved: list) -> None:
        key = (path.stem, method)
        if depth > _MAX_DEPTH or key in seen:
            return
        seen.add(key)
        text = self.read(path)
        fields = field_types(text)
        rel = rel_to_root(path)
        for start, body in method_bodies(text, method):
            if _ORCHESTRATED.search(body):
                m = _ORCHESTRATED.search(body)
                events.append({"kind": PATTERN_ORCHESTRATED, "depth": depth,
                               "at": f"{rel}:{line_of(text, start + m.start())}"})
            for call in _CALL.finditer(body):
                field, meth = call.group(1), call.group(2)
                typ = fields.get(field)
                at = f"{rel}:{line_of(text, start + call.start())}"
                if typ is None:
                    continue
                if meth in _PROCESSOR_ENTRY and self.is_processor(typ):
                    events.append({"kind": PATTERN_PROCESSOR, "depth": depth, "at": at,
                                   "target": typ})
                    for entry in sorted(_PROCESSOR_ENTRY):
                        self.walk(self.index[typ], entry, depth + 1, seen, events, writes,
                                  unresolved)
                    continue
                verb = ("writes" if _WRITE_VERB.match(meth)
                        else "deletes" if _DELETE_VERB.match(meth) else None)
                if verb and (typ.endswith(_DAO_SUFFIX) or typ in _PERSISTENCE_TYPES):
                    owner = path.stem if typ in _PERSISTENCE_TYPES else typ
                    entity = self.daos.get(owner)
                    table = self.tables.get(entity or "")
                    if table:
                        events.append({"kind": PATTERN_DAO, "depth": depth, "at": at,
                                       "target": f"{typ}.{meth}"})
                        writes.setdefault((table, verb),
                                          f"{at} -> {owner}.{meth} -> {entity} (hop {depth})")
                        continue
                target = self.index.get(typ)
                if target is None or typ.endswith("Entity"):
                    if verb and typ not in _JAVA_BUILTINS:
                        unresolved.append(f"{at} -> {typ}.{meth} (entity not resolvable)")
                    continue
                modifying = self.modifying_query(target, meth)
                if modifying:
                    verb, table = modifying
                    if table in self.tables.values():
                        events.append({"kind": PATTERN_DAO, "depth": depth, "at": at,
                                       "target": f"{typ}.{meth}"})
                        writes.setdefault((table, verb),
                                          f"{at} -> {typ}.{meth} -> @Modifying {verb} (hop {depth})")
                    else:
                        unresolved.append(f"{at} -> {typ}.{meth} (@Modifying table {table} "
                                          "not an @Table in this repo)")
                    continue
                self.walk(target, meth, depth + 1, seen, events, writes, unresolved)
            for call in _BARE_CALL.finditer(body):
                name = call.group(1)
                if name in ("if", "for", "while", "switch", "catch", "return", "new"):
                    continue
                if method_bodies(text, name) and name != method:
                    self.walk(path, name, depth + 1, seen, events, writes, unresolved)


def scan_repo(repo: str, xml_paths: list[pathlib.Path]) -> list[dict]:
    java_root = ROOT / repo / "src" / "main" / "java"
    if not java_root.is_dir():
        return []
    index = class_index(java_root)
    beans = bean_index(java_root)
    tables = table_map(java_root)
    daos = dao_entities(java_root, tables)
    walker = Walker(java_root, index, tables, daos)

    by_bean: dict[str, dict] = {}
    for row in parse_consumers(xml_paths):
        bucket = by_bean.setdefault(row["bean"], {
            "bean": row["bean"], "repo": repo, "topics": [], "groups": [], "xmls": set(),
        })
        if row["topic_prefix"]:
            bucket["topics"].append(row["topic_prefix"])
        if row["group_prefix"]:
            bucket["groups"].append(row["group_prefix"])
        bucket["xmls"].add(row["xml"])

    rows: list[dict] = []
    for bean, row in sorted(by_bean.items()):
        path = beans.get(bean)
        row["topic_count"] = len(row["topics"])
        row["topics"] = sorted(set(row["topics"]))
        row["groups"] = sorted(set(row["groups"]))
        row["xmls"] = sorted(row["xmls"])
        if path is None:
            row.update({"class": None, "pattern": "unresolved_bean", "events": [],
                        "tables_written": [], "evidence": {}, "unresolved": []})
            rows.append(row)
            continue
        events: list = []
        writes: dict = {}
        unresolved: list = []
        walker.walk(path, "computeRecords", 0, set(), events, writes, unresolved)
        row["class"] = str(path.relative_to(ROOT))
        row["pattern"] = classify_pattern(events, writes)
        row["events"] = events[:12]
        row["tables_written"] = sorted({t for t, r in writes if r == "writes"})
        row["tables_deleted"] = sorted({t for t, r in writes if r == "deletes"})
        row["evidence"] = {f"{t}:{r}": why for (t, r), why in sorted(writes.items())}
        row["unresolved"] = sorted(set(unresolved))
        rows.append(row)
    return rows


def scan_all(repo_filter: str | None = None) -> list[dict]:
    rows: list[dict] = []
    for repo, xmls in sorted(repos_with_consumers().items()):
        if repo_filter and repo != repo_filter:
            continue
        rows.extend(scan_repo(repo, xmls))
    return rows


def kg_state() -> tuple[set[str], set[str], set[tuple[str, str, str]]]:
    import sqlite3
    if not KG_DB.is_file():
        return set(), set(), set()
    con = sqlite3.connect(f"file:{KG_DB}?mode=ro", uri=True)
    nodes = {r[0] for r in con.execute("SELECT id FROM nodes")}
    consumers = {n.split(":", 1)[1] for n in nodes if n.startswith("consumer:")}
    edges = {(f, t, r) for f, t, r in con.execute(
        "SELECT src_id, dst_id, rel FROM edges WHERE src_id LIKE 'consumer:%'")}
    con.close()
    return nodes, consumers, edges


def curated_lines(rows: list[dict]) -> tuple[list[str], list[tuple[str, str]]]:
    nodes, _, edges = kg_state()
    lines: list[str] = []
    skipped: list[tuple[str, str]] = []
    emitted: set[tuple[str, str, str]] = set()
    for row in rows:
        if row["pattern"] in (PATTERN_ORCHESTRATED, "unresolved_bean", PATTERN_NONE):
            skipped.append((row["bean"], row["pattern"]))
            continue
        if row["bean"] in _SHARED_BEANS:
            skipped.append((row["bean"], "shared bean"))
            continue
        src = f"consumer:{row['bean']}"
        if nodes and src not in nodes:
            skipped.append((row["bean"], "no consumer node in the KG"))
            continue
        for rel, tables in (("writes", row["tables_written"]),
                            ("deletes", row.get("tables_deleted", []))):
            for table in tables:
                dst = f"table:{table}"
                if nodes and dst not in nodes:
                    skipped.append((row["bean"], f"no table node: {table}"))
                    continue
                key = (src, dst, rel)
                if key in edges or key in emitted:
                    continue
                emitted.add(key)
                lines.append(json.dumps({
                    "t": "edge", "from": src, "to": dst, "rel": rel,
                    "note": f"consumer-footprint scan ({row['pattern']}): "
                            f"{row['class']} — past the message-broker boundary, which the "
                            "orchestration index cannot follow",
                    "src": "scripts/testing/consumer_footprint_scan.py",
                }))
    return lines, skipped


def registry_drift(rows: list[dict]) -> dict[str, list[str]]:
    text = EVENT_REGISTRY.read_text(encoding="utf-8") if EVENT_REGISTRY.is_file() else ""
    named = {n for n in re.findall(r"\b([A-Za-z]\w*Consumer)\b", text) if n != "Consumer"}
    scanned = {pathlib.Path(r["class"]).stem for r in rows if r.get("class")}
    beans = {r["bean"] for r in rows}
    topics = {t for r in rows for t in r["topics"]}
    return {
        "class_in_xml_not_in_registry": sorted(scanned - named),
        "class_in_registry_not_in_xml": sorted(n for n in named - scanned
                                                if n[0].lower() + n[1:] not in beans),
        "topic_prefix_in_xml_not_in_registry": sorted(t for t in topics if t not in text),
        "unresolved_bean": sorted(r["bean"] for r in rows if not r.get("class")),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo")
    ap.add_argument("--bean")
    ap.add_argument("--curated-preview", action="store_true")
    ap.add_argument("--emit-curated", action="store_true")
    ap.add_argument("--include-out-of-scope", action="store_true")
    ap.add_argument("--registry-drift", action="store_true")
    args = ap.parse_args()

    rows = scan_all(args.repo)

    if args.bean:
        row = next((r for r in rows if r["bean"] == args.bean), None)
        if row is None:
            print(f"no consumer bean named {args.bean}")
            return 1
        print(json.dumps(row, indent=1))
        return 0

    if args.registry_drift:
        print(json.dumps(registry_drift(rows), indent=1))
        return 0

    SCRATCH.mkdir(parents=True, exist_ok=True)
    out_path = SCRATCH / "consumer_footprint.jsonl"
    with out_path.open("w", encoding="utf-8") as fh:
        fh.write("# Kafka consumer table footprint, scanned past the message-broker boundary.\n")
        for row in rows:
            fh.write(json.dumps(row) + "\n")

    if not args.include_out_of_scope:
        rows = [r for r in rows if r["repo"] not in OUT_OF_SCOPE_REPOS]

    lines, skipped = curated_lines(rows)

    if args.emit_curated:
        target = ROOT / "cursor-bundle" / "kg" / "curated" / "consumer_footprint.jsonl"
        existing = target.read_text(encoding="utf-8").splitlines() if target.is_file() else []
        seen = {l for l in existing if l.strip() and not l.startswith("#")}
        fresh = [l for l in lines if l not in seen]
        with target.open("a", encoding="utf-8") as fh:
            for line in fresh:
                fh.write(line + "\n")
        print(f"emitted {len(fresh)} new edge(s) ({len(lines) - len(fresh)} already present) "
              f"-> {target.relative_to(ROOT)}")
        return 0

    if args.curated_preview:
        preview = SCRATCH / "consumer_curated_preview.jsonl"
        preview.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"curated preview: {len(lines)} edge(s) -> {preview.relative_to(ROOT)} "
              "(not written into the KG)")
        for bean, why in skipped:
            print(f"    skipped {bean:44} {why}")
        return 0

    print(f"consumer footprint: {len(rows)} bean(s) across "
          f"{len({r['repo'] for r in rows})} repo(s)")
    print(f"{'bean':44}{'repo':32}{'pattern':18}{'topics':>7}{'tables':>7}")
    for row in rows:
        print(f"{row['bean'][:42]:44}{row['repo'].replace('trustt-platform-', '')[:30]:32}"
              f"{row['pattern']:18}{row['topic_count']:>7}{len(row['tables_written']):>7}")
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["pattern"]] = counts.get(row["pattern"], 0) + 1
    print("\npattern split: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print(f"{len(lines)} edge(s) would be emitted  ->  {out_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
