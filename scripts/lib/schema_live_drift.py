#!/usr/bin/env python3
"""Columns the code maps but the live local DB does not have.

`schema_train_diff.py` answers "live has it, Flyway does not". This answers the
direction that actually breaks a run: an entity or query names a column, the local
DB never got it, and the flow dies at runtime with `Unable to find column position
by name: <col>` — or an agent writes a query that errors with `column does not exist`.

Precedent: mfi_los.loan_app.vrm_category. LoanAppEntity mapped it, V000001__table.sql
declared it, the local DB predated it, and getTaskDataFromLos failed for an hour before
anyone looked at the column list.

  schema_live_drift.py                 # all schemas
  schema_live_drift.py --schema mfi_los
  schema_live_drift.py --json
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "cursor-bundle" / "schema"


def load_live() -> dict[tuple[str, str], set[str]]:
    live: dict[tuple[str, str], set[str]] = {}
    path = SCHEMA_DIR / "tables.jsonl"
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        key = (row["schema"], row["table"])
        live[key] = {c["name"] for c in row.get("columns") or []}
    return live


def load_bindings() -> list[dict]:
    path = SCHEMA_DIR / "bindings.jsonl"
    out = []
    for line in path.read_text().splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def is_persistent(binding: dict) -> bool:
    java_type = binding.get("java_type") or ""
    if "static" in java_type or "transient" in java_type:
        return False
    return binding.get("field") != "serialVersionUID"


def compute_drift(bindings: list[dict], live: dict[tuple[str, str], set[str]], schema_filter: str | None) -> list[dict]:
    drift = []
    seen = set()
    for b in bindings:
        schema, table, column = b.get("schema"), b.get("table"), b.get("column")
        if not (schema and table and column):
            continue
        if not is_persistent(b):
            continue
        if (schema, table, column) in seen:
            continue
        seen.add((schema, table, column))
        if schema_filter and schema != schema_filter:
            continue
        key = (schema, table)
        if key not in live:
            continue
        if column in live[key]:
            continue
        drift.append({
            "schema": schema,
            "table": table,
            "column": column,
            "entity": b.get("entity"),
            "repo": b.get("repo"),
            "source": b.get("source"),
        })
    return sorted(drift, key=lambda d: (d["schema"], d["table"], d["column"]))


def find_drift(schema_filter: str | None) -> list[dict]:
    return compute_drift(load_bindings(), load_live(), schema_filter)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if not (SCHEMA_DIR / "tables.jsonl").exists():
        print("schema oracle missing — run: bash scripts/bin/schema-sync.sh", file=sys.stderr)
        return 2

    drift = find_drift(args.schema)
    if args.json:
        print(json.dumps(drift, indent=1))
        return 1 if drift else 0

    if not drift:
        if not args.quiet:
            print("schema live drift: none — every mapped column exists in the local DB")
        return 0

    by_schema = collections.defaultdict(list)
    for d in drift:
        by_schema[d["schema"]].append(d)

    print(f"schema live drift: {len(drift)} mapped column(s) missing from the local DB")
    for schema in sorted(by_schema):
        rows = by_schema[schema]
        print(f"\n  {schema}  ({len(rows)})")
        for d in rows:
            entity = d["entity"] or "?"
            print(f"    {d['table']}.{d['column']:<34} {entity}")
    print("\n  Fix: apply the migration that declares it, or ALTER the local table to match")
    print("  the migration (never invent a type — read it from the Flyway SQL).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
