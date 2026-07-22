#!/usr/bin/env python3
"""
Super agent — unified session entry: KG + test KG + skills + learning bus.

Performance tiers:
  session          # fast default (~2–5s) — fingerprint cache, always learn
  sync             # fast incremental — rebuild only stale layers
  sync --full      # heavy — full test + platform sync (minutes)
  sync --full --kg # + KG force rebuild

Self-learning: learning_bus + hints NEVER skipped on any tier.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/testing"))

from cross_learn import propagate_learnings_to_hints, unified_gaps, unified_orient  # noqa: E402
from sync_engine import fast_session, fast_sync, full_sync  # noqa: E402


def cmd_session(args: argparse.Namespace) -> int:
    if args.full:
        r = fast_session(quiet=args.quiet)  # still use engine; --full on session = verbose
    else:
        r = fast_session(quiet=not args.verbose)
    print("## Super agent — session bootstrap\n")
    print(f"**Mode:** {r.get('mode')} · **{r.get('elapsed_s')}s** · learn: {r.get('learn')}\n")
    if not r.get("ok"):
        print("SESSION FAIL — kg validate", file=sys.stderr)
        return 1
    try:
        sys.path.insert(0, str(ROOT / "scripts" / "lib"))
        from process_router import stamp_ttl

        stamp_ttl("kg_fresh")
        stamp_ttl("services")
        print("**TTL stamped:** kg_fresh, services\n")
    except Exception:
        pass
    hub = ROOT / ".cursor/workspace-intelligence-state.md"
    if hub.is_file():
        for line in hub.read_text(encoding="utf-8").splitlines()[:28]:
            print(line)
        print("\n… full hub: .cursor/workspace-intelligence-state.md")
    tm = r.get("cache") or {}
    if tm:
        print(f"\nTest map (cached): {tm}")
    print("\n**Skill:** `.cursor/skills/super-agent/SKILL.md`")
    return 0


def cmd_close(args: argparse.Namespace) -> int:
    """LEARN close: capture → propose → enrichment decision → backlog note."""
    sys.path.insert(0, str(ROOT / "scripts" / "lib"))
    from autonomy_loop import learn_close, wall_clock_log
    from process_router import map_class

    text = " ".join(getattr(args, "words", []) or []) or (args.text or "")
    cls = args.classification or "GENERAL"
    t0 = time.time()
    result = learn_close(text=text, classification=cls)
    elapsed = time.time() - t0
    wall_clock_log(map_class(cls, text), elapsed)
    print("## Super agent — LEARN close\n")
    print(json.dumps(result, indent=2))
    print(f"\n**wall:** {elapsed:.2f}s · enrichment={result.get('enrichment_tier')}")
    return 0


def cmd_orient(args: argparse.Namespace) -> int:
    if args.fast:
        sys.path.insert(0, str(ROOT / "scripts/testing"))
        from cross_learn import coverage_for_api, learnings_for_api, kg_query
        api = args.api
        parts = [f"# Unified orient (fast): `{api}`\n"]
        parts.append("```\n" + kg_query("flow", api, limit=1200) + "\n```\n")
        cov = coverage_for_api(api)
        if cov:
            parts.append(f"**Test:** footprint={cov.get('footprint_best')} gaps={cov.get('gaps')}\n")
        for r in learnings_for_api(api, 5):
            parts.append(f"- [{r.get('kind')}] {r.get('text')}\n")
        print("".join(parts))
        if getattr(args, "base", None):
            print("\n--- fixed-elsewhere (fail-closed) ---")
            cmd = [
                sys.executable,
                str(ROOT / "cursor-bundle/kg/bin/kg.py"),
                "fixed-elsewhere",
                api,
                "--base",
                args.base,
                "--fetch-if-stale",
            ]
            return subprocess.call(cmd, cwd=str(ROOT))
        return 0
    print(unified_orient(args.api))
    if getattr(args, "base", None):
        print("\n--- fixed-elsewhere (fail-closed) ---")
        return subprocess.call(
            [
                sys.executable,
                str(ROOT / "cursor-bundle/kg/bin/kg.py"),
                "fixed-elsewhere",
                args.api,
                "--base",
                args.base,
                "--fetch-if-stale",
            ],
            cwd=str(ROOT),
        )
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    if args.full:
        r = full_sync(with_kg=args.kg, quiet=not args.verbose)
    else:
        r = fast_sync(quiet=not args.verbose)
    print(json.dumps(r, indent=2))
    return 0 if r.get("ok", True) else 1


def cmd_gaps(args: argparse.Namespace) -> int:
    gaps = unified_gaps(money_only=args.money)
    print(f"Unified gaps ({len(gaps)}):\n")
    for g in gaps[:40]:
        print(f"  [{g['layer']:14}] {g['api']:40} {g['detail']}  fp={g.get('footprint')}")
    if len(gaps) > 40:
        print(f"  … +{len(gaps) - 40} more")
    return 0


def cmd_learn(args: argparse.Namespace) -> int:
    from learning_bus import append_event
    from lib.test_learnings import append_learning

    append_learning(
        api=args.api,
        kind=args.kind,
        text=args.text,
        error_code=args.error_code or "",
        correlator=args.key or "",
        value=args.value or "",
    )
    append_event(
        "gotcha",
        source="super_agent.learn",
        api=args.api,
        detail=args.text,
        meta={"kind": args.kind},
    )
    n = propagate_learnings_to_hints()
    # Incremental: mark test_map + hub stale so next fast-sync rebuilds only if needed
    print(json.dumps({
        "ok": True,
        "api": args.api,
        "hints_propagated": n,
        "layers": ["learnings.jsonl", "learning_bus", "test_hints"],
    }))
    return 0


def cmd_classify(args: argparse.Namespace) -> int:
    return subprocess.call(
        ["bash", "scripts/bin/agent-router.sh", "classify", *args.words],
        cwd=str(ROOT),
    )


def cmd_status(_: argparse.Namespace) -> int:
    return subprocess.call(
        [sys.executable, str(ROOT / "scripts/testing/sync_engine.py"), "status"],
        cwd=str(ROOT),
    )


def cmd_loop(_: argparse.Namespace) -> int:
    """Fast intelligence loop: session bootstrap + quick corroborate + status."""
    r = fast_session(quiet=True)
    if not r.get("ok"):
        return 1
    from corroborate import run

    run(mode="quick", emit_bus=False)
    return cmd_status(_)


def cmd_handle(args: argparse.Namespace) -> int:
    msg = " ".join(args.words).strip()
    if not msg:
        print("handle: message required", file=sys.stderr)
        return 2
    return subprocess.call(
        [sys.executable, str(ROOT / "scripts/testing/workspace_autopilot.py"), "task", msg],
        cwd=str(ROOT),
    )


def cmd_clean(args: argparse.Namespace) -> int:
    """Disk + hygiene cleanup — safe for local dev (archived logs, scratch, pycache)."""
    cmd = ["bash", "scripts/bin/workspace-disk-clean.sh"]
    if args.apply:
        cmd.append("--clean")
    if args.verbose:
        cmd.append("--verbose")
    rc = subprocess.call(cmd, cwd=str(ROOT))
    if rc != 0:
        return rc
    if args.apply:
        subprocess.call(
            [sys.executable, str(ROOT / "scripts/testing/sync_engine.py"), "fast-sync", "--quiet"],
            cwd=str(ROOT),
        )
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Super agent — unified intelligence")
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("session", help="Fast session bootstrap (default)")
    ps.add_argument("--verbose", action="store_true")
    ps.add_argument("--full", action="store_true", help="Alias verbose session")
    ps.add_argument("--quiet", action="store_true")

    pclose = sub.add_parser("close", help="LEARN close phase (capture→propose→enrichment)")
    pclose.add_argument("--text", default="")
    pclose.add_argument("--classification", default="GENERAL")
    pclose.add_argument("words", nargs="*", help="optional task text")

    po = sub.add_parser("orient")
    po.add_argument("api")
    po.add_argument("--fast", action="store_true", help="Shorter KG output, skip crud/why")
    po.add_argument(
        "--base",
        help="Reported train branch for fail-closed kg fixed-elsewhere (e.g. mfi_integration_v3.6.1)",
    )

    pt = sub.add_parser("trace", help="Alias for orient --fast")
    pt.add_argument("api")
    pt.add_argument("--fast", action="store_true", default=True)
    pt.add_argument(
        "--base",
        help="Reported train branch for fail-closed kg fixed-elsewhere",
    )

    psy = sub.add_parser("sync", help="Fast incremental sync (default)")
    psy.add_argument("--full", action="store_true", help="Heavy full sync — use after branch/orch change")
    psy.add_argument("--kg", action="store_true", help="With --full: force KG rebuild")
    psy.add_argument("--verbose", action="store_true")

    sub.add_parser("status", help="Fingerprint stale/fresh per layer")

    pg = sub.add_parser("gaps")
    pg.add_argument("--money", action="store_true")
    pl = sub.add_parser("learn")
    pl.add_argument("--api", required=True)
    pl.add_argument("--kind", default="gotcha")
    pl.add_argument("--text", required=True)
    pl.add_argument("--error-code")
    pl.add_argument("--key")
    pl.add_argument("--value")
    pc = sub.add_parser("classify")
    pc.add_argument("words", nargs="+")

    sub.add_parser("loop", help="Session + quick corroborate + status")
    pcor = sub.add_parser("corroborate", help="Cross-layer corroboration score")
    pcor.add_argument("--full", action="store_true")
    pcor.add_argument("--quick", action="store_true", default=True)

    ph = sub.add_parser("handle", help="Delegate to workspace autopilot task")
    ph.add_argument("words", nargs="+")

    pcl = sub.add_parser("clean", help="Audit/reclaim disk — archived service logs, scratch, pycache")
    pcl.add_argument("--apply", action="store_true", help="Run --clean (default is audit only)")
    pcl.add_argument("--verbose", "-v", action="store_true")

    args = p.parse_args()
    if args.cmd == "session":
        return cmd_session(args)
    if args.cmd == "close":
        return cmd_close(args)
    if args.cmd == "orient":
        return cmd_orient(args)
    if args.cmd == "trace":
        args.fast = True
        return cmd_orient(args)
    if args.cmd == "sync":
        return cmd_sync(args)
    if args.cmd == "status":
        return cmd_status(args)
    if args.cmd == "gaps":
        return cmd_gaps(args)
    if args.cmd == "learn":
        return cmd_learn(args)
    if args.cmd == "classify":
        return cmd_classify(args)
    if args.cmd == "loop":
        return cmd_loop(args)
    if args.cmd == "corroborate":
        from corroborate import run as corroborate_run

        mode = "full" if getattr(args, "full", False) else "quick"
        report = corroborate_run(mode=mode, emit_bus=True)
        print(f"corroborate {report.score} ({report.mode}, {report.elapsed_s}s)")
        for c in report.checks:
            mark = "✓" if c.ok else "✗"
            print(f"  {mark} {c.id}: {c.detail}")
        return 0 if report.passed == report.total else 1
    if args.cmd == "handle":
        return cmd_handle(args)
    if args.cmd == "clean":
        return cmd_clean(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
