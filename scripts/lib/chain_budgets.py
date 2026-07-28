#!/usr/bin/env python3
"""Ship-chain time budgets — derived from registry ship_baseline + history caps."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "scripts/testing/registry.json"
INVARIANTS = "flowtest.invariants_universal"
SMOKE_READ = "accounting.read_smoke"

# Step ceilings when no history (seconds)
_DEFAULT_STEP = {
    "stack-doctor": 120,
    "kg-validate": 60,
    "ntest-validate": 90,
    "gradle-build": 600,
    "ship-discipline": 30,
    "acceptance-coverage": 30,
    "ship-knowledge-gate": 180,
    "ntest-case": 120,
    "workspace-close-total": 7200,
    "ship-loop-total": 5400,
}

# Generous cap multiplier over planned wall
_WALL_CAP_MULT = 2.5
_WALL_CAP_MIN = 300
_WALL_CAP_MAX = 7200


def _load_registry() -> dict:
    if not REGISTRY.is_file():
        return {}
    try:
        return json.loads(REGISTRY.read_text(encoding="utf-8"))
    except Exception:
        return {}


def case_wall_s(case_id: str, reg: dict | None = None) -> int:
    reg = reg if reg is not None else _load_registry()
    meta = reg.get(case_id) or {}
    bl = meta.get("ship_baseline") or {}
    if bl.get("wall_s"):
        return int(bl["wall_s"])
    if case_id == INVARIANTS:
        return 90  # dual snapshot_invariants ~60–80s wall
    if case_id == SMOKE_READ:
        return 20
    if case_id.startswith("health."):
        return 8
    if case_id.startswith("dcf."):
        return 600
    if case_id.startswith("dpic.ud_compliance") or case_id.startswith("dpic.go_live"):
        return 600  # multi-phase EOD + booking on local portfolio
    if case_id.startswith("dpic.") or case_id.startswith("batch.dpi"):
        return 180  # typical DPI e2e / batch wait
    if meta.get("type") == "flow":
        return 90
    return 120


def plan_wall_s(case_ids: list[str], reg: dict | None = None) -> int:
    reg = reg if reg is not None else _load_registry()
    return sum(case_wall_s(c, reg) for c in case_ids if c)


def step_budget(step: str, *, cases: list[str] | None = None) -> int:
    """Derived budget for a named chain step."""
    if step == "ntest-case" and cases:
        cid = cases[0] if len(cases) == 1 else ""
        if cid:
            wall = case_wall_s(cid)
            return int(min(_WALL_CAP_MAX, max(_WALL_CAP_MIN, wall * _WALL_CAP_MULT)))
    if step == "ship-loop-total" and cases:
        wall = plan_wall_s(cases)
        extra = 600 + len(cases) * 30  # gradle + validate overhead
        return int(min(_WALL_CAP_MAX, max(_WALL_CAP_MIN, (wall + extra) * 1.2)))
    return _DEFAULT_STEP.get(step, 300)


def total_ceiling(case_ids: list[str]) -> int:
    return step_budget("ship-loop-total", cases=case_ids)


def heartbeat_line(label: str, elapsed: float, budget: int) -> str:
    return f"HEARTBEAT still running {label} elapsed={int(elapsed)}s budget={budget}s"


def run_with_timeout(
    cmd: list[str],
    *,
    budget_s: int,
    label: str = "",
    cwd: str | Path | None = None,
    env: dict | None = None,
) -> int:
    """Run subprocess with timeout; on expiry kill tree and dump actionable FAIL."""
    label = label or " ".join(cmd[:3])
    started = time.time()
    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd) if cwd else None,
            env=proc_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except OSError as ex:
        print(f"chain_budgets FAIL: cannot start {label}: {ex}", file=sys.stderr)
        return 127

    last_lines: list[str] = []
    next_hb = started + 15
    while True:
        if proc.stdout:
            line = proc.stdout.readline()
            if line:
                line = line.rstrip("\n")
                print(line, flush=True)
                last_lines.append(line)
                if len(last_lines) > 40:
                    last_lines.pop(0)
        rc = proc.poll()
        now = time.time()
        elapsed = now - started
        if rc is not None:
            return int(rc)
        if now >= next_hb:
            print(heartbeat_line(label, elapsed, budget_s), flush=True)
            next_hb = now + 15
        if elapsed > budget_s:
            proc.kill()
            try:
                proc.wait(timeout=5)
            except Exception:
                pass
            print(
                f"chain_budgets TIMEOUT: {label} exceeded {budget_s}s — killed",
                file=sys.stderr,
            )
            print("--- last output ---", file=sys.stderr)
            for ln in last_lines[-15:]:
                print(f"  {ln}", file=sys.stderr)
            return 124
        time.sleep(0.2)


def main() -> int:
    ap = argparse.ArgumentParser(description="Chain step budgets")
    ap.add_argument("step", nargs="?", default="ship-loop-total")
    ap.add_argument("--case", action="append", default=[], help="ntest case id(s)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    cases = args.case or []
    if args.step == "plan-wall" and cases:
        wall = plan_wall_s(cases)
        out = {"wall_s": wall, "budget_s": step_budget("ship-loop-total", cases=cases)}
    elif args.step == "case-wall" and cases:
        reg = _load_registry()
        out = {c: case_wall_s(c, reg) for c in cases}
    else:
        out = {"step": args.step, "budget_s": step_budget(args.step, cases=cases or None)}
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(out.get("budget_s", out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
