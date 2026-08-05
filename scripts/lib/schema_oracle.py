#!/usr/bin/env python3
"""Structural truth for every service schema, generated from the live local DB.

Agents were reasoning about columns from code and memory, so asserts referenced
columns that do not exist — `loan_account_payments_details.is_deleted` sat in two
money-tier registry cases while that table has no soft-delete column at all.

This module is the oracle those references are checked against: one JSON line per
table, diffable in git, refreshed from `information_schema`. It records what the
LOCAL fixture holds. The local DB is not production truth (see
`.cursor/rules/40-knowledge-upkeep.md`) — `train_note` carries that caveat, and
absence here means "not on this checkout", never "does not exist".

  schema_oracle.py --rebuild          regenerate from localhost:5433
  schema_oracle.py loan_product       describe a table
  schema_oracle.py loan_product.prepayment_allowed
"""
from __future__ import annotations

import csv
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "cursor-bundle" / "schema"
TABLES = OUT_DIR / "tables.jsonl"
META = OUT_DIR / "meta.json"
DB_LOCAL = ROOT / "scripts" / "db-local.sh"

SKIP_SCHEMA_PREFIX = ("dcf_bak", "pg_", "information_schema")
SKIP_TABLE_MARKERS = ("_backup", "_quarantine", "_bak_")

COLUMNS_SQL = """
COPY (SELECT table_schema, table_name, column_name, ordinal_position::text, data_type,
             is_nullable, coalesce(column_default, '')
      FROM information_schema.columns
      ORDER BY table_schema, table_name, ordinal_position) TO STDOUT WITH CSV
"""

PK_SQL = """
COPY (SELECT tc.table_schema, tc.table_name, kcu.column_name
      FROM information_schema.table_constraints tc
      JOIN information_schema.key_column_usage kcu
        ON tc.constraint_name = kcu.constraint_name
       AND tc.table_schema = kcu.table_schema
      WHERE tc.constraint_type = 'PRIMARY KEY') TO STDOUT WITH CSV
"""

FK_SQL = """
COPY (SELECT tc.table_schema, tc.table_name, kcu.column_name,
             ccu.table_name, ccu.column_name
      FROM information_schema.table_constraints tc
      JOIN information_schema.key_column_usage kcu
        ON tc.constraint_name = kcu.constraint_name
       AND tc.table_schema = kcu.table_schema
      JOIN information_schema.constraint_column_usage ccu
        ON tc.constraint_name = ccu.constraint_name
       AND tc.table_schema = ccu.table_schema
      WHERE tc.constraint_type = 'FOREIGN KEY') TO STDOUT WITH CSV
"""

INDEX_SQL = """
COPY (SELECT schemaname, tablename, indexname, indexdef
      FROM pg_indexes) TO STDOUT WITH CSV
"""


def _skip(schema: str, table: str) -> bool:
    if any(schema.startswith(p) for p in SKIP_SCHEMA_PREFIX):
        return True
    low = table.lower()
    return low.startswith("_") or any(m in low for m in SKIP_TABLE_MARKERS)


def _query(sql: str) -> list[list[str]]:
    proc = subprocess.run(
        ["bash", str(DB_LOCAL), "--sql", sql],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"db-local failed: {proc.stderr.strip()[:400]}")
    return [r for r in csv.reader(io.StringIO(proc.stdout)) if r]


