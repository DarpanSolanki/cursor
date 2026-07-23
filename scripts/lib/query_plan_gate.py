#!/usr/bin/env python3
"""Query plan gate — EXPLAIN heuristics when diff touches @Query / native SQL / repo methods.

Lean delta (Upgrade 11): does NOT replace reuse_query_gate (ladder) or query-index-perf-audit
(profile matrix). Adds: auto-detect query_touched → local EXPLAIN → PASS/WARN/FAIL + excerpt.

Exit: 0 = PASS or SKIPPED; 1 = FAIL; 2 = usage error.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))

import reuse_query_gate as rqg  # noqa: E402

PENDING = ROOT / ".cursor" / ".pending-ship-work.json"
RESULT = ROOT / ".cursor" / ".query-plan-gate-result.json"
EVIDENCE_DIR = ROOT / ".cursor" / "query-plan-evidence"
SELF_REPORT = ROOT / "cursor-bundle" / "memory" / "SELF-REPORT.md"
MANIFEST = ROOT / "scripts" / "lib" / "acceptance_coverage_manifest.json"
DEFAULT_SCHEMA = "mfi_accounting"

SEQ_SCAN_RE = re.compile(r"\bSeq Scan\b", re.I)
INDEX_SCAN_RE = re.compile(r"\b(?:Index(?: Only)? Scan|Bitmap Index Scan|Bitmap Heap Scan)\b", re.I)
NESTLOOP_RE = re.compile(r"\bNested Loop\b", re.I)
COST_RE = re.compile(r"cost=[\d.]+\.\.([\d.]+)")
TABLE_FROM_RE = re.compile(
    r"\b(?:FROM|JOIN|UPDATE|INTO|TABLE)\s+(?:ONLY\s+)?(?:(\w+)\.)?(\w+)",
    re.I,
)
SQL_CHUNK_RE = re.compile(
    r"""(?is)(?:value\s*=\s*)?(?:\"\"\"|'''|"|')\s*((?:SELECT|WITH|UPDATE|DELETE|INSERT)\b.{12,}?)\s*(?:\"\"\"|'''|"|')"""
)
PLACEHOLDER_RE = re.compile(r"\?(?:\d+)?|:[A-Za-z_]\w*")

# Reader / batch SQL files also carry native SQL outside *Repository.java
_EXTRA_SQL_FILES = re.compile(r"(?i)(Reader|Writer|ItemReader|Jdbc)\.java$")


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def money_tables() -> set[str]:
    if not MANIFEST.is_file():
        return {
            "loan_account",
            "loan_account_billing_details",
            "loan_account_payments_details",
            "transaction_master",
            "client_request_response_log",
        }
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    out: set[str] = set()
    for tables in (data.get("domain_money_tables") or {}).values():
        out.update(t.lower() for t in (tables or []))
    return out


def pending_files(pending: dict | None = None) -> list[str]:
    if pending is None:
        if not PENDING.is_file():
            return []
        pending = json.loads(PENDING.read_text(encoding="utf-8"))
    return [str(f).replace("\\", "/") for f in (pending.get("files") or [])]


def is_query_candidate_file(path: str) -> bool:
    if rqg.is_repo_or_dao_file(path):
        return True
    base = Path(path).name
    if _EXTRA_SQL_FILES.search(base):
        return True
    return path.endswith(".java") and ("repository" in path.lower() or "/dao/" in path.lower())


def _repo_rel(path: str) -> tuple[str, str]:
    return rqg._repo_and_rel(path)  # noqa: SLF001 — shared helper


def collect_query_touches(
    files: list[str],
    *,
    root: Path = ROOT,
    diff_getter=None,
) -> list[dict[str, Any]]:
    """Files whose diff changes query semantics (reuse markers + reader SQL)."""
    getter = diff_getter or rqg.default_diff_getter(root)
    out: list[dict[str, Any]] = []
    for f in files or []:
        if not is_query_candidate_file(f):
            continue
        repo, rel = _repo_rel(f)
        diff = getter(repo, rel)
        signals = rqg.diff_query_signals(diff)
        if not signals and not (diff and re.search(r"(?i)\b(select|from|where)\b", diff)):
            continue
        if not signals:
            signals = ["sql-text"]
        sqls = extract_sql_from_diff(diff)
        out.append({"file": f, "signals": signals, "sqls": sqls, "diff": diff})
    return out


