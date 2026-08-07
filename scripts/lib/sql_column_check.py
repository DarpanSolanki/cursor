#!/usr/bin/env python3
"""Refuse a query that names a column the database does not have.

`schema_ref_gate.py` checks SQL that lives in files. Nothing checked the SQL an agent
types straight into `db-local.sh`, so a guessed column surfaced as a raw
`column "x" does not exist` after the round trip — or worse, as a wrong conclusion when
the typo sat in a WHERE clause and the query merely returned nothing.

Reads `cursor-bundle/schema/tables.jsonl` (live local DB, refreshed by schema-sync.sh).

  sql_column_check.py --sql "SELECT a.foo FROM mfi_accounting.account a"
  echo "<sql>" | sql_column_check.py

Exit 0 = every resolvable reference exists (or nothing was resolvable).
Exit 1 = at least one confident miss; the real column list is printed.

Only *confident* misses are reported: the alias must resolve to a table the oracle knows,
and the column must be absent from it. Anything ambiguous — CTEs, subquery aliases,
functions, unknown tables — is left alone, because a gate that cries wolf gets bypassed.
"""
from __future__ import annotations

import argparse
import difflib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
TABLES = ROOT / "cursor-bundle" / "schema" / "tables.jsonl"

DEFAULT_SCHEMA = "mfi_accounting"

_TABLE_REF = re.compile(
    r"\b(?:FROM|JOIN|UPDATE|INTO)\s+([a-z_][a-z0-9_]*)\.([a-z_][a-z0-9_]*)"
    r"(?:\s+(?:AS\s+)?([a-z_][a-z0-9_]*))?",
    re.I,
)
_BARE_TABLE_REF = re.compile(
    r"\b(?:FROM|JOIN|UPDATE|INTO)\s+([a-z_][a-z0-9_]*)"
    r"(?:\s+(?:AS\s+)?([a-z_][a-z0-9_]*))?",
    re.I,
)
_QUALIFIED = re.compile(r"\b([a-z_][a-z0-9_]*)\.([a-z_][a-z0-9_]*)\b", re.I)
_CTE = re.compile(r"\b([a-z_][a-z0-9_]*)\s+AS\s*\(", re.I)

_SQL_KEYWORDS = {
    "as", "on", "and", "or", "not", "in", "is", "null", "select", "from", "where",
    "join", "left", "right", "inner", "outer", "full", "cross", "group", "order",
    "by", "having", "limit", "offset", "union", "all", "distinct", "case", "when",
    "then", "else", "end", "asc", "desc", "with", "using", "lateral", "values",
}


def load_tables() -> dict[tuple[str, str], set[str]]:
    tables: dict[tuple[str, str], set[str]] = {}
    if not TABLES.exists():
        return tables
    for line in TABLES.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        tables[(row["schema"], row["table"])] = {c["name"] for c in row.get("columns") or []}
    return tables


