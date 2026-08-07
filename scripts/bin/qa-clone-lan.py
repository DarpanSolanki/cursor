#!/usr/bin/env python3
"""Clone a QA loan's state into a local seed file, so a QA-reported bug can be run here.

The workspace can execute only locally. QA is read-only, prod is invisible. So every
finding carries `NOT VERIFIED ON <env>` — honest, and a permanent handicap: TDPQA-72 was
a QA4 observation and there was no way to reproduce it in the environment that saw it.

This closes that. It reads one LAN's rows from QA (read-only, through the existing
wrapper, which also column-checks against QA's own catalog) and writes **a local seed
file**. It does not apply anything: applying is a separate, explicit step through
`db-local-write.sh`, because the boundary between "read QA" and "write local" should stay
visible in the transcript.

    scripts/bin/qa-clone-lan.py --env qa4 --lan 6004044425
    scripts/bin/qa-clone-lan.py --env qa4 --lan 6004044425 --out /path/seed.sql

What it is *not*: a request replay. `client_request_response_log` records outbound partner
calls, not the inbound API envelope, so the request that caused the state is not
recoverable from it. Cloning the state and then driving the real orchestration locally is
the honest substitute — and it is the one that satisfies
`run-the-real-thing-locally.md`, because the flow under test still runs for real.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "mfi_accounting"

# Ordered parent-first so a straight apply satisfies FKs.
#
# Each entry lists *candidate* link columns rather than one hardcoded name. Trains differ
# — `loan_account_events_queue` has `parent_account_id` on QA4 but not `account_id` — and
# a hardcoded column turns a clone into a crash on the first environment that renamed it.
# The real column set is read from the target's own catalog, same discipline as
# sql_column_check: resolve before you name.
BY_ACCOUNT = ("account_id", "loan_account_id", "parent_account_id", "parent_loan_account_id")
BY_LAN = ("loan_account_number",)

TABLES: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [
    ("account", ("id",), ()),
    ("loan_account", ("account_id",), ()),
    ("account_interest_details", ("account_id",), ()),
    ("loan_installment_details", BY_ACCOUNT, ()),
    ("loan_due_details", BY_ACCOUNT, ()),
    ("loan_account_payments_details", BY_ACCOUNT, ()),
    ("loan_disbursement_mode_details", BY_ACCOUNT, ()),
    ("loan_disbursement_charge_details", BY_ACCOUNT, ()),
    ("loan_account_charge_details", BY_ACCOUNT, ()),
    ("loan_account_events_queue", BY_ACCOUNT, ()),
    ("loan_repayment_schedule_details", BY_ACCOUNT, ()),
    ("interest_accrual_details", BY_ACCOUNT, ()),
    ("prepayment_details", BY_ACCOUNT, ()),
    ("loan_disbursement_cancellation_details", BY_ACCOUNT, ()),
    ("loan_account_closure_details", BY_ACCOUNT, ()),
    ("client_request_response_log", (), BY_LAN),
]

_COLUMN_CACHE: dict[str, set[str]] = {}


def columns_of(env: str, table: str) -> set[str]:
    if table not in _COLUMN_CACHE:
        raw = scalar(env, "SELECT string_agg(column_name, ',') FROM information_schema.columns "
                          f"WHERE table_schema='{SCHEMA}' AND table_name='{table}'")
        _COLUMN_CACHE[table] = {c.strip() for c in raw.split(",") if c.strip()}
    return _COLUMN_CACHE[table]


def where_for(env: str, table: str, by_account: tuple[str, ...], by_lan: tuple[str, ...],
              account_id: str, lan: str) -> str:
    present = columns_of(env, table)
    parts = [f"{c} = {account_id}" for c in by_account if c in present]
    parts += [f"{c} = '{lan}'" for c in by_lan if c in present]
    return " OR ".join(parts)


def qa(env: str, sql: str, timeout: int = 180) -> str:
    out = subprocess.run(
        ["bash", str(ROOT / "scripts/db-qa.sh"), "--env", env, "--sql", sql],
        capture_output=True, text=True, timeout=timeout, cwd=str(ROOT),
        env={**__import__("os").environ, "DB_QA_SKIP_COLUMN_CHECK": "1"})
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip()[:400] or "qa query failed")
    return out.stdout


def scalar(env: str, sql: str) -> str:
    """Single value via an explicit marker.

    db-qa.sh runs psql in aligned mode, so positional parsing picks up the column header
    as the first data line. Marking the value is unambiguous regardless of formatting.
    """
    marked = sql.strip().rstrip(";")
    marked = f"SELECT '<<V>>' || COALESCE(({marked})::text, '') || '<<E>>';"
    for line in qa(env, marked).splitlines():
        m = re.search(r"<<V>>(.*?)<<E>>", line)
        if m:
            return m.group(1)
    return ""


def table_exists(env: str, table: str) -> bool:
    got = scalar(env, f"SELECT count(*) FROM information_schema.tables "
                      f"WHERE table_schema='{SCHEMA}' AND table_name='{table}';")
    return got.strip().isdigit() and int(got.strip()) > 0


def rows_as_json(env: str, table: str, where: str) -> list[dict]:
    sql = (f"SELECT COALESCE(json_agg(t), '[]'::json) FROM "
           f"(SELECT * FROM {SCHEMA}.{table} WHERE {where}) t;")
    marked = f"SELECT '<<V>>' || ({sql.rstrip(';')})::text || '<<E>>';"
    raw = qa(env, marked)
    body = ""
    capture = False
    for line in raw.splitlines():
        if "<<V>>" in line:
            capture = True
            line = line.split("<<V>>", 1)[1]
        if capture:
            if "<<E>>" in line:
                body += line.split("<<E>>", 1)[0]
                break
            body += line.strip()
    body = body.strip()
    if not body:
        return []
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return []


_PK_CACHE: dict[str, list[str]] = {}


def primary_key_of(env: str, table: str) -> list[str]:
    """Real PK columns, read from the catalog.

    `loan_account` is joined-inheritance: its PK is `account_id`, not `id`. Assuming `id`
    produced an ON CONFLICT clause the table could not honour, so the upsert degraded to
    a plain INSERT and died on the primary key. Ask, do not assume.
    """
    if table not in _PK_CACHE:
        raw = scalar(env,
            "SELECT string_agg(a.attname, ',' ORDER BY k.ord) "
            "FROM pg_constraint c "
            "JOIN LATERAL unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord) ON true "
            "JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum "
            f"WHERE c.contype = 'p' AND c.conrelid = '{SCHEMA}.{table}'::regclass")
        _PK_CACHE[table] = [c.strip() for c in raw.split(",") if c.strip()]
    return _PK_CACHE[table]


def sql_literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (dict, list)):
        value = json.dumps(value)
    return "'" + str(value).replace("'", "''") + "'"


def upsert(env: str, table: str, rows: list[dict]) -> list[str]:
    out: list[str] = []
    pk = [c for c in primary_key_of(env, table)]
    for row in rows:
        cols = list(row.keys())
        vals = ", ".join(sql_literal(row[c]) for c in cols)
        collist = ", ".join(f'"{c}"' for c in cols)
        conflict = ""
        if pk and all(c in cols for c in pk):
            target = ", ".join(f'"{c}"' for c in pk)
            sets = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in cols if c not in pk)
            conflict = (f" ON CONFLICT ({target}) DO UPDATE SET {sets}" if sets
                        else f" ON CONFLICT ({target}) DO NOTHING")
        out.append(f"INSERT INTO {SCHEMA}.{table} ({collist}) VALUES ({vals}){conflict};")
    return out


def dry_run(statements: list[str]) -> tuple[bool, str]:
    """Apply against local inside a transaction, then ROLLBACK. Never commits."""
    import os
    if not statements:
        return True, ""
    sql = "BEGIN;\n" + "\n".join(statements) + "\nROLLBACK;"
    try:
        r = subprocess.run(
            ["psql", "-h", os.environ.get("PGHOST", "localhost"),
             "-p", os.environ.get("PGPORT", "5433"),
             "-U", os.environ.get("PGUSER", "yugabyte"),
             "-d", os.environ.get("PGDATABASE", "yugabyte"),
             "-v", "ON_ERROR_STOP=1", "-q"],
            input=sql, capture_output=True, text=True, timeout=300,
            env=dict(os.environ, PGPASSWORD=os.environ.get("PGPASSWORD", "yugabyte")))
        if r.returncode == 0:
            return True, ""
        return False, (r.stderr or "").strip().splitlines()[0][:200]
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:200]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", required=True, help="qa1..qa6")
    ap.add_argument("--lan", required=True)
    ap.add_argument("--out")
    ap.add_argument("--include-children", action="store_true",
                    help="also clone every child of a group parent")
    args = ap.parse_args()

    if not re.fullmatch(r"\d{6,}", args.lan):
        print(f"not a LAN: {args.lan}", file=sys.stderr)
        return 2

    account_id = scalar(args.env, f"SELECT id FROM {SCHEMA}.account "
                                  f"WHERE account_number = '{args.lan}' LIMIT 1;").strip()
    if not account_id.isdigit():
        print(f"{args.lan} not found on {args.env}", file=sys.stderr)
        return 1

    account_ids = [account_id]
    if args.include_children:
        kids = qa(args.env, f"SELECT account_id FROM {SCHEMA}.loan_account "
                            f"WHERE parent_loan_account_id = {account_id};")
        for line in kids.splitlines():
            v = line.strip()
            if v.isdigit():
                account_ids.append(v)

    statements: list[str] = []
    summary: list[tuple[str, int]] = []
    skipped: list[str] = []
    for table, by_account, by_lan in TABLES:
        if not table_exists(args.env, table):
            skipped.append(f"{table} (absent on {args.env})")
            continue
        total = 0
        for aid in account_ids:
            lan = args.lan if aid == account_id else scalar(
                args.env, f"SELECT account_number FROM {SCHEMA}.account WHERE id = {aid}").strip()
            clause = where_for(args.env, table, by_account, by_lan, aid, lan)
            if not clause:
                continue
            rows = rows_as_json(args.env, table, clause)
            if rows:
                statements.extend(upsert(args.env, table, rows))
                total += len(rows)
        if total:
            summary.append((table, total))

    out_path = Path(args.out) if args.out else (
        ROOT / f"scripts/scratch/qa-clone/{args.env}-{args.lan}.sql")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    header = [
        f"-- QA clone: {args.lan} from {args.env}",
        f"-- account_id(s): {', '.join(account_ids)}",
        "-- Read-only capture. Apply deliberately:",
        f"--   bash scripts/bin/db-local-write.sh --file {out_path}",
        "-- Then drive the REAL flow locally; do not assert on these rows alone.",
        "BEGIN;",
    ]
    out_path.write_text("\n".join(header + statements + ["COMMIT;"]) + "\n", encoding="utf-8")

    print(f"cloned {args.lan} from {args.env}  ({len(account_ids)} account(s))")
    for table, n in summary:
        print(f"  {table:<42} {n}")
    for note in skipped:
        print(f"  -- {note}")
    print(f"\nseed: {out_path}")

    # A seed that does not apply cleanly is worse than none: it fails halfway and leaves
    # a partial clone. Prove it against the real local schema first, then roll back.
    ok, err = dry_run(statements)
    if ok:
        print("dry-run: OK (applied and rolled back against local)")
    else:
        print(f"dry-run: FAILED — {err}", file=sys.stderr)
        print("  the seed was still written; fix the clone before applying", file=sys.stderr)
    print(f"apply: bash scripts/bin/db-local-write.sh --file {out_path}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