def query_touched(files: list[str] | None = None, **kwargs) -> bool:
    files = files if files is not None else pending_files()
    return bool(collect_query_touches(files, **kwargs))


def extract_sql_from_diff(diff_text: str) -> list[str]:
    """Pull native SQL string fragments from added (+) diff lines."""
    if not diff_text:
        return []
    added: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:])
    blob = "\n".join(added)
    # Join Java string concatenations: "a " + "b"
    blob = re.sub(r'"\s*\+\s*"', "", blob)
    blob = re.sub(r"'\s*\+\s*'", "", blob)
    found: list[str] = []
    for m in SQL_CHUNK_RE.finditer(blob):
        sql = " ".join(m.group(1).split())
        if len(sql) >= 20:
            found.append(sql)
    # Fallback: whole-line SELECT fragments
    if not found:
        for line in added:
            s = line.strip().strip('"').strip("'")
            if re.match(r"(?i)^(SELECT|WITH|UPDATE|DELETE|INSERT)\b", s) and len(s) > 20:
                found.append(s)
    # de-dupe
    seen: set[str] = set()
    out: list[str] = []
    for s in found:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def bind_placeholders(sql: str) -> str:
    """Replace ? / :name with safe literals for EXPLAIN (not ANALYZE)."""
    n = 0

    def repl(_m: re.Match[str]) -> str:
        nonlocal n
        n += 1
        return str(n)

    return PLACEHOLDER_RE.sub(repl, sql)


def qualify_schema(sql: str, schema: str = DEFAULT_SCHEMA) -> str:
    """Prefix bare FROM/JOIN tables with schema when missing (local YB)."""
    money = money_tables()

    def repl(m: re.Match[str]) -> str:
        sch, tbl = m.group(1), m.group(2)
        if sch:
            return m.group(0)
        if tbl.lower() in money or tbl.lower().startswith("loan_"):
            kw = m.group(0).split()[0]
            return f"{kw} {schema}.{tbl}"
        return m.group(0)

    return TABLE_FROM_RE.sub(repl, sql)


def tables_in_sql(sql: str) -> set[str]:
    return {m.group(2).lower() for m in TABLE_FROM_RE.finditer(sql)}


def run_explain(
    sql: str,
    *,
    db: str = "local",
    qa: int | None = None,
) -> tuple[int, str]:
    """Run plain EXPLAIN (COSTS ON). DML allowed under EXPLAIN (no ANALYZE)."""
    bound = bind_placeholders(sql.strip().rstrip(";"))
    bound = qualify_schema(bound)
    kind = bound.split(None, 1)[0].upper() if bound else ""
    if kind in {"UPDATE", "DELETE", "INSERT"}:
        # Plain EXPLAIN — no execution. Optional rollback wrap unused (EXPLAIN alone is safe).
        explain_sql = f"EXPLAIN (COSTS ON) {bound}"
    else:
        explain_sql = f"EXPLAIN (COSTS ON) {bound}"

    if qa is not None:
        script = ROOT / "scripts" / f"db-qa{qa}.sh"
        if not script.is_file():
            return 2, f"missing {script.name}"
        cmd = ["bash", str(script), "--sql", explain_sql]
    else:
        cmd = ["bash", str(ROOT / "scripts" / "db-local.sh"), "--sql", explain_sql]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=str(ROOT))
    except OSError as e:
        return 2, str(e)
    out = (r.stdout or "") + (r.stderr or "")
    return r.returncode, out


def verdict_from_plan(plan_text: str, sql: str) -> tuple[str, str]:
    """PASS / WARN / FAIL heuristics + short detail."""
    money = money_tables()
    tables = tables_in_sql(sql)
    money_hit = tables & money
    seq = bool(SEQ_SCAN_RE.search(plan_text))
    idx = bool(INDEX_SCAN_RE.search(plan_text))
    nest = bool(NESTLOOP_RE.search(plan_text))
    costs = [float(m.group(1)) for m in COST_RE.finditer(plan_text)]
    max_cost = max(costs) if costs else 0.0

    if seq and money_hit:
        return (
            "FAIL",
            f"Seq Scan on money table(s) {sorted(money_hit)} (cost≈{max_cost:.0f})",
        )
    if seq and max_cost >= 50:
        return "FAIL", f"Seq Scan high cost≈{max_cost:.0f} tables={sorted(tables) or '?'}"
    if nest and seq and max_cost >= 20:
        return "FAIL", f"Nested Loop + Seq Scan cost≈{max_cost:.0f}"
    if nest and max_cost >= 100:
        return "WARN", f"Nested Loop cost≈{max_cost:.0f} — review join order"
    if seq and not idx:
        return "WARN", f"Seq Scan (cost≈{max_cost:.0f}) on {sorted(tables) or 'unknown'}"
    if idx and not seq:
        return "PASS", "Index access plan"
    if idx and seq:
        return "WARN", "Mixed Index + Seq Scan — check join/filter"
    return "PASS", "Plan OK"


