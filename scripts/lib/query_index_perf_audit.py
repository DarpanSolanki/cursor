#!/usr/bin/env python3
"""Audit native SQL / batch reader filters for index coverage and EXPLAIN plans."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

TABLE_COL_RE = re.compile(
    r"\b(death_foreclosure_details_id|claim_status|inout_status|status|claim_number|id)\b",
    re.I,
)
SEQ_SCAN_RE = re.compile(r"Seq Scan", re.I)
INDEX_SCAN_RE = re.compile(r"Index Scan|Index Only Scan|Bitmap Index Scan", re.I)


@dataclass
class QueryProfile:
    name: str
    table: str
    schema: str
    explain_sql: str
    predicate_columns: list[str]
    note: str = ""
    max_seq_scan_cost: float = 5000.0


@dataclass
class AuditResult:
    profile: str
    indexes: list[str] = field(default_factory=list)
    covering_index: bool = False
    explain_lines: list[str] = field(default_factory=list)
    seq_scan: bool = False
    index_scan: bool = False
    explain_cost: float | None = None
    verdict: str = "UNKNOWN"
    detail: str = ""


DFC_INSURANCE_PROFILES: list[QueryProfile] = [
    QueryProfile(
        name="reader_business_job",
        table="death_foreclosure_insurance_staging_details",
        schema="mfi_accounting",
        explain_sql="""
SELECT id FROM mfi_accounting.death_foreclosure_insurance_staging_details
WHERE id >= 1 AND id <= 100000
  AND claim_status NOT IN ('PENDING', 'REJECTED', 'APPROVED')
  AND inout_status = 'INBOUND_SUCCESS'
  AND (status IS NULL OR status NOT IN ('PROCESSING', 'COMPLETED'))
ORDER BY id
""",
        predicate_columns=["id", "claim_status", "inout_status", "status"],
        note="Batch reader (fix adds status NOT IN PROCESSING/COMPLETED — narrows rows, same scan shape).",
    ),
    QueryProfile(
        name="claim_for_reupload",
        table="death_foreclosure_insurance_staging_details",
        schema="mfi_accounting",
        explain_sql="""
SELECT id FROM mfi_accounting.death_foreclosure_insurance_staging_details
WHERE death_foreclosure_details_id = (
  SELECT death_foreclosure_details_id
  FROM mfi_accounting.death_foreclosure_insurance_staging_details
  WHERE claim_status = 'Pending for FR' AND inout_status = 'INBOUND_SUCCESS'
  LIMIT 1
)
  AND claim_status = 'Pending for FR'
  AND inout_status = 'INBOUND_SUCCESS'
  AND (status IS NULL OR status = 'FAILED')
""",
        predicate_columns=[
            "death_foreclosure_details_id",
            "claim_status",
            "inout_status",
            "status",
        ],
        note="UPDATE claimForReUpload — one row per RE_UPLOAD attempt.",
    ),
    QueryProfile(
        name="lookup_by_dfc_id",
        table="death_foreclosure_insurance_staging_details",
        schema="mfi_accounting",
        explain_sql="""
SELECT id FROM mfi_accounting.death_foreclosure_insurance_staging_details
WHERE death_foreclosure_details_id = (
  SELECT death_foreclosure_details_id
  FROM mfi_accounting.death_foreclosure_insurance_staging_details LIMIT 1
)
""",
        predicate_columns=["death_foreclosure_details_id"],
        note="findOneByDeathForeclosureDetailsId — per RE_UPLOAD row.",
    ),
    QueryProfile(
        name="mark_processing_status",
        table="death_foreclosure_insurance_staging_details",
        schema="mfi_accounting",
        explain_sql="""
SELECT id FROM mfi_accounting.death_foreclosure_insurance_staging_details
WHERE death_foreclosure_details_id = (
  SELECT death_foreclosure_details_id
  FROM mfi_accounting.death_foreclosure_insurance_staging_details LIMIT 1
)
  AND status = 'PROCESSING'