def rebuild() -> dict:
    cols = _query(COLUMNS_SQL)
    pks = _query(PK_SQL)
    fks = _query(FK_SQL)
    idxs = _query(INDEX_SQL)

    pk_set = {(s, t, c) for s, t, c in pks}
    fk_map: dict[tuple[str, str], list[dict]] = {}
    for s, t, c, rt, rc in fks:
        fk_map.setdefault((s, t), []).append({"col": c, "ref": f"{rt}.{rc}"})
    idx_map: dict[tuple[str, str], list[dict]] = {}
    for s, t, name, ddl in idxs:
        if _skip(s, t):
            continue
        idx_map.setdefault((s, t), []).append({"name": name, "unique": "UNIQUE INDEX" in ddl})

    tables: dict[tuple[str, str], list[dict]] = {}
    for schema, table, col, _pos, dtype, nullable, default in cols:
        if _skip(schema, table):
            continue
        tables.setdefault((schema, table), []).append(
            {
                "name": col,
                "type": dtype,
                "nullable": nullable == "YES",
                "default": default,
                "pk": (schema, table, col) in pk_set,
            }
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lines = []
    for (schema, table), columns in sorted(tables.items()):
        lines.append(
            json.dumps(
                {
                    "schema": schema,
                    "table": table,
                    "columns": columns,
                    "fks": fk_map.get((schema, table), []),
                    "indexes": idx_map.get((schema, table), []),
                },
                separators=(",", ":"),
            )
        )
    TABLES.write_text("\n".join(lines) + "\n", encoding="utf-8")

    by_schema: dict[str, int] = {}
    for schema, table in tables:
        by_schema[schema] = by_schema.get(schema, 0) + 1
    meta = {
        "source": "localhost:5433 yugabyte (local fixture)",
        "tables": len(tables),
        "columns": sum(len(c) for c in tables.values()),
        "schemas": dict(sorted(by_schema.items(), key=lambda kv: -kv[1])),
        "train_note": "Local fixture. Absence means 'not on this checkout', not 'does not exist'. "
        "Cross-check Flyway in trustt-platform-initial-setup before cross-train claims.",
    }
    META.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


_CACHE: dict[tuple[str, str], dict] | None = None

# 18 table names exist in more than one schema and 6 of those carry DIFFERENT
# columns — `client_request_response_log` lives in accounting, audit and los.
# Merging them let the gate accept a column that only exists in a sibling schema,
# so every lookup is schema-scoped. An unqualified name resolves in this order.
SCHEMA_PREFERENCE = [
    "mfi_accounting", "mfi_los", "mfi_actor", "mfi_payments", "mfi_task",
    "mfi_masterdata", "mfi_batch", "mfi_notifications", "mfi_audit",
    "mfi_authorization", "mfi_approval", "mfi_reporting",
]


def load() -> dict[tuple[str, str], dict]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    out: dict[tuple[str, str], dict] = {}
    if TABLES.is_file():
        for line in TABLES.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            out[(row["schema"], row["table"])] = {
                "columns": {c["name"]: c for c in row["columns"]},
                "fks": row["fks"],
                "indexes": row["indexes"],
            }
    _CACHE = out
    return out


def schemas_for(table: str) -> list[str]:
    return sorted(s for (s, t) in load() if t == table)


def schemas_and_tables(schema: str) -> set[str]:
    return {t for (s, t) in load() if s == schema}


def resolve(ref: str) -> tuple[str | None, str, dict | None]:
    """`ref` is `table` or `schema.table`. Returns (schema, table, entry)."""
    parts = ref.split(".")
    if len(parts) >= 2 and (parts[0], parts[1]) in load():
        return parts[0], parts[1], load()[(parts[0], parts[1])]
    table = parts[0]
    candidates = schemas_for(table)
    if not candidates and len(parts) > 1:
        table = parts[-1]
        candidates = schemas_for(table)
    if not candidates:
        return None, table, None
    for preferred in SCHEMA_PREFERENCE:
        if preferred in candidates:
            return preferred, table, load()[(preferred, table)]
    return candidates[0], table, load()[(candidates[0], table)]


def known_table(table: str) -> bool:
    return resolve(table)[2] is not None


def has_column(table: str, column: str) -> bool:
    entry = resolve(table)[2]
    return bool(entry) and column in entry["columns"]


def columns_of(table: str) -> list[str]:
    entry = resolve(table)[2]
    return sorted(entry["columns"]) if entry else []


def describe(ref: str) -> str:
    parts = ref.split(".")
    column = ""
    table_ref = ref
    if len(parts) >= 2:
        if (parts[0], parts[1]) in load():
            table_ref = f"{parts[0]}.{parts[1]}"
            column = parts[2] if len(parts) > 2 else ""
        else:
            table_ref, column = ".".join(parts[:-1]), parts[-1]
    schema, table, entry = resolve(table_ref)
    if not entry:
        return f"unknown table: {table}"
    others = [s for s in schemas_for(table) if s != schema]
    also = f"  (also in {', '.join(others)} — qualify to target those)" if others else ""
    if column:
        col = entry["columns"].get(column)
        if not col:
            near = [c for c in entry["columns"] if column in c or c in column]
            hint = f" — did you mean: {', '.join(near[:5])}" if near else ""
            return (
                f"{schema}.{table}.{column}: NOT A COLUMN{hint}{also}\n"
                f"  columns: {', '.join(sorted(entry['columns']))}"
            )
        null = "NULL ok" if col["nullable"] else "NOT NULL"
        dflt = f" default={col['default']}" if col["default"] else ""
        pk = " PK" if col["pk"] else ""
        return f"{schema}.{table}.{column}: {col['type']} {null}{dflt}{pk}{also}"
    out = [f"{schema}.{table}  {len(entry['columns'])} columns{also}"]
    for name in sorted(entry["columns"]):
        col = entry["columns"][name]
        flags = "".join([" PK" if col["pk"] else "", "" if col["nullable"] else " NOT NULL"])
        out.append(f"  {name:45s} {col['type']}{flags}")
    if entry["fks"]:
        out.append("  FK: " + ", ".join(f"{f['col']}->{f['ref']}" for f in entry["fks"][:12]))
    return "\n".join(out)


def main(argv: list[str]) -> int:
    if "--rebuild" in argv:
        meta = rebuild()
        print(f"schema oracle: {meta['tables']} tables · {meta['columns']} columns")
        for schema, count in meta["schemas"].items():
            print(f"  {schema:22s} {count}")
        return 0
    if not argv:
        meta = json.loads(META.read_text(encoding="utf-8")) if META.is_file() else {}
        print(f"schema oracle: {meta.get('tables', 0)} tables · {meta.get('columns', 0)} columns")
        print("usage: schema_oracle.py --rebuild | <table> | <table>.<column>")
        return 0
    print(describe(argv[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
