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


def cmd_orient(args: argparse.Namespace) -> int:
    if args.fast:
        sys.path.insert(0, str(ROOT / "scripts/testing"))
        from cross_learn import coverage_for_api, ftg_for_api, learnings_for_api, bus_for_api, kg_query
        api = args.api
        parts = [f"# Unified orient (fast): `{api}`\n"]
        parts.append("```\n" + kg_query("flow", api, limit=1200) + "\n```\n")
        cov = coverage_for_api(api)
        if cov:
            parts.append(f"**Test:** footprint={cov.get('footprint_best')} gaps={cov.get('gaps')}\n")
        for r in learnings_for_api(api, 5):
            parts.append(f"- [{r.get('kind')}] {r.get('text')}\n")
        print("".join(parts))
        return 0
    print(unified_orient(args.api))
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


def main() -> int:
    p = argparse.ArgumentParser(description="Super agent — unified intelligence")
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("session", help="Fast session bootstrap (default)")
    ps.add_argument("--verbose", action="store_true")
    ps.add_argument("--full", action="store_true", help="Alias verbose session")
    ps.add_argument("--quiet", action="store_true")

    po = sub.add_parser("orient")
    po.add_argument("api")
    po.add_argument("--fast", action="store_true", help="Shorter KG output, skip crud/why")

    pt = sub.add_parser("trace", help="Alias for orient --fast")
    pt.add_argument("api")
    pt.add_argument("--fast", action="store_true", default=True)

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

    ph = sub.add_parser("handle", help="Delegate to workspace autopilot task")
    ph.add_argument("words", nargs="+")

    args = p.parse_args()
    if args.cmd == "session":
        return cmd_session(args)
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
    if args.cmd == "handle":
        return cmd_handle(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