def strip_noise(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    sql = re.sub(r"'(?:[^']|'')*'", " '' ", sql)
    return sql


def resolve_aliases(sql: str, tables: dict) -> tuple[dict[str, tuple[str, str]], set[str]]:
    """alias/table-name -> (schema, table). Second value: names we must not judge."""
    aliases: dict[str, tuple[str, str]] = {}
    opaque: set[str] = {m.group(1).lower() for m in _CTE.finditer(sql)}

    for m in _TABLE_REF.finditer(sql):
        schema, table, alias = m.group(1).lower(), m.group(2).lower(), m.group(3)
        key = (schema, table)
        if key not in tables:
            opaque.add(table)
            if alias:
                opaque.add(alias.lower())
            continue
        aliases[table] = key
        if alias and alias.lower() not in _SQL_KEYWORDS:
            aliases[alias.lower()] = key

    for m in _BARE_TABLE_REF.finditer(sql):
        name, alias = m.group(1).lower(), m.group(2)
        if "." in m.group(0):
            continue
        key = (DEFAULT_SCHEMA, name)
        if key in tables:
            aliases.setdefault(name, key)
            if alias and alias.lower() not in _SQL_KEYWORDS:
                aliases.setdefault(alias.lower(), key)
        else:
            opaque.add(name)
            if alias:
                opaque.add(alias.lower())

    for name in opaque:
        aliases.pop(name, None)
    return aliases, opaque


def check(sql: str, tables: dict | None = None) -> list[str]:
    tables = load_tables() if tables is None else tables
    if not tables:
        return []
    clean = strip_noise(sql)
    aliases, opaque = resolve_aliases(clean, tables)
    if not aliases:
        return []

    problems: list[str] = []
    seen: set[tuple[str, str]] = set()
    known_schemas = {s for s, _ in tables}

    for m in _QUALIFIED.finditer(clean):
        left, col = m.group(1).lower(), m.group(2).lower()
        if left in opaque or left in known_schemas or left in _SQL_KEYWORDS:
            continue
        if col in _SQL_KEYWORDS or col == "*":
            continue
        key = aliases.get(left)
        if not key:
            continue
        columns = tables[key]
        if col in columns:
            continue
        if (left, col) in seen:
            continue
        seen.add((left, col))
        near = difflib.get_close_matches(col, sorted(columns), n=4, cutoff=0.6)
        hint = f"  did you mean: {', '.join(near)}" if near else ""
        problems.append(
            f"{key[0]}.{key[1]} has no column '{col}' (referenced as {left}.{col}){hint}"
        )
    return problems


def referenced_tables(sql: str, tables: dict | None = None) -> list[tuple[str, str]]:
    """Every schema.table an alias in this SQL resolves to.

    Used to pre-flight a *remote* environment: the local oracle is not authority for QA,
    which may run a different train, so the caller queries that environment's own
    information_schema for exactly these tables and feeds it back via --catalog.
    """
    clean = strip_noise(sql)
    known = tables if tables is not None else load_tables()
    out: set[tuple[str, str]] = set()
    for m in _TABLE_REF.finditer(clean):
        out.add((m.group(1).lower(), m.group(2).lower()))
    for m in _BARE_TABLE_REF.finditer(clean):
        if "." in m.group(0):
            continue
        name = m.group(1).lower()
        if (DEFAULT_SCHEMA, name) in known or not known:
            out.add((DEFAULT_SCHEMA, name))
    return sorted(out)


def load_catalog(path: str) -> dict[tuple[str, str], set[str]]:
    """{"schema.table": ["col", ...]} as produced by a remote information_schema query."""
    raw = json.loads(pathlib.Path(path).read_text())
    out: dict[tuple[str, str], set[str]] = {}
    for key, cols in raw.items():
        schema, _, table = key.partition(".")
        out[(schema.lower(), table.lower())] = {c.lower() for c in cols}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sql")
    ap.add_argument("--list-tables", action="store_true",
                    help="print schema.table refs, one per line (for remote pre-flight)")
    ap.add_argument("--catalog",
                    help="JSON catalog to validate against instead of the local oracle")
    ap.add_argument("--label", default="the local database",
                    help="environment name used in the failure message")
    ap.add_argument("--escape", default="DB_LOCAL_SKIP_COLUMN_CHECK",
                    help="env var named in the escape hint")
    args = ap.parse_args()
    sql = args.sql if args.sql is not None else sys.stdin.read()

    if args.list_tables:
        for schema, table in referenced_tables(sql):
            print(f"{schema}.{table}")
        return 0

    if args.catalog:
        catalog = load_catalog(args.catalog)
        if not catalog:
            return 0
        problems = check(sql, tables=catalog)
    else:
        problems = check(sql)
    if not problems:
        return 0
    print(f"column check FAILED — {args.label} does not have these:", file=sys.stderr)
    for p in problems:
        print(f"  {p}", file=sys.stderr)
    print("\n  Columns are listed by: python3 cursor-bundle/kg/bin/kg.py schema <table>", file=sys.stderr)
    print("  If the DB is behind the code: python3 scripts/lib/schema_live_drift.py", file=sys.stderr)
    print(f"  To run anyway: {args.escape}=1", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
