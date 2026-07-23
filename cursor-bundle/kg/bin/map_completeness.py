#!/usr/bin/env python3
"""
map_completeness.py — per-kind map completeness vs disk (Upgrade 10).

Writes:
  .cursor/kg-map-completeness.json
  appends a line into weekly SELF-REPORT when --self-report

Exit 0 always for metrics; --doctor-warn exits 1 on regression vs previous JSON.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DB = ROOT / "cursor-bundle/kg/data/kg.db"
CFG = ROOT / "cursor-bundle/kg/build_config.json"
# Fallback if config lives beside extractors (legacy)
if not CFG.is_file():
    CFG = ROOT / "cursor-bundle/kg/bin/build_config.json"
OUT = ROOT / ".cursor/kg-map-completeness.json"
SELF = ROOT / "cursor-bundle/memory/SELF-REPORT.md"


def _load_cfg():
    if not CFG.is_file():
        return {}
    return json.loads(CFG.read_text(encoding="utf-8"))


def _disk_requests(repo: Path) -> set[str]:
    names: set[str] = set()
    for xml in repo.rglob("*.xml"):
        s = str(xml)
        if "/build/" in s or "/.git/" in s:
            continue
        if "orchestration" not in s and not s.endswith("_orc.xml"):
            continue
        try:
            txt = xml.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in re.finditer(r"<Request\s+[^>]*\bname\s*=\s*\"([^\"]+)\"", txt):
            names.add(m.group(1))
    return names


def _disk_tables(repo: Path) -> set[str]:
    names: set[str] = set()
    for java in repo.rglob("*.java"):
        s = str(java)
        if "/build/" in s or "/test/" in s:
            continue
        try:
            txt = java.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in re.finditer(r'@Table\s*\(\s*name\s*=\s*"([^"]+)"', txt):
            names.add(m.group(1))
    return names


def measure() -> dict:
    cfg = _load_cfg()
    excluded = {e["repo"] for e in cfg.get("exclude_from_orch_coverage", [])}
    c = sqlite3.connect(DB) if DB.is_file() else None
    repos = []
    for d in sorted(ROOT.iterdir()):
        if not d.is_dir() or not (d / ".git").is_dir():
            continue
        if not (d.name.startswith("trustt-") or d.name.startswith("novopay-")):
            continue
        repos.append(d.name)

    per_repo = {}
    totals = {"request": [0, 0], "table": [0, 0], "doc": [0, 0], "topic": [0, 0], "scheduler": [0, 0]}
    for name in repos:
        if name in excluded:
            per_repo[name] = {"excluded": True, "reason": next(
                (e["reason"] for e in cfg.get("exclude_from_orch_coverage", []) if e["repo"] == name), ""
            )}
            continue
        repo = ROOT / name
        disk_req = _disk_requests(repo)
        disk_tbl = _disk_tables(repo)
        kg_req = kg_tbl = 0
        if c:
            kg_req = c.execute(
                "SELECT count(*) FROM nodes WHERE kind='request' AND repo=?", (name,)
            ).fetchone()[0]
            kg_tbl = c.execute(
                "SELECT count(*) FROM nodes WHERE kind='table' AND repo=?", (name,)
            ).fetchone()[0]
        per_repo[name] = {
            "request": {"kg": kg_req, "disk": len(disk_req)},
            "table": {"kg": kg_tbl, "disk": len(disk_tbl)},
        }
        totals["request"][0] += kg_req
        totals["request"][1] += len(disk_req)
        totals["table"][0] += kg_tbl
        totals["table"][1] += len(disk_tbl)

    if c:
        totals["doc"][0] = c.execute("SELECT count(*) FROM nodes WHERE kind='doc'").fetchone()[0]
        totals["topic"][0] = c.execute("SELECT count(*) FROM nodes WHERE kind='topic'").fetchone()[0]
        totals["scheduler"][0] = c.execute("SELECT count(*) FROM nodes WHERE kind='scheduler'").fetchone()[0]
        # disk for doc = same roots the docs extractor indexes (cap pct ≤100)
        doc_roots = [
            ROOT / "cursor-bundle/brain",
            ROOT / ".cursor",
            ROOT / "system_brain",
            ROOT / ".cursor/skills",
        ]
        disk_docs = 0
        seen_docs: set[str] = set()
        for root in doc_roots:
            if not root.is_dir():
                continue
            for p in root.rglob("*.md"):
                try:
                    rel = str(p.relative_to(ROOT))
                except ValueError:
                    continue
                if rel in seen_docs or "/node_modules/" in rel:
                    continue
                seen_docs.add(rel)
                disk_docs += 1
        totals["doc"][1] = disk_docs
        # schedulers: registry backtick beans (approx denominator)
        reg = ROOT / ".cursor/scheduler-registry.md"
        if reg.is_file():
            txt = reg.read_text(encoding="utf-8", errors="replace")
            beans = set(re.findall(
                r"`([A-Za-z][A-Za-z0-9_]*(?:Job|Batch|Scheduler|ConfigService|Executor|Config)[A-Za-z0-9_]*)`",
                txt,
            ))
            beans |= set(re.findall(
                r"`(AutoScheduler|processJobs|ThreadPoolTaskScheduler|ScheduleBatchGroupExecutor)`",
                txt,
            ))
            totals["scheduler"][1] = max(len(beans), totals["scheduler"][0])
        else:
            totals["scheduler"][1] = totals["scheduler"][0]
        # topics: no stable disk inventory — report kg count; pct N/A (use 100 when present)
        totals["topic"][1] = totals["topic"][0]

    def pct(n, d):
        if d == 0:
            return None
        return round(min(100.0, 100.0 * n / d), 1)

    kinds = {}
    for k, (n, d) in totals.items():
        kinds[k] = {"kg": n, "disk": d, "pct": pct(n, d) if d else (100.0 if n else 0.0)}

    # Overall = mean of request+table only (orch/model SoT). Doc/topic/sched are inventory signals.
    overall_nums = [kinds[k]["pct"] for k in ("request", "table") if kinds[k]["pct"] is not None]
    overall = round(sum(overall_nums) / len(overall_nums), 1) if overall_nums else 0.0

    return {
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "overall_pct": overall,
        "kinds": kinds,
        "per_repo": per_repo,
        "excluded": sorted(excluded),
    }


def doctor_warn(prev: dict | None, cur: dict) -> list[str]:
    warns = []
    if not prev:
        return warns
    po, co = prev.get("overall_pct", 0), cur.get("overall_pct", 0)
    if co + 0.5 < po:
        warns.append(f"map-completeness regression overall {po}% → {co}%")
    for k in ("request", "table", "doc", "topic"):
        pk = (prev.get("kinds") or {}).get(k, {}).get("pct")
        ck = (cur.get("kinds") or {}).get(k, {}).get("pct")
        if pk is not None and ck is not None and ck + 1.0 < pk:
            warns.append(f"map-completeness {k} {pk}% → {ck}%")
    return warns


def main(argv: list[str]) -> int:
    cur = measure()
    prev = None
    if OUT.is_file():
        try:
            prev = json.loads(OUT.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            prev = None
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(cur, indent=2), encoding="utf-8")
    line = (
        f"map-completeness: overall={cur['overall_pct']}% "
        f"req={cur['kinds']['request']['pct']}% "
        f"table={cur['kinds']['table']['pct']}% "
        f"doc={cur['kinds']['doc']['kg']}/{cur['kinds']['doc']['disk']} "
        f"topic={cur['kinds']['topic']['kg']} sched={cur['kinds']['scheduler']['kg']} "
        f"excluded={len(cur['excluded'])}"
    )
    print(line)
    if "--self-report" in argv and SELF.is_file():
        block = f"\n## KG map-completeness\n- {line}\n- measured: {cur['built_at']}\n"
        txt = SELF.read_text(encoding="utf-8")
        if "KG map-completeness" in txt:
            txt = re.sub(
                r"\n## KG map-completeness\n(?:.*\n)*?(?=\n## |\Z)",
                block,
                txt,
                count=1,
            )
        else:
            txt = txt.rstrip() + "\n" + block
        SELF.write_text(txt, encoding="utf-8")
    if "--doctor-warn" in argv:
        warns = doctor_warn(prev, cur)
        for w in warns:
            print(f"WARN {w}")
        return 1 if warns else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
