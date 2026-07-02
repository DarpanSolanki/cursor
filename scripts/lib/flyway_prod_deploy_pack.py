#!/usr/bin/env python3
"""Build production deploy SQL: DDL + flyway_schema_history INSERT (manual prod path)."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

VERSION_RE = re.compile(r"^V([0-9.]+)__(.+)\.sql$", re.I)
CREATE_INDEX_RE = re.compile(r"\bcreate\s+index\b", re.I)
ALTER_RE = re.compile(r"\balter\s+table\b", re.I)
INSERT_DATA_RE = re.compile(r"\binsert\s+into\b", re.I)
UPDATE_RE = re.compile(r"\bupdate\b", re.I)


def parse_flyway_file(path: Path) -> tuple[str, str, str, str]:
    m = VERSION_RE.match(path.name)
    if not m:
        raise SystemExit(f"Not a Flyway migration filename: {path.name}")
    version_raw = m.group(1)
    version = version_raw.lstrip("0") or "0"
    version_padded = version_raw.zfill(6) if version_raw.isdigit() else version_raw
    # History table stores 6-digit style without leading V, e.g. 000198
    version_history = version_padded if version_raw.isdigit() else version_raw
    description = m.group(2).replace("_", " ")
    script_ref = _script_ref(path)
    return version_history, description, script_ref, path.read_text(encoding="utf-8")


def _script_ref(path: Path) -> str:
    parts = path.as_posix().split("/")
    if "product" in parts:
        idx = parts.index("product")
        return "/".join(parts[idx:])
    if "sql" in parts:
        idx = parts.index("sql")
        return "/".join(parts[idx + 1 :])
    return path.name


def infer_schema(path: Path) -> str:
    parts = path.as_posix().split("/")
    try:
        sli = parts.index("sli")
        service = parts[sli + 1]
    except (ValueError, IndexError):
        return "mfi_accounting"
    mapping = {
        "accounting": "mfi_accounting",
        "los": "mfi_los",
        "actor": "mfi_actor",
        "task": "mfi_task",
        "payments": "mfi_payments",
        "batch": "mfi_batch",
        "audit": "mfi_audit",
        "notifications": "mfi_notifications",
        "reporting": "mfi_reporting",
        "dms": "mfi_dms",
        "bre": "mfi_bre",
        "consents": "mfi_consents",
        "platform_master": "platform_master",
        "platform_batch_master": "platform_batch_master",
        "platform_batch_worker": "platform_batch_worker",
    }
    return mapping.get(service, f"mfi_{service}")


def infer_timing(sql: str, description: str) -> str:
    """pre = before app deploy; post = after app deploy."""
    low = sql.lower()
    if CREATE_INDEX_RE.search(sql) or ALTER_RE.search(sql):
        return "pre"
    if INSERT_DATA_RE.search(sql) and not CREATE_INDEX_RE.search(sql):
        return "post"
    if UPDATE_RE.search(sql):
        return "post"
    if "create table" in low:
        return "pre"
    return "pre"


def strip_comments(sql: str) -> str:
    lines = []
    for line in sql.splitlines():
        s = line.strip()
        if s and not s.startswith("--"):
            lines.append(line.rstrip())
    return "\n".join(lines).strip()


def history_insert(schema: str, version: str, description: str, script: str) -> str:
    desc = description.replace("'", "''")
    fq = f"{schema}.flyway_schema_history"
    return f"""INSERT INTO {fq}
(installed_rank, version, description, type, script, checksum, installed_by, installed_on, execution_time, success)
VALUES
((SELECT COALESCE(MAX(installed_rank), 0) + 1 FROM {fq}),
 '{version}', '{desc}', 'SQL', '{script}', NULL, 'yugabyte', NOW(), 0, true);"""


def build_pack(
    flyway_path: Path,
    *,
    schema: str | None = None,
    timing: str | None = None,
) -> dict:
    version, description, script_ref, raw_sql = parse_flyway_file(flyway_path)
    schema = schema or infer_schema(flyway_path)
    ddl = strip_comments(raw_sql)
    timing = timing or infer_timing(ddl, description)
    insert = history_insert(schema, version, description, script_ref)
    return {
        "flyway_file": str(flyway_path.relative_to(ROOT)) if flyway_path.is_relative_to(ROOT) else str(flyway_path),
        "schema": schema,
        "version": version,
        "description": description,
        "script": script_ref,
        "timing": timing,
        "ddl": ddl,
        "flyway_history_insert": insert,
    }


def format_pack(pack: dict) -> str:
    timing = pack["timing"].upper()
    lines = [
        f"-- Production deploy pack: {pack['schema']} {pack['version']} ({pack['description']})",
        f"-- Source: {pack['flyway_file']}",
        f"-- Timing: {timing}-DEPLOYMENT (run DDL + history INSERT in same change window)",
        "",
        f"-- === {timing.upper()} DEPLOYMENT: DDL (execute on {pack['schema']}) ===",
        "",
        pack["ddl"],
        "",
        f"-- === {timing.upper()} DEPLOYMENT: register in Flyway history ===",
        "",
        pack["flyway_history_insert"],
        "",
        f"-- Verify: SELECT version, script, success FROM {pack['schema']}.flyway_schema_history WHERE version = '{pack['version']}';",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Prod Flyway manual deploy pack (DDL + history INSERT)")
    ap.add_argument("flyway_sql", type=Path, help="Path to Vxxxx__*.sql in initial-setup")
    ap.add_argument("--schema", help="Override schema (default: infer from flyway path)")
    ap.add_argument("--timing", choices=["pre", "post"], help="Override pre/post deploy")
    ap.add_argument("--out", type=Path, help="Write combined .sql file")
    args = ap.parse_args()

    path = args.flyway_sql
    if not path.is_file():
        path = ROOT / args.flyway_sql
    if not path.is_file():
        raise SystemExit(f"File not found: {args.flyway_sql}")

    pack = build_pack(path, schema=args.schema, timing=args.timing)
    text = format_pack(pack)
    if args.out:
        out = args.out if args.out.is_absolute() else ROOT / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(f"Wrote {out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
