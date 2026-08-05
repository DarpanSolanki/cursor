#!/usr/bin/env python3
"""Separate product schema from local fixture patches.

The oracle records the LOCAL Yugabyte, which is a long-lived dev fixture carrying
hand-applied patches (`scripts/sql/setup/local_setup_dpi_suspense_amount.sql`) and
missing columns that exist on other trains. Treating it as product truth is how
GAP-076 happens.

This diffs the oracle against the initial-setup Flyway corpus so a column can be
labelled: `product` (in Flyway), `local-only` (in the DB, in no migration — do not
build contracts on it), or `not-applied` (migration exists, DB lacks it).

Flyway is read from whatever branch initial-setup is checked out on, which is
reported — a column absent there may simply live on another train.

  schema_train_diff.py [--schema mfi_accounting]
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLYWAY = ROOT / "trustt-platform-initial-setup" / "flyway"
TABLES = ROOT / "cursor-bundle" / "schema" / "tables.jsonl"
OUT = ROOT / "cursor-bundle" / "schema" / "train-diff.json"

ADD_COLUMN_RE = re.compile(
    r"alter\s+table\s+(?:if\s+exists\s+)?(?:[\w]+\.)?(\w+)\s+add\s+(?:column\s+)?(?:if\s+not\s+exists\s+)?(\w+)",
    re.I,
)
CREATE_TABLE_RE = re.compile(
    r"create\s+table\s+(?:if\s+not\s+exists\s+)?(?:[\w]+\.)?(\w+)\s*\((.*?)\n\s*\)\s*;", re.I | re.S
)
COL_LINE_RE = re.compile(r"^\s*\"?(\w+)\"?\s+[a-z]", re.I)
NON_COLUMN = {
    "primary", "unique", "constraint", "foreign", "check", "key", "index", "exclude",
}


def flyway_columns() -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    if not FLYWAY.is_dir():
        return out
    for path in FLYWAY.rglob("*.sql"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for table, col in ADD_COLUMN_RE.findall(text):
            out.setdefault(table.lower(), set()).add(col.lower())
        for table, body in CREATE_TABLE_RE.findall(text):
            cols = out.setdefault(table.lower(), set())
            for line in body.splitlines():
                match = COL_LINE_RE.match(line)
                if match and match.group(1).lower() not in NON_COLUMN:
                    cols.add(match.group(1).lower())
    return out


def _branch() -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(ROOT / "trustt-platform-initial-setup"), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=15,
        ).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def diff(schema: str) -> dict:
    fly = flyway_columns()
    local_only: list[str] = []
    product = 0
    unknown_table = 0
    for line in TABLES.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row["schema"] != schema:
            continue
        known = fly.get(row["table"].lower())
        if known is None:
            unknown_table += 1
            continue
        for col in row["columns"]:
            if col["name"].lower() in known:
                product += 1
            else:
                local_only.append(f"{row['table']}.{col['name']}")
    return {
        "schema": schema,
        "flyway_branch": _branch(),
        "flyway_tables": len(fly),
        "product_columns": product,
        "local_only_columns": sorted(local_only),
        "tables_absent_from_flyway": unknown_table,
        "note": "local-only means: present in the local fixture, matched by no migration on "
        "the checked-out initial-setup branch. It is not proof the column is invented — it "
        "may live on another train. Never build a cross-train contract on one.",
    }


def main(argv: list[str]) -> int:
    schema = "mfi_accounting"
    if "--schema" in argv:
        schema = argv[argv.index("--schema") + 1]
    result = diff(schema)
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"train diff · {schema} · flyway branch {result['flyway_branch']}")
    print(f"  matched a migration      : {result['product_columns']}")
    print(f"  local-only (unmatched)   : {len(result['local_only_columns'])}")
    print(f"  tables absent from flyway: {result['tables_absent_from_flyway']}")
    for ref in result["local_only_columns"][:15]:
        print(f"    {ref}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