def check_reuse_for_new_query(touches: list[dict], disc: dict | None) -> list[str]:
    """FAIL when @Query/nativeQuery changed without reuse ladder proof (reuse_query_gate)."""
    needs = [
        t
        for t in touches
        if set(t.get("signals") or []) & {"@Query", "nativeQuery", "finder-signature"}
    ]
    if not needs:
        return []
    by_rel = {}
    for t in needs:
        _repo, rel = _repo_rel(t["file"])
        by_rel[rel] = t.get("diff") or ""
        by_rel[t["file"]] = t.get("diff") or ""

    def _getter(repo: str, relpath: str) -> str:
        if relpath in by_rel:
            return by_rel[relpath]
        key = f"{repo}/{relpath}" if repo else relpath
        return by_rel.get(key, "")

    pending = {"files": [t["file"] for t in needs]}
    return rqg.check(pending, disc or {}, root=ROOT, diff_getter=_getter)


def plan_excerpt(plan_text: str, limit: int = 12) -> str:
    lines = [
        ln.rstrip()
        for ln in plan_text.splitlines()
        if ln.strip() and "QUERY PLAN" not in ln and not ln.strip().startswith("---")
        and not re.match(r"^\(\d+ rows?\)$", ln.strip())
    ]
    return "\n".join(lines[:limit])


def save_evidence(label: str, sql: str, plan: str, verdict: str) -> Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE_DIR / f"{label.replace('/', '_')[:80]}.txt"
    path.write_text(
        f"# query-plan-gate {_utc()} verdict={verdict}\nSQL:\n{sql}\n\nPLAN:\n{plan}\n",
        encoding="utf-8",
    )
    return path


def append_self_report(runs: int, warns: int, fails: int) -> None:
    line = f"- query-gate runs={runs} WARN={warns} FAIL={fails} ({_utc()[:10]})"
    if not SELF_REPORT.is_file():
        SELF_REPORT.write_text("# SELF-REPORT\n\n" + line + "\n", encoding="utf-8")
        return
    text = SELF_REPORT.read_text(encoding="utf-8")
    # Replace prior query-gate line if present
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("- query-gate runs=")]
    lines.append(line)
    SELF_REPORT.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def run_gate(
    *,
    files: list[str] | None = None,
    sqls: list[str] | None = None,
    db: str = "local",
    qa: int | None = None,
    disc: dict | None = None,
    label: str = "run",
    fail_warn: bool = False,
) -> dict[str, Any]:
    touches = collect_query_touches(files or []) if files is not None else []
    if files is None and sqls is None:
        files = pending_files()
        touches = collect_query_touches(files)

    result: dict[str, Any] = {
        "built_at": _utc(),
        "verdict": "SKIPPED",
        "reason": "",
        "items": [],
        "reuse_errors": [],
        "runs": 0,
        "warns": 0,
        "fails": 0,
    }

    if sqls:
        explain_list = [{"file": label, "signals": ["cli"], "sqls": sqls}]
    else:
        explain_list = touches

    if not explain_list and not sqls:
        result["reason"] = "no query_touched files"
        RESULT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return result

    reuse_errs = check_reuse_for_new_query(touches, disc) if touches else []
    result["reuse_errors"] = reuse_errs

    worst = "PASS"
    items: list[dict] = []
    for touch in explain_list:
        for i, raw_sql in enumerate(touch.get("sqls") or []):
            result["runs"] += 1
            rc, out = run_explain(raw_sql, db=db, qa=qa)
            if rc != 0:
                v, detail = "WARN", f"EXPLAIN failed rc={rc}: {out[:180]}"
            else:
                v, detail = verdict_from_plan(out, raw_sql)
            excerpt = plan_excerpt(out)
            ev = save_evidence(f"{label}_{Path(touch['file']).stem}_{i}", raw_sql, excerpt, v)
            items.append(
                {
                    "file": touch["file"],
                    "verdict": v,
                    "detail": detail,
                    "excerpt": excerpt,
                    "evidence": str(ev.relative_to(ROOT)),
                    "sql_preview": raw_sql[:160],
                }
            )
            if v == "FAIL":
                result["fails"] += 1
                worst = "FAIL"
            elif v == "WARN":
                result["warns"] += 1
                if worst != "FAIL":
                    worst = "WARN"

    if not items and touches:
        # Query signals without extractable SQL — still require reuse proof; plan = WARN
        worst = "WARN"
        result["warns"] += 1
        result["reason"] = "query signals but no extractable SQL — document EXPLAIN manually"
        items.append(
            {
                "file": touches[0]["file"],
                "verdict": "WARN",
                "detail": result["reason"],
                "signals": touches[0].get("signals"),
            }
        )

    if reuse_errs:
        worst = "FAIL"
        result["fails"] += 1
        result["reason"] = "reuse_query proof missing/incomplete for new/changed @Query"

    if fail_warn and worst == "WARN":
        worst = "FAIL"

    result["verdict"] = worst
    result["items"] = items
    RESULT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    append_self_report(result["runs"], result["warns"], result["fails"])
    return result


