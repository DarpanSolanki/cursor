#!/usr/bin/env python3
"""Generate .cursor/workspace-intelligence-state.md — session hub for all skills."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLOW = ROOT / "cursor-bundle/flow-test"
OUT = ROOT / ".cursor/workspace-intelligence-state.md"
MANIFEST = ROOT / "cursor-bundle/brain/skills-manifest.json"


def _count_jsonl(path: Path | str) -> int:
    p = Path(path)
    if not p.is_file():
        return 0
    return sum(1 for l in p.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#"))


def _load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _load_json_path(path: Path) -> list[dict]:
    rows = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def _kg_fresh(fast: bool = False) -> str:
    if fast:
        state = ROOT / ".cursor/workspace-kg-state.md"
        if state.is_file():
            for line in state.read_text(encoding="utf-8").splitlines():
                if "KG FRESH" in line or "KG STALE" in line or line.startswith("KG FRESH") or "FRESH —" in line:
                    return line.strip().strip("`")
            # first freshness block line
            lines = state.read_text(encoding="utf-8").splitlines()
            for i, line in enumerate(lines):
                if line.strip() == "## Freshness" and i + 2 < len(lines):
                    return lines[i + 2].strip().strip("`")
        return "KG state: see .cursor/workspace-kg-state.md (fast path — no subprocess)"
    try:
        r = subprocess.run(
            [sys.executable, str(ROOT / "cursor-bundle/kg/bin/kg.py"), "fresh", "--no-drift-check"],
            capture_output=True, text=True, timeout=15,
        )
        line = (r.stdout or r.stderr or "").strip().split("\n")[0]
        return line or "NOT VERIFIED"
    except Exception as ex:
        return f"NOT VERIFIED — {ex}"


def _footprint_stats() -> tuple[int, int, int]:
    v = p = u = 0
    fp = FLOW / "footprints.jsonl"
    if not fp.is_file():
        return 0, 0, 0
    for line in fp.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        try:
            s = json.loads(line).get("status", "")
            if s == "verified":
                v += 1
            elif s == "partial":
                p += 1
            elif s == "untested":
                u += 1
        except json.JSONDecodeError:
            pass
    return v, p, u


def _top_test_gaps(limit: int = 8) -> list[str]:
    gaps: list[tuple[str, str]] = []
    db = ROOT / "cursor-bundle/kg/data/kg.db"
    if db.is_file():
        try:
            import sqlite3
            c = sqlite3.connect(db)
            rows = c.execute(
                "SELECT json FROM nodes WHERE kind='test_gap' LIMIT 500"
            ).fetchall()
            for (js,) in rows:
                try:
                    o = json.loads(js)
                    label = o.get("label") or o.get("id", "?")
                    repo = o.get("repo", "")
                    gaps.append((repo, label.replace("UNTESTED ", "")))
                except json.JSONDecodeError:
                    pass
            c.close()
        except Exception:
            pass
    if not gaps:
        for line in (FLOW / "loan_flows.jsonl").read_text(encoding="utf-8").splitlines() if (FLOW / "loan_flows.jsonl").is_file() else []:
            if line.startswith("#") or not line.strip():
                continue
            try:
                o = json.loads(line)
                if o.get("money"):
                    gaps.append((o.get("repo", ""), o.get("request", "?")))
            except json.JSONDecodeError:
                pass
    seen: set[str] = set()
    out: list[str] = []
    for repo, req in gaps:
        key = f"{repo}:{req}"
        if key in seen:
            continue
        seen.add(key)
        out.append(f"`{req}` ({repo})")
        if len(out) >= limit:
            break
    return out


def _branch_drift() -> list[str]:
    wm = _load_json(FLOW / "branch_watermark.json")
    bad = []
    for repo, v in (wm.get("repos") or {}).items():
        if not v.get("aligned"):
            bad.append(f"{repo}: {v.get('branch')} @ {v.get('head', '?')[:10]}")
    return bad


def _recent_bus(limit: int = 8) -> list[str]:
    sys.path.insert(0, str(ROOT / "scripts/testing"))
    try:
        from learning_bus import load_signal_events
        rows = load_signal_events(limit=limit)
        out = []
        for r in rows:
            api = r.get("api") or ""
            detail = (r.get("detail") or "")[:60]
            out.append(f"{r.get('ts', '?')} `{r.get('type')}` {api} {detail}".strip())
        return out
    except Exception:
        return []


def _layer_status() -> list[str]:
    sys.path.insert(0, str(ROOT / "scripts/testing"))
    try:
        from sync_engine import is_stale, LAYER_OUTPUTS
        lines = []
        for layer in LAYER_OUTPUTS:
            lines.append(f"- **{layer}:** {'STALE' if is_stale(layer) else 'fresh'}")
        return lines
    except Exception:
        return ["- (run `super-agent.sh status`)"]


def _scan_summary() -> dict:
    m = _load_json(FLOW / "scan_manifest.json")
    return m.get("stats") or {}


def generate(*, fast: bool = False) -> str:
    scan = _scan_summary()
    manifest = _load_json(FLOW / "scan_manifest.json")
    cache_path = ROOT / ".cursor/.intel-cache.json"
    if fast and cache_path.is_file():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            if cache.get("test_map"):
                scan.setdefault("registry_cases", cache["test_map"].get("registry_cases"))
        except json.JSONDecodeError:
            pass
    v, p, u = _footprint_stats()
    drift = _branch_drift()
    skills_n = len(_load_json(MANIFEST).get("skills", []))
    updated = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) if fast else (
        manifest.get("scanned_at") or "run sync-intelligence / write-intelligence-hub"
    )

    lines = [
        "# Workspace intelligence hub (auto-generated — do not edit)",
        "",
        f"Updated: {updated}" + (" (fast cache)" if fast else ""),
        "",
        "## Freshness",
        "```",
        _kg_fresh(fast=fast),
        "```",
        "",
        "## Corroboration",
        "",
    ]
    corro = _load_json(FLOW / "corroboration_last.json")
    if corro:
        lines.append(f"Last run: **{corro.get('score', '?')}** ({corro.get('mode', 'quick')}) · {corro.get('elapsed_s', 0)}s")
        failed = [c for c in (corro.get("checks") or []) if isinstance(c, dict) and not c.get("ok")]
        if failed:
            for c in failed[:5]:
                lines.append(f"- ✗ {c.get('id')}: {c.get('detail')}")
        else:
            lines.append("- ✓ All corroboration checks passed")
    else:
        lines.append("- Run `python3 scripts/testing/corroborate.py --quick`")
    lines.extend([
        "",
        "## Platform map (last scan)",
        "",
        "| Metric | Count |",
        "|--------|------:|",
    ])
    for k, label in [
        ("platform_apis", "Platform APIs"),
        ("loan_flows", "Loan flows"),
        ("batch_jobs", "Batch jobs"),
        ("kafka_entries", "Kafka entries"),
        ("contracts", "Contracts"),
        ("chains", "API chains"),
        ("ftg_flows", "FTG flows"),
    ]:
        val = scan.get(k) or _count_jsonl(FLOW / f"{k.replace('platform_apis', 'platform_map').replace('ftg_flows', 'flows')}.jsonl")
        if k == "platform_apis":
            val = scan.get("platform_apis") or _count_jsonl(FLOW / "platform_map.jsonl")
        elif k == "ftg_flows":
            val = scan.get("ftg_flows") or _count_jsonl(FLOW / "flows.jsonl")
        else:
            val = scan.get(k) or _count_jsonl(FLOW / f"{k}.jsonl" if k != "chains" else "chains.jsonl")
        lines.append(f"| {label} | {val} |")

    lines.extend([
        "",
        f"**Footprints:** {v} verified · {p} partial · {u} untested",
        "",
        "## Test intelligence",
        "",
    ])
    tstats = _load_json_path(FLOW / "test_coverage.jsonl")
    if tstats:
        lines.append(f"| Metric | Count |")
        lines.append(f"|--------|------:|")
        lines.append(f"| Registry cases mapped | {_count_jsonl(FLOW / 'test_map.jsonl')} |")
        lines.append(f"| APIs in coverage matrix | {len(tstats)} |")
        money_gaps = sum(1 for r in tstats if isinstance(r, dict) and r.get("money") and r.get("gaps"))
        lines.append(f"| Money APIs with test gaps | {money_gaps} |")
    else:
        lines.append("Run `scripts/bin/sync-test-intelligence.sh` to build test map.")
    lines.extend([
        "",
        "## Branch drift",
    ])
    if drift:
        lines.append("⚠ Production-accurate chains need alignment:")
        for d in drift[:6]:
            lines.append(f"- {d}")
    else:
        lines.append("✓ Core repos aligned with target branch (see `branch_watermark.json`)")

    gaps = _top_test_gaps()
    lines.extend(["", "## Priority test gaps (money / untested)", ""])
    if gaps:
        for g in gaps:
            lines.append(f"- {g}")
    else:
        lines.append("- Run `python3 cursor-bundle/kg/bin/kg.py test-gaps` after KG rebuild")

    lines.extend([
        "",
        "## Intel layers (fingerprint)",
        "",
    ])
    lines.extend(_layer_status())

    bus = _recent_bus()
    lines.extend(["", "## Recent learning bus (signal events only)", ""])
    if bus:
        for b in bus:
            lines.append(f"- {b}")
    else:
        lines.append("- (empty — use `test-learn.sh` after test failures)")

    lines.extend([
        "",
        "## Session entry (skills)",
        "",
        "1. `cursor-bundle/memory/MEMORY.md`",
        "2. This file",
        "3. `cursor-bundle/brain/CANONICAL-MAP.md`",
        "4. `python3 cursor-bundle/kg/bin/kg.py validate && kg orient <api>`",
        "5. Orchestration XML + `scripts/db-local.sh`",
        "",
        f"**Skills registered:** {skills_n} — see `cursor-bundle/brain/SKILLS-INDEX.md`",
        "",
        "## Commands",
        "",
        "```bash",
        "scripts/bin/super-agent.sh session",
        "scripts/bin/super-agent.sh sync          # fast incremental",
        "scripts/bin/super-agent.sh sync --full   # heavy — branch/orch drift only",
        "scripts/bin/workspace-sanity.sh --fast",
        "ntest map stats | ntest smoke --tier smoke",
        "scripts/bin/platform-scan.sh --with-kg",
        "```",
        "",
        "Rule: `.cursor/rules/30-kg-discipline.md` — KG orients; code + DB decide.",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--write", action="store_true", help="Write .cursor/workspace-intelligence-state.md")
    p.add_argument("--fast", action="store_true", help="Skip slow kg fresh subprocess; use cached state")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    text = generate(fast=args.fast)
    if args.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(text, encoding="utf-8")
        sys.path.insert(0, str(ROOT / "scripts/testing"))
        try:
            from learning_bus import append_event
            append_event("hub_refresh", source="intelligence_hub.py", detail=str(OUT))
        except Exception:
            pass
        print(f"Wrote {OUT.relative_to(ROOT)}")
    if args.json:
        print(json.dumps({"path": str(OUT), "lines": len(text.splitlines())}))
    elif not args.write:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