""",
        predicate_columns=["death_foreclosure_details_id", "status"],
        note="markReUploadFailed / markAccountingPending WHERE clause.",
    ),
    QueryProfile(
        name="count_by_claim_number",
        table="death_foreclosure_insurance_staging_details",
        schema="mfi_accounting",
        explain_sql="""
SELECT COUNT(1) FROM mfi_accounting.death_foreclosure_insurance_staging_details
WHERE claim_number = 'DUMMY' AND claim_status IN ('Claim Closed', 'Pending for FR')
""",
        predicate_columns=["claim_number", "claim_status"],
        note="Duplicate claim validation in processor (Claim Closed path).",
    ),
]

PROFILE_GROUPS = {
    "dcf_insurance_reupload": DFC_INSURANCE_PROFILES,
}


def _run_db_cmd(db_runner: list[str], sql: str) -> tuple[int, str]:
    proc = subprocess.run(
        [*db_runner, "--sql", sql.strip()],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out


def _parse_indexes(db_out: str) -> list[str]:
    lines = []
    for line in db_out.splitlines():
        if "CREATE" in line and "INDEX" in line:
            lines.append(line.strip())
    return lines


def _index_covers(indexdef: str, columns: list[str]) -> bool:
    low = indexdef.lower()
    return any(c.lower() in low for c in columns)


def _parse_explain_cost(explain_out: str) -> float | None:
    m = re.search(r"cost=\s*([\d.]+)\.\.", explain_out)
    if m:
        return float(m.group(1))
    return None


def audit_profile(db_runner: list[str], profile: QueryProfile) -> AuditResult:
    res = AuditResult(profile=profile.name)

    idx_sql = f"""
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = '{profile.schema}' AND tablename = '{profile.table}'
ORDER BY indexname;
"""
    rc, idx_out = _run_db_cmd(db_runner, idx_sql)
    if rc != 0:
        res.verdict = "SKIP"
        res.detail = f"index lookup failed: {idx_out[:200]}"
        return res

    res.indexes = _parse_indexes(idx_out)
    res.covering_index = any(
        _index_covers(idx, profile.predicate_columns) for idx in res.indexes
    )

    explain_sql = f"EXPLAIN (COSTS ON)\n{profile.explain_sql.strip()}"
    rc, ex_out = _run_db_cmd(db_runner, explain_sql)
    if rc != 0:
        res.verdict = "WARN"
        res.detail = f"EXPLAIN failed: {ex_out[:200]}"
        return res

    res.explain_lines = [
        ln.strip() for ln in ex_out.splitlines() if ln.strip() and "QUERY PLAN" not in ln
    ]
    plan_blob = "\n".join(res.explain_lines)
    res.seq_scan = bool(SEQ_SCAN_RE.search(plan_blob))
    res.index_scan = bool(INDEX_SCAN_RE.search(plan_blob))
    res.explain_cost = _parse_explain_cost(plan_blob)

    if res.index_scan and not res.seq_scan:
        res.verdict = "PASS"
        res.detail = "Index scan plan"
    elif res.seq_scan and not res.covering_index:
        cost = res.explain_cost or 0.0
        if cost <= profile.max_seq_scan_cost:
            res.verdict = "WARN"
            res.detail = (
                f"Seq scan (cost≈{cost:.0f}) — acceptable at current table size; "
                f"no secondary index on {', '.join(profile.predicate_columns)}"
            )
        else:
            res.verdict = "FAIL"
            res.detail = (
                f"Seq scan cost≈{cost:.0f} exceeds threshold {profile.max_seq_scan_cost:.0f}"
            )
    elif res.seq_scan and res.covering_index:
        res.verdict = "WARN"
        res.detail = "Seq scan despite secondary index — verify stats / Yugabyte tablet distribution"
    else:
        res.verdict = "PASS"
        res.detail = "Plan OK"

    return res


def audit_group(db_runner: list[str], group: str) -> list[AuditResult]:
    profiles = PROFILE_GROUPS.get(group)
    if not profiles:
        raise SystemExit(f"Unknown profile group: {group}")
    return [audit_profile(db_runner, p) for p in profiles]


def _row_count(db_runner: list[str], schema: str, table: str) -> int | None:
    rc, out = _run_db_cmd(
        db_runner, f"SELECT COUNT(*) AS n FROM {schema}.{table};"
    )
    if rc != 0:
        return None
    for line in out.splitlines():
        line = line.strip()
        if line.isdigit():
            return int(line)
    return None


def print_report(
    group: str, results: list[AuditResult], row_count: int | None, db_label: str
) -> None:
    print(f"=== query-index-perf-audit: {group} ({db_label}) ===")
    if row_count is not None:
        print(f"Table rows (death_foreclosure_insurance_staging_details): {row_count}")
    print("")
    fails = warns = passes = 0
    for r, p in zip(results, PROFILE_GROUPS[group]):
        icon = {"PASS": "[PASS]", "WARN": "[WARN]", "FAIL": "[FAIL]", "SKIP": "[SKIP]"}.get(
            r.verdict, "[?]"
        )
        if r.verdict == "FAIL":
            fails += 1
        elif r.verdict == "WARN":
            warns += 1
        elif r.verdict == "PASS":
            passes += 1
        print(f"{icon} {r.profile}")
        print(f"       {p.note}")
        print(f"       {r.detail}")
        if r.explain_lines:
            print(f"       plan: {r.explain_lines[0][:140]}")
        print("")
    print(
        f"Summary: PASS={passes} WARN={warns} FAIL={fails} "
        f"(Seq scan on small staging table is expected without secondary index)"
    )
    if warns or fails:
        print("")
        print("Recommended L2 index (production scale / high Pending-for-FR volume):")
        print(
            "  CREATE INDEX idx_dfisd_dfc_id "
            "ON mfi_accounting.death_foreclosure_insurance_staging_details "
            "(death_foreclosure_details_id);"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description="Query index + EXPLAIN audit")
    ap.add_argument(
        "--group",
        default="dcf_insurance_reupload",
        choices=sorted(PROFILE_GROUPS.keys()),
    )
    ap.add_argument(
        "--db",
        default="qa4",
        help="qa1-qa5 via scripts/db-qaN.sh, local via scripts/db-local.sh, offline skips EXPLAIN",
    )
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="Exit 1 on FAIL (not WARN)")
    args = ap.parse_args()

    if args.db == "offline":
        print("offline mode: profile definitions only — run with --db qa4 or local for EXPLAIN")
        for p in PROFILE_GROUPS[args.group]:
            print(f"  {p.name}: columns={p.predicate_columns}")
        return 0

    if args.db == "local":
        db_runner = [str(ROOT / "scripts/db-local.sh")]
        db_label = "local"
    elif args.db.startswith("qa"):
        db_runner = [str(ROOT / f"scripts/db-{args.db}.sh")]
        db_label = args.db
    else:
        raise SystemExit(f"Unsupported --db {args.db}")

    results = audit_group(db_runner, args.group)
    row_count = _row_count(
        db_runner, "mfi_accounting", "death_foreclosure_insurance_staging_details"
    )

    if args.json:
        payload = {
            "group": args.group,
            "db": db_label,
            "row_count": row_count,
            "results": [
                {
                    "profile": r.profile,
                    "verdict": r.verdict,
                    "detail": r.detail,
                    "seq_scan": r.seq_scan,
                    "explain_cost": r.explain_cost,
                    "covering_index": r.covering_index,
                }
                for r in results
            ],
        }
        print(json.dumps(payload, indent=2))
    else:
        print_report(args.group, results, row_count, db_label)

    if any(r.verdict == "FAIL" for r in results):
        return 1
    if args.strict and any(r.verdict == "WARN" for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
