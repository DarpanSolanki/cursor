#!/usr/bin/env python3
"""Fail when anything references a table or column the schema does not have.

`dpic.repayment_e2e` and `foreclosure.individual_child` both asserted
`loan_account_payments_details.is_deleted=false` on a table that has no
soft-delete column. Nothing caught it: the expect key was never checked against a
schema, so a money-tier assert described a column that has never existed.

Checked here:
  - registry `acceptance.db_asserts[].table`      must be a known table
  - registry `expect` keys                        must be columns of that table
  - mis-attributed columns in assert prose        see `_misattributed`
  - `<known_table>.<column>` in scripts/**/*.sql  must be a real column

Fail-closed against `cursor-bundle/schema/tables.jsonl`. When the oracle is
missing the gate SKIPS rather than passes — an absent oracle is not evidence.

  schema_ref_gate.py            check, exit 1 on any bad reference
  schema_ref_gate.py --sql      include the SQL corpus scan
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

import schema_oracle  # noqa: E402

REGISTRY = ROOT / "scripts" / "testing" / "registry.json"
SQL_ROOTS = ["scripts/dpic/sql", "scripts/sql", "scripts/testing"]

COMPARISON = re.compile(r"\b([a-z][a-z0-9_]{2,})\s*(?:=|!=|>=|<=|<>)")
QUALIFIED = re.compile(r"\b([a-z_][a-z0-9_]{3,})\.([a-z_][a-z0-9_]{2,})\b")

_ALL_COLUMNS: set[str] | None = None


def _all_columns() -> set[str]:
    """Every column name that exists anywhere in the schema."""
    global _ALL_COLUMNS
    if _ALL_COLUMNS is None:
        _ALL_COLUMNS = {
            col for entry in schema_oracle.load().values() for col in entry["columns"]
        }
    return _ALL_COLUMNS


def _misattributed(token: str, table_columns: set[str]) -> bool:
    """A real column, carrying an underscore, claimed against the wrong table.

    Assert prose mixes shorthand with column names. `debit`, `pending` and
    `prin_pending` are shorthand — they exist on no table, so they are not
    column claims. `is_deleted`, `installment_amount` and `original_amount` are
    genuine columns of OTHER tables, which is what mis-attribution looks like.
    The underscore requirement drops bare English words like `parent`.
    """
    return "_" in token and token not in table_columns and token in _all_columns()


def _iter_asserts(reg: dict):
    for cid, case in reg.items():
        if cid.startswith("_") or not isinstance(case, dict):
            continue
        for entry in (case.get("acceptance") or {}).get("db_asserts") or []:
            if isinstance(entry, dict):
                yield cid, entry


def check_registry() -> list[str]:
    if not REGISTRY.is_file():
        return []
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    bad: list[str] = []
    for cid, entry in _iter_asserts(reg):
        table = (entry.get("table") or "").split(".")[-1]
        if not table:
            continue
        if not schema_oracle.known_table(table):
            bad.append(f"{cid}: unknown table `{table}`")
            continue
        cols = set(schema_oracle.columns_of(table))
        for key in (entry.get("expect") or {}):
            base = key.split(".")[-1].split("[")[0].strip()
            if base and not base.isupper() and base not in cols:
                bad.append(f"{cid}: `{table}.{base}` is not a column (expect key)")
        prose = entry.get("assert") or ""
        for other_table, other_col in QUALIFIED.findall(prose):
            if schema_oracle.known_table(other_table) and not schema_oracle.has_column(
                other_table, other_col
            ):
                bad.append(f"{cid}: `{other_table}.{other_col}` is not a column (assert text)")
        prose = QUALIFIED.sub(" ", prose)
        seen: set[str] = set()
        for token in COMPARISON.findall(prose):
            if token in seen or not _misattributed(token, cols):
                continue
            seen.add(token)
            bad.append(f"{cid}: `{table}.{token}` is not a column (assert text)")
    return bad


SCHEMA_TABLE = re.compile(r"\b(mfi_[a-z_]+|platform_master)\.([a-z_][a-z0-9_]+)\b")


def check_wrong_schema(roots: list[str], suffixes: tuple[str, ...]) -> list[str]:
    """A `schema.table` naming a real table that lives in a DIFFERENT schema.

    `clear_batch_failure_audit.sql` deleted from `mfi_batch.batch_failure_audit`
    while the table is in `mfi_accounting`, so the cleanup silently did nothing.

    Deliberately narrow: an unknown schema (`mfi_config__hdfc.bank`) or a table in
    no schema at all (harness temp tables like `_dpi_synthetic_loan_map`) is NOT
    flagged. Only a table that demonstrably exists somewhere else is a claim we can
    prove wrong — anything looser turns this into noise and gets the gate disabled.
    """
    known_schemas = {s for s, _ in schema_oracle.load()}
    bad: list[str] = []
    for root in roots:
        base = ROOT / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix not in suffixes or not path.is_file():
                continue
            if path.resolve() == Path(__file__).resolve():
                continue
            seen: set[tuple[str, str]] = set()
            text = _strip_sql_comments(path.read_text(encoding="utf-8", errors="ignore").lower())
            for schema, table in SCHEMA_TABLE.findall(text):
                if (schema, table) in seen or schema not in known_schemas:
                    continue
                seen.add((schema, table))
                if (schema, table) in schema_oracle.load():
                    continue
                elsewhere = schema_oracle.schemas_for(table)
                if elsewhere:
                    rel = path.relative_to(ROOT)
                    bad.append(
                        f"{rel}: `{schema}.{table}` — that table is in {', '.join(elsewhere)}"
                    )
    return bad


def _strip_sql_comments(text: str) -> str:
    """Comments carry request-JSON paths like `group_details.group_id`, which are
    not column references."""
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"--[^\n]*", " ", text)


def check_sql() -> list[str]:
    bad: list[str] = []
    for root in SQL_ROOTS:
        base = ROOT / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.sql")):
            text = _strip_sql_comments(path.read_text(encoding="utf-8", errors="ignore").lower())
            seen: set[tuple[str, str]] = set()
            for table, column in QUALIFIED.findall(text):
                if (table, column) in seen or not schema_oracle.known_table(table):
                    continue
                seen.add((table, column))
                if column not in set(schema_oracle.columns_of(table)):
                    rel = path.relative_to(ROOT)
                    bad.append(f"{rel}: `{table}.{column}` is not a column")
    return bad


def main(argv: list[str]) -> int:
    if not schema_oracle.TABLES.is_file():
        print("schema-ref: SKIP — no oracle (run schema_oracle.py --rebuild)")
        return 0
    bad = check_registry()
    if "--sql" in argv:
        bad += check_sql()
        bad += check_wrong_schema(["scripts"], (".sql", ".py", ".sh"))
    if bad:
        print(f"schema-ref: FAIL — {len(bad)} bad reference(s)")
        for line in bad[:40]:
            print(f"  {line}")
        if len(bad) > 40:
            print(f"  … {len(bad) - 40} more")
        return 1
    print("schema-ref: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
