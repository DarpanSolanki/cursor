#!/usr/bin/env python3
"""
Cross-layer learning — KG ↔ test map ↔ FTG ↔ skills share facts via learning_bus + JSONL.

All layers read/write through this module; skills never duplicate state.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
FLOW = ROOT / "cursor-bundle/flow-test"
REGISTRY = ROOT / "scripts/testing/registry.json"
LEARNINGS = ROOT / "cursor-bundle/brain/testing/learnings.jsonl"
KG = ROOT / "cursor-bundle/kg/bin/kg.py"


def _load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def coverage_for_api(api: str) -> dict | None:
    for row in _load_jsonl(FLOW / "test_coverage.jsonl"):
        if row.get("api") == api:
            return row
    return None


def map_cases_for_api(api: str) -> list[dict]:
    return [r for r in _load_jsonl(FLOW / "test_map.jsonl") if r.get("api") == api]


def ftg_for_api(api: str) -> list[dict]:
    return [r for r in _load_jsonl(FLOW / "flows.jsonl") if r.get("request") == api]


def kg_query(cmd: str, *args: str, limit: int = 2500) -> str:
    if not KG.is_file():
        return "(kg.py missing)"
    try:
        p = subprocess.run(
            [sys.executable, str(KG), "--no-drift-check", cmd, *args],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=45,
        )
        out = (p.stdout or p.stderr or "").strip()
        return out[:limit] if out else f"(empty rc={p.returncode})"
    except Exception as ex:
        return f"(kg error: {ex})"


def learnings_for_api(api: str, limit: int = 8) -> list[dict]:
    rows = []
    if not LEARNINGS.is_file():
        return rows
    for line in LEARNINGS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if o.get("kind") == "meta":
            continue
        a = o.get("api") or "*"
        if a in ("*", api) or api.lower() in a.lower():
            rows.append(o)
    return rows[-limit:]


def bus_for_api(api: str, limit: int = 5) -> list[dict]:
    sys.path.insert(0, str(ROOT / "scripts/testing"))
    try:
        from learning_bus import load_events
        return [
            e for e in load_events(limit=100)
            if e.get("api") == api or (e.get("meta") or {}).get("api") == api
        ][-limit:]
    except Exception:
        return []


def unified_orient(api: str) -> str:
    """Single proof-backed view: KG structure + test proof + learnings."""
    lines = [
        f"# Unified orient: `{api}`",
        "",
        "> KG = structure · test_coverage = proof · orchestration XML + db-local = behaviour truth",
        "",
        "## KG spine",
        "",
        "### Flow",
        "```",
        kg_query("flow", api),
        "```",
        "",
        "### DB footprint",
        "```",
        kg_query("crud", api, limit=1800),
        "```",
        "",
        "### Silent surfaces (why)",
        "```",
        kg_query("why", api, limit=2000),
        "```",
        "",
        "### Precedents (cases)",
        "```",
        kg_query("cases", api, limit=1200),
        "```",
        "",
        "## Test intelligence",
    ]
    cov = coverage_for_api(api)
    if cov:
        lines.extend([
            f"- **Footprint best:** {cov.get('footprint_best')}",
            f"- **FTG:** {', '.join(cov.get('ftg_ids') or [])}",
            f"- **ntest cases:** {', '.join(cov.get('ntest_cases') or [])}",
            f"- **unit tests:** {', '.join(cov.get('unit_tests') or [])}",
            f"- **gaps:** {cov.get('gaps') or []}",
            f"- **tiers:** {', '.join(cov.get('tiers') or [])}",
        ])
    else:
        lines.append("- No test_coverage row — run `sync-test-intelligence.sh`")

    ftgs = ftg_for_api(api)
    if ftgs:
        lines.append("\n### FTG flows")
        for f in ftgs[:5]:
            tests = f.get("tests") or {}
            lines.append(
                f"- `{f['id']}` tier={f.get('tier')} coverage={f.get('coverage')} "
                f"({len(tests.get('unit') or [])}u/{len(tests.get('ntest') or [])}n)"
            )

    learns = learnings_for_api(api)
    if learns:
        lines.append("\n### Prior learnings")
        for r in learns:
            lines.append(f"- [{r.get('kind')}] {r.get('text')}")

    bus = bus_for_api(api)
    if bus:
        lines.append("\n### Recent learning bus")
        for e in bus:
            lines.append(f"- {e.get('ts')} `{e.get('type')}` {e.get('detail', '')[:80]}")

    lines.extend([
        "",
        "## Next commands",
        f"```bash",
        f"ntest auto {api}",
        f"ntest map --api {api}",
        f"python3 scripts/testing/ftg.py show ftf:...  # from FTG list above",
        f"scripts/db-local.sh --canned 01-loan-status-by-lan --param account_number=$ACCOUNT_NUMBER",
        f"```",
    ])
    return "\n".join(lines)


_SERVICE_REPO = {
    "accounting": "trustt-platform-accounting",
    "los": "trustt-platform-los",
    "actor": "trustt-platform-actor",
    "payments": "trustt-platform-payments",
    "task": "trustt-platform-task",
}


def _service_train(service: str) -> str:
    """Branch the evidence was recorded on — a pass on 3.7.1 says nothing about 3.5.1.1."""
    repo = ROOT / _SERVICE_REPO.get(service, "trustt-platform-accounting")
    if not (repo / ".git").exists():
        return ""
    import subprocess

    out = subprocess.run(
        ["git", "-C", str(repo), "branch", "--show-current"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    return out.stdout.strip()


def record_test_result(
    *,
    api: str,
    case_id: str,
    passed: bool,
    service: str = "accounting",
    body: str = "",
    http_status: int = 0,
) -> None:
    sys.path.insert(0, str(ROOT / "scripts/testing"))
    from learning_bus import append_event

    etype = "test_pass" if passed else "test_fail"
    append_event(
        etype,
        source="ntest",
        api=api,
        detail=f"case={case_id}",
        evidence=f"http={http_status}",
        meta={"case_id": case_id, "service": service, "train": _service_train(service)},
    )
    if not passed and body:
        codes = re.findall(r"\b(?:1[0-9]{5}|[3-9][0-9]{4})\b", body)
        if codes:
            append_event(
                "gotcha",
                source="ntest.auto",
                api=api,
                detail=f"error_codes={','.join(codes[:3])} on case {case_id}",
                evidence=body[:500],
            )


def unified_gaps(*, money_only: bool = False) -> list[dict]:
    gaps: list[dict] = []
    seen: set[str] = set()

    for row in _load_jsonl(FLOW / "test_coverage.jsonl"):
        if money_only and not row.get("money"):
            continue
        if row.get("gaps"):
            key = f"cov:{row['api']}"
            if key not in seen:
                seen.add(key)
                gaps.append({
                    "layer": "test_coverage",
                    "api": row["api"],
                    "detail": row["gaps"],
                    "footprint": row.get("footprint_best"),
                })

    for row in _load_jsonl(FLOW / "flows.jsonl"):
        if money_only and not row.get("money"):
            continue
        if row.get("coverage") == "gap":
            key = f"ftg:{row['id']}"
            if key not in seen:
                seen.add(key)
                tests = row.get("tests") or {}
                has_proof = bool(tests.get("unit") or tests.get("ntest") or tests.get("disburse_regression"))
                if not has_proof:
                    gaps.append({
                        "layer": "ftg",
                        "api": row.get("request"),
                        "detail": [f"coverage=gap", row["id"]],
                        "footprint": "?",
                    })

    # KG test gaps (sample via sqlite if available)
    db = ROOT / "cursor-bundle/kg/data/kg.db"
    if db.is_file():
        try:
            import sqlite3
            c = sqlite3.connect(db)
            q = "SELECT json FROM nodes WHERE kind='test_gap' LIMIT 200"
            for (js,) in c.execute(q):
                o = json.loads(js)
                label = (o.get("label") or "").replace("UNTESTED ", "")
                if money_only and "loan" not in label.lower() and "disburse" not in label.lower():
                    continue
                key = f"kg:{label}"
                if key not in seen:
                    seen.add(key)
                    gaps.append({
                        "layer": "kg_test_gap",
                        "api": label,
                        "detail": ["no FTG proof in KG"],
                        "footprint": "none",
                    })
            c.close()
        except Exception:
            pass

    return gaps


def propagate_learnings_to_hints() -> int:
    """Sync brain learnings → test_hints.jsonl (dedupe)."""
    hints_path = FLOW / "test_hints.jsonl"
    existing: set[str] = set()
    if hints_path.is_file():
        for line in hints_path.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.startswith("#"):
                existing.add(line.strip())
    n = 0
    if not LEARNINGS.is_file():
        return 0
    hints_path.parent.mkdir(parents=True, exist_ok=True)
    if not hints_path.is_file():
        hints_path.write_text("# Test hints — from learnings + learning_bus\n", encoding="utf-8")
    with hints_path.open("a", encoding="utf-8") as fh:
        for line in LEARNINGS.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            if line.strip() in existing:
                continue
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            if o.get("kind") == "meta":
                continue
            row = {"api": o.get("api", "*"), "kind": o.get("kind"), "text": o.get("text", "")}
            s = json.dumps(row, separators=(",", ":"))
            if s not in existing:
                fh.write(s + "\n")
                existing.add(s)
                n += 1
    return n
