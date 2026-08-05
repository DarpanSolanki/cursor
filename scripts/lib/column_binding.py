#!/usr/bin/env python3
"""Bind every schema column to the Java that reads and writes it, per service.

Knowing a column exists is not knowing what it does. For a config column the
semantics ARE its readers: `loan_product.prepayment_allowed` means whatever the
validators that read it enforce — it throws 134144 when false.

Two accuracy rules this file exists to keep:

- **Per-repo accessor index.** `getAmount()` exists in accounting, los and payments.
  One shared index would bind a los reader to an accounting column. Each repo is
  indexed against its own sources only.
- **Schema-qualified keys.** 18 table names live in more than one schema and 6 of
  those carry different columns, so a `table.column` key is ambiguous. Keys are
  `schema.table.column`, with the schema derived from the owning repo.

Entities carry no `@Column(name=…)` — they rely on the implicit
CamelCaseToUnderscores naming strategy. Explicit `@Column` / `@JoinColumn` win.

  column_binding.py --rebuild [--repos a,b]
  column_binding.py loan_product.prepayment_allowed
  column_binding.py --coverage
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

import schema_oracle  # noqa: E402

OUT = ROOT / "cursor-bundle" / "schema" / "bindings.jsonl"
MAP = ROOT / "cursor-bundle" / "schema" / "service-map.json"
MAX_CALLERS = 12

REPO_SCHEMA = {
    "trustt-platform-accounting": "mfi_accounting",
    "trustt-platform-actor": "mfi_actor",
    "trustt-platform-los": "mfi_los",
    "trustt-platform-payments": "mfi_payments",
    "trustt-platform-task": "mfi_task",
    "trustt-platform-masterdata-management": "mfi_masterdata",
    "trustt-platform-batch": "mfi_batch",
    "trustt-platform-notifications": "mfi_notifications",
    "trustt-platform-audit": "mfi_audit",
    "trustt-platform-authorization": "mfi_authorization",
    "trustt-platform-approval": "mfi_approval",
    "trustt-platform-reporting": "mfi_reporting",
    "trustt-platform-api-gateway": "mfi_gateway",
    "trustt-platform-dms": "mfi_dms",
    # platform-lib owns platform_master (tenant/service/api master, read by
    # infra-platform and infra-batch) but its entities also write tables in OTHER
    # schemas — hierarchy-builder writes mfi_actor. The hint is a preference, not
    # an assumption: every entity resolves its own schema from the oracle.
    "trustt-platform-lib": "platform_master",
}

TABLE_RE = re.compile(r'@Table\s*\(\s*name\s*=\s*"((?:[^"\\]|\\.)+)"')
COLUMN_RE = re.compile(r'@(?:Join)?Column\s*\([^)]*name\s*=\s*"([^"]+)"')
FIELD_RE = re.compile(r"^\s*(?:private|protected|public)\s+(?:final\s+)?([\w<>,\[\]\. ]+?)\s+(\w+)\s*(?:=|;)")
ACCESSOR_RE = re.compile(r"(\w+)\s*\.\s*(get|is|set)([A-Z]\w*)\s*\(")
TRANSIENT_RE = re.compile(r"@Transient")
GUARD_RE = re.compile(r'NovopayFatalException\s*\(\s*"(\d+)"')
GUARD_LINES = 5


def snake(name: str) -> str:
    out = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    out = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", out)
    return out.lower()


def _java_files(repo: str) -> list[Path]:
    base = ROOT / repo
    if not base.is_dir():
        return []
    src = base / "src" / "main" / "java"
    if src.is_dir():
        return sorted(src.rglob("*.java"))
    return sorted(p for p in base.rglob("src/main/java/**/*.java"))


def resolve_schema(table: str, hint: str | None) -> tuple[str | None, str]:
    """Which schema does this entity's table actually live in?

    A repo does not imply a schema. `hierarchy-builder` lives in platform-lib and
    writes `mfi_actor.hierarchy_element`; `Sequence` maps `sequences`, which exists
    in 17 schemas. Assuming repo == schema attributed lib's tables to the wrong
    place and hid it from the map entirely.
    """
    tables = schema_oracle.load()
    if hint and (hint, table) in tables:
        return hint, "repo"
    candidates = schema_oracle.schemas_for(table)
    if len(candidates) == 1:
        return candidates[0], "oracle"
    if candidates:
        for preferred in ([hint] if hint else []) + schema_oracle.SCHEMA_PREFERENCE:
            if preferred in candidates:
                return preferred, "oracle"
        return candidates[0], "oracle"
    return None, "absent"


def parse_entities(files: list[Path], schema: str, repo: str) -> list[dict]:
    rows: list[dict] = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        match = TABLE_RE.search(text)
        if not match:
            continue
        # `@Table(name="\"user\"")` — reserved words are mapped as quoted
        # identifiers, so the escapes are part of the annotation, not the name.
        table = match.group(1).replace('\\"', '"').strip('"')
        entity = path.stem
        pending_col: str | None = None
        skip_next = False
        for line in text.splitlines():
            if TRANSIENT_RE.search(line):
                skip_next = True
                continue
            col_match = COLUMN_RE.search(line)
            if col_match:
                pending_col = col_match.group(1)
                continue
            field = FIELD_RE.match(line)
            if not field:
                continue
            java_type, name = field.group(1).strip(), field.group(2)
            if skip_next:
                skip_next = False
                pending_col = None
                continue
            if java_type.startswith(("List", "Set", "Map", "Collection")):
                pending_col = None
                continue
            rows.append(
                {
                    "schema": schema,
                    "repo": repo,
                    "table": table,
                    "column": pending_col or snake(name),
                    "entity": entity,
                    "field": name,
                    "java_type": java_type,
                    "source": str(path.relative_to(ROOT)),
                }
            )
            pending_col = None
    return rows


def accessor_index(files: list[Path]) -> tuple[dict[tuple[str, str], set[str]], dict[str, set[str]]]:
    """(kind, Field) -> classes touching it, plus Field -> error codes it gates.

    A guard is only recorded when the read sits in a CONDITION and a throw follows
    within a few lines. Scanning a flat character window instead attributed nine
    unrelated error codes to `status`, because `getStatus()` appears near a throw
    all over the codebase without gating it.
    """
    index: dict[tuple[str, str], set[tuple[str, str]]] = {}
    guards: dict[str, set[tuple[str, str]]] = {}
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        cls = path.stem
        lines = text.splitlines()
        for match in ACCESSOR_RE.finditer(text):
            receiver, kind, field = match.group(1), match.group(2), match.group(3)
            index.setdefault(("set" if kind == "set" else "get", field), set()).add(
                (cls, receiver.lower())
            )
            if kind == "set":
                continue
            line_no = text.count("\n", 0, match.start())
            line = lines[line_no] if line_no < len(lines) else ""
            if not re.search(r"\b(if|while)\s*\(|\|\||&&|[!=]=|\breturn\b", line):
                continue
            window = "\n".join(lines[line_no : line_no + GUARD_LINES])
            for code in GUARD_RE.findall(window):
                guards.setdefault(field, set()).add((code, receiver.lower()))
    return index, guards


def _stem(entity: str) -> str:
    return re.sub(r"(entity|vo|dto)$", "", entity.lower())


def _receiver_matches(entity: str, receiver: str) -> bool:
    """`loanProductEntity.isPrepaymentAllowed()` belongs to LoanProductEntity.

    Only consulted when a field name is declared by more than one entity in the
    repo — otherwise every entity with a `status` field inherits every
    `getStatus()` caller in the service.
    """
    stem = _stem(entity)
    return bool(stem) and (stem in receiver or receiver.replace("_", "") in stem)


def _filter_callers(
    callers: set[tuple[str, str]], entity: str, ambiguous: bool
) -> list[str]:
    if not ambiguous:
        return sorted({cls for cls, _ in callers} - {entity})
    return sorted(
        {cls for cls, receiver in callers if _receiver_matches(entity, receiver)} - {entity}
    )


def query_index(files: list[Path]) -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    for path in files:
        if "repository" not in str(path).lower():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "@Query" not in text:
            continue
        for token in set(re.findall(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b", text)):
            index.setdefault(token, set()).add(path.stem)
    return index


def rebuild(repos: list[str]) -> dict:
    lines: list[str] = []
    per_service: dict[str, dict] = {}

    for repo in repos:
        schema = REPO_SCHEMA.get(repo)
        files = _java_files(repo)
        if not schema or not files:
            continue
        entities = parse_entities(files, schema, repo)
        accessors, guards = accessor_index(files)
        queries = query_index(files)

        field_owners: dict[str, set[str]] = {}
        for row in entities:
            field_owners.setdefault(row["field"], set()).add(row["entity"])

        bound = 0
        ambiguous_fields = 0
        unknown_tables: set[str] = set()
        schemas_touched: set[str] = set()
        emitted: list[dict] = []
        for row in entities:
            resolved, how = resolve_schema(row["table"], schema)
            if resolved is None:
                unknown_tables.add(row["table"])
                continue
            row["schema"] = resolved
            if how == "oracle" and resolved != schema:
                row["schema_from"] = "oracle"
            schemas_touched.add(resolved)
            emitted.append(row)
        entities = emitted
        for row in entities:
            cap = row["field"][:1].upper() + row["field"][1:]
            ambiguous = len(field_owners.get(row["field"], ())) > 1
            ambiguous_fields += 1 if ambiguous else 0
            readers = _filter_callers(accessors.get(("get", cap), set()), row["entity"], ambiguous)
            writers = _filter_callers(accessors.get(("set", cap), set()), row["entity"], ambiguous)
            row["readers"] = readers[:MAX_CALLERS]
            row["writers"] = writers[:MAX_CALLERS]
            if len(readers) > MAX_CALLERS:
                row["readers_total"] = len(readers)
            if len(writers) > MAX_CALLERS:
                row["writers_total"] = len(writers)
            row["queries"] = sorted(queries.get(row["column"], set()))
            if ambiguous:
                row["ambiguous_field"] = True
            row["guards"] = sorted(
                {
                    code
                    for code, receiver in guards.get(cap, set())
                    if not ambiguous or _receiver_matches(row["entity"], receiver)
                }
            )
            if readers or writers or row["queries"]:
                bound += 1
            lines.append(json.dumps(row, separators=(",", ":")))

        primary_tables = schema_oracle.schemas_and_tables(schema)
        mapped_tables = {r["table"] for r in entities}
        per_service[repo] = {
            "schema": schema,
            "schemas_touched": sorted(schemas_touched),
            "java_files": len(files),
            "entities": len({r["entity"] for r in entities}),
            "tables_in_db": len(primary_tables),
            "tables_mapped_by_an_entity": len(mapped_tables & primary_tables),
            "columns_mapped": len(entities),
            "columns_with_code_binding": bound,
            "columns_with_ambiguous_field_name": ambiguous_fields,
            "entity_tables_absent_from_db": sorted(unknown_tables)[:20],
            "entity_tables_absent_count": len(unknown_tables),
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    MAP.write_text(
        json.dumps(
            {
                "note": "Per-service map. `tables_in_db` counts the live local schema; "
                "`entity_tables_absent_from_db` are entities whose table is not in that schema "
                "on this checkout — a train or naming signal, not automatically a defect.",
                "services": per_service,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "repos": len(per_service),
        "columns": len(lines),
        "services": per_service,
    }


_CACHE: dict[str, dict] | None = None


def load() -> dict[str, dict]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    out: dict[str, dict] = {}
    if OUT.is_file():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                out[f"{row['schema']}.{row['table']}.{row['column']}"] = row
    _CACHE = out
    return out


def _key(ref: str) -> str | None:
    parts = ref.split(".")
    if len(parts) < 2:
        return None
    column = parts[-1]
    schema, table, _ = schema_oracle.resolve(".".join(parts[:-1]))
    return f"{schema}.{table}.{column}" if schema else None


def describe(ref: str) -> str:
    if not OUT.is_file():
        return "no bindings yet — run `bash scripts/bin/schema-sync.sh --bindings` (~1s)"
    key = _key(ref)
    row = load().get(key) if key else None
    if not row:
        return f"no code binding for {ref}"
    out = [
        key,
        f"  service  {row['repo']}",
        f"  entity   {row['entity']}.{row['field']} ({row['java_type']})",
        f"  source   {row['source']}",
    ]
    if row.get("guards"):
        out.append(f"  gates    error codes {', '.join(row['guards'])} when the check fails")
    for key_name in ("readers", "writers", "queries"):
        vals = row.get(key_name) or []
        if vals:
            total = row.get(f"{key_name}_total", len(vals))
            more = f" … +{total - 10}" if total > 10 else ""
            out.append(f"  {key_name:8s} {', '.join(vals[:10])}{more}")
    if not (row.get("readers") or row.get("writers") or row.get("queries")):
        out.append("  readers  NONE — no code reads this column on this checkout")
    if row.get("ambiguous_field"):
        out.append(
            f"  note     `{row['field']}` is declared by several entities in this service; "
            "callers are receiver-matched, so this list favours precision and may be incomplete"
        )
    return "\n".join(out)


def coverage() -> str:
    if not MAP.is_file():
        return "no service map — run --rebuild"
    data = json.loads(MAP.read_text(encoding="utf-8"))
    head = f"{'service':40s} {'schema':18s} {'tables':>12s} {'cols':>7s} {'bound':>7s}"
    out = [head, "-" * len(head)]
    for repo, m in sorted(data["services"].items()):
        out.append(
            f"{repo:40s} {m['schema']:18s} "
            f"{m['tables_mapped_by_an_entity']:>5}/{m['tables_in_db']:<6} "
            f"{m['columns_mapped']:>7} {m['columns_with_code_binding']:>7}"
        )
    return "\n".join(out)


def main(argv: list[str]) -> int:
    if "--coverage" in argv:
        print(coverage())
        return 0
    if "--rebuild" in argv:
        repos = list(REPO_SCHEMA)
        if "--repos" in argv:
            repos = argv[argv.index("--repos") + 1].split(",")
        meta = rebuild(repos)
        print(f"column bindings: {meta['columns']} columns across {meta['repos']} services")
        print(coverage())
        return 0
    if not argv:
        print("usage: column_binding.py --rebuild [--repos a,b] | --coverage | <table>.<column>")
        return 0
    print(describe(argv[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