def format_report(result: dict) -> str:
    lines = [
        f"query-plan-gate: {result.get('verdict')} "
        f"runs={result.get('runs')} WARN={result.get('warns')} FAIL={result.get('fails')}"
    ]
    if result.get("reason"):
        lines.append(f"  reason: {result['reason']}")
    for err in result.get("reuse_errors") or []:
        lines.append(f"  reuse: {err}")
    for it in result.get("items") or []:
        lines.append(f"  [{it.get('verdict')}] {it.get('file')}: {it.get('detail')}")
        if it.get("excerpt"):
            for el in str(it["excerpt"]).splitlines()[:6]:
                lines.append(f"    | {el}")
        if it.get("evidence"):
            lines.append(f"    evidence: {it['evidence']}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Query plan gate (EXPLAIN on query_touched)")
    ap.add_argument("--from-pending", action="store_true")
    ap.add_argument("--paths", nargs="*", default=[])
    ap.add_argument("--sql", action="append", default=[], help="Direct SQL to EXPLAIN (proof/cli)")
    ap.add_argument("--label", default="run")
    ap.add_argument("--qa", type=int, default=None, help="Optional QA N for SELECT EXPLAIN")
    ap.add_argument("--check-touched", action="store_true", help="Exit 0 if query_touched else 1")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fail-warn", action="store_true")
    ap.add_argument(
        "--disc",
        default="",
        help="Path to ship-discipline JSON (reuse_query block); default .cursor/.ship-discipline.json",
    )
    args = ap.parse_args()

    if args.check_touched:
        files = args.paths or pending_files()
        ok = query_touched(files)
        print("query_touched=yes" if ok else "query_touched=no")
        return 0 if ok else 1

    disc = {}
    disc_path = Path(args.disc) if args.disc else ROOT / ".cursor" / ".ship-discipline.json"
    if disc_path.is_file():
        try:
            disc = json.loads(disc_path.read_text(encoding="utf-8"))
        except Exception:
            disc = {}

    files: list[str] | None
    if args.sql:
        files = []
        result = run_gate(
            files=[],
            sqls=args.sql,
            qa=args.qa,
            disc=disc,
            label=args.label,
            fail_warn=args.fail_warn,
        )
    else:
        files = args.paths if args.paths else (pending_files() if args.from_pending else pending_files())
        if not query_touched(files):
            result = {
                "built_at": _utc(),
                "verdict": "SKIPPED",
                "reason": "no query_touched in scope",
                "items": [],
                "runs": 0,
                "warns": 0,
                "fails": 0,
            }
            RESULT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        else:
            result = run_gate(
                files=files,
                qa=args.qa,
                disc=disc,
                label=args.label,
                fail_warn=args.fail_warn,
            )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_report(result))

    if result.get("verdict") == "FAIL":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
