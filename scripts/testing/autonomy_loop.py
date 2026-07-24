#!/usr/bin/env python3
"""Super-agent LEARN close phase + SELF-REPORT weekly (Upgrade 8)."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def learn_close(*, text: str = "", classification: str = "GENERAL") -> dict:
    """After route→plan→execute: capture → propose drafts → backlog (auto_safe unchanged)."""
    import sys

    sys.path.insert(0, str(ROOT / "scripts" / "testing"))
    sys.path.insert(0, str(ROOT / "scripts" / "lib"))
    from learn_lifecycle import capture, propose
    from process_router import stamp_ttl

    out: dict = {"ts": _utc(), "steps": []}
    lid = f"learn.{_utc()[:10].replace('-', '')}.{classification.lower().replace('/', '_')}"
    detail = (text or classification)[:200]
    capture(detail=detail, learning_id=lid, meta={"classification": classification})
    out["steps"].append({"op": "captured", "id": lid})

    try:
        import registry_proposals as rp

        draft = rp.draft_from_ship(force=False)
        if draft:
            propose(
                learning_id=lid,
                detail=f"registry draft {draft.get('id')}",
                api=(draft.get("case") or {}).get("api"),
                kind="registry_proposal",
            )
            out["steps"].append({"op": "proposed", "id": draft.get("id")})
        else:
            # still propose a KB/rule note stub for the learning id
            propose(learning_id=lid, detail="KB/rule-change PROPOSAL queued for human", kind="kb_note")
            out["steps"].append({"op": "proposed", "id": f"{lid}.kb"})
    except Exception as exc:  # noqa: BLE001
        out["steps"].append({"op": "propose_skip", "error": str(exc)})

    tier = "SKIP"
    if classification in ("FIX+SHIP", "RELEASE") or "money" in detail.lower():
        tier = "CASES"
    if any(x in detail.lower() for x in ("orch", "processor", "flyway")):
        tier = "FULL"
    out["enrichment_tier"] = tier
    out["steps"].append({"op": "enrichment_decision", "tier": tier})
    out["steps"].append(
        {"op": "backlog", "note": "auto_safe items may self-apply; others queue for human"}
    )
    stamp_ttl("kg_fresh")
    out["learning_id"] = lid
    return out


def wall_clock_log(process_class: str, elapsed_s: float) -> None:
    log = ROOT / "scripts" / "scratch" / "logs" / "task-wallclock.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as f:
        f.write(f"{_utc()} | {process_class} | {elapsed_s:.2f}s\n")
    lines = log.read_text(encoding="utf-8").splitlines()
    if len(lines) > 400:
        log.write_text("\n".join(lines[-400:]) + "\n", encoding="utf-8")


def generate_self_report() -> Path:
    import sys

    sys.path.insert(0, str(ROOT / "scripts" / "lib"))
    sys.path.insert(0, str(ROOT / "scripts" / "testing"))

    mem = ROOT / "cursor-bundle" / "memory"
    mem.mkdir(parents=True, exist_ok=True)
    out = mem / "SELF-REPORT.md"
    archive = mem / "self-reports"
    archive.mkdir(parents=True, exist_ok=True)

    if out.is_file():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        dest = archive / f"SELF-REPORT-{stamp}.md"
        if not dest.is_file():
            shutil.copy2(out, dest)
        old = sorted(archive.glob("SELF-REPORT-*.md"))
        for p in old[:-8]:
            p.unlink(missing_ok=True)

    aa_bytes = 0
    offenders = []
    for p in (ROOT / ".cursor" / "rules").glob("*.mdc"):
        t = p.read_text(encoding="utf-8", errors="ignore")
        if "alwaysApply: true" in t[:500]:
            n = len(t.encode())
            aa_bytes += n
            offenders.append((p.name, n))
    offenders.sort(key=lambda x: -x[1])

    man = json.loads((ROOT / "scripts/lib/acceptance_coverage_manifest.json").read_text())
    enforced = man.get("enforced_domains") or []
    reg = json.loads((ROOT / "scripts/testing/registry.json").read_text())
    money = [c for c, v in reg.items() if isinstance(v, dict) and v.get("smoke_tier") == "money"]
    vm = sum(
        1
        for c in money
        if reg[c].get("verify_mode") or (reg[c].get("acceptance") or {}).get("verify_mode")
    )
    props = {}
    pp = ROOT / "scripts/testing/registry-proposals.json"
    if pp.is_file():
        props = json.loads(pp.read_text())
    proposals = props.get("proposals") or []
    stubs = sum(1 for p in proposals if p.get("source") == "gap_miner")
    drafts = sum(1 for p in proposals if p.get("status") == "draft")

    by_class: dict[str, list[float]] = {}
    wc = ROOT / "scripts/scratch/logs/task-wallclock.log"
    if wc.is_file():
        for ln in wc.read_text().splitlines():
            parts = [x.strip() for x in ln.split("|")]
            if len(parts) >= 3:
                try:
                    by_class.setdefault(parts[1], []).append(float(parts[2].rstrip("s")))
                except ValueError:
                    pass

    def pct(vals: list[float], p: float) -> str:
        if not vals:
            return "n/a (baseline starts now)"
        s = sorted(vals)
        i = min(len(s) - 1, max(0, int(round((p / 100) * (len(s) - 1)))))
        return f"{s[i]:.2f}s"

    hits = misses = gates = 0
    kg_state = ROOT / ".cursor/workspace-kg-state.md"
    if kg_state.is_file():
        for ln in kg_state.read_text().splitlines():
            if "| hit |" in ln:
                hits += 1
            if "| miss |" in ln:
                misses += 1
            if "trigger=gate" in ln:
                gates += 1
    total_hm = hits + misses
    hit_ratio = f"{(100 * hits / total_hm):.0f}%" if total_hm else "n/a"

    try:
        from ntest_telemetry import doctor_report

        flaky = doctor_report()
    except Exception:
        flaky = "n/a"

    soft = 35000
    tax_warn = aa_bytes > soft
    lines = [
        f"# SELF-REPORT — week of {_utc()[:10]}",
        "",
        f"Generated: {_utc()} · Upgrade 8 self-metrics",
        "",
        "## Fixed tax",
        f"- alwaysApply bytes: **{aa_bytes}** / soft ceiling **{soft}**"
        + (" — **WARN BREACH**" if tax_warn else " — OK"),
        "- largest offenders: " + ", ".join(f"{n}={b}" for n, b in offenders[:5]),
        "",
        "## Speed (wall-clock by process class)",
    ]
    for cls in sorted(by_class) or ["question", "read-only-rca", "money-fix"]:
        vals = by_class.get(cls) or []
        lines.append(f"- `{cls}`: p50={pct(vals, 50)} p95={pct(vals, 95)} n={len(vals)}")
    # map-completeness (Upgrade 10)
    map_line = "n/a"
    try:
        import subprocess

        r = subprocess.run(
            [sys.executable, str(ROOT / "cursor-bundle/kg/bin/map_completeness.py")],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        map_line = (r.stdout or "").strip().splitlines()[-1] if r.stdout else "n/a"
    except Exception as e:
        map_line = f"error: {e}"

    # flow-coverage % (F1 ratchet — scripts/testing/flow_coverage.json)
    flow_cov = "n/a"
    try:
        import json as _json

        fc = _json.loads((ROOT / "scripts/testing/flow_coverage.json").read_text(encoding="utf-8"))
        rows = fc.get("flows") or []
        yes = sum(1 for r in rows if (r.get("harness_ready") or "").upper() == "YES")
        flow_cov = f"{yes}/{len(rows)} ({(100.0 * yes / len(rows)) if rows else 0:.1f}%)"
    except Exception as e:
        flow_cov = f"error: {e}"

    lines += [
        "",
        "## KG",
        f"- cache hit ratio (telemetry window): {hit_ratio} (hit={hits} miss={misses})",
        f"- gate hits (PROVISIONAL): {gates} — revisit kg-profiles.md if ≥8/week",
        f"- map-completeness: {map_line}",
        "",
        "## QA bar",
        f"- enforced acceptance domains: **{len(enforced)}/21** — {', '.join(enforced)}",
        f"- money verify_mode coverage: **{vm}/{len(money)}**",
        f"- flow-coverage (live harness YES): **{flow_cov}**",
        f"- proposals: total={len(proposals)} drafts={drafts} gap_stubs={stubs}",
        f"- flaky: {flaky}",
        "",
        "## Env / ratchets",
        "- env-smoke: see `.cursor/workspace-ops-state.md` § Env smoke",
        "- money-cell process ratchet + acceptance enforced_domains ratchet: active",
        "- flow_coverage.json ratchet: harness_ready YES count must not decrease",
        "",
        "## Red flags",
    ]
    flags = []
    if tax_warn:
        flags.append(f"fixed tax {aa_bytes} > {soft}")
    if stubs >= 15:
        flags.append(f"gap stubs still high ({stubs})")
    if gates >= 8:
        flags.append(f"KG gate hits {gates} — consider kg-profiles")
    if not flags:
        flags.append("none")
    for f in flags:
        lines.append(f"- {f}")
    lines.append("")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["learn-close", "self-report", "wall"])
    ap.add_argument("--text", default="")
    ap.add_argument("--class", dest="cls", default="GENERAL")
    ap.add_argument("--elapsed", type=float, default=0.0)
    args = ap.parse_args()
    if args.cmd == "learn-close":
        print(json.dumps(learn_close(text=args.text, classification=args.cls), indent=2))
    elif args.cmd == "self-report":
        p = generate_self_report()
        print(str(p))
    elif args.cmd == "wall":
        import sys

        sys.path.insert(0, str(ROOT / "scripts" / "lib"))
        from process_router import map_class

        wall_clock_log(map_class(args.cls, args.text), args.elapsed)
        print("logged")
