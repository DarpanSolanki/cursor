#!/usr/bin/env python3
"""
Cross-layer corroboration — read cached artifacts only on --quick (~1–2s).
Full mode adds registry-gaps sample + autopilot verify (~5–15s).
Writes gap_discovered to learning_bus; persists last run to corroboration.jsonl.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLOW = ROOT / "cursor-bundle/flow-test"
CORRO_PATH = FLOW / "corroboration_last.json"
CORRO_LOG = FLOW / "corroboration.jsonl"
STAMP = ROOT / ".cursor/.last-corroborate-run"


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


@dataclass
class Check:
    id: str
    ok: bool
    detail: str = ""
    action: str = ""


@dataclass
class Report:
    mode: str
    score: str
    passed: int
    total: int
    elapsed_s: float
    checks: list[Check] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["checks"] = [asdict(c) for c in self.checks]
        return d


def _kg_state_ok() -> Check:
    state = ROOT / ".cursor/workspace-kg-state.md"
    if not state.is_file():
        return Check("kg_state", False, "missing", "bash scripts/bin/kg-ensure-fresh.sh --quiet")
    text = state.read_text(encoding="utf-8")
    if "STALE" in text.upper() and "FRESH" not in text.split("STALE")[0][-20:]:
        return Check("kg_state", False, "STALE", "bash scripts/bin/kg-switch.sh")
    if "FRESH" in text:
        return Check("kg_state", True, "FRESH")
    return Check("kg_state", True, "present")


def _hooks_ok() -> Check:
    hooks = ROOT / ".cursor/hooks.json"
    if not hooks.is_file():
        return Check("hooks", False, "hooks.json missing", "restore .cursor/hooks.json from repo")
    try:
        h = json.loads(hooks.read_text(encoding="utf-8"))
        starts = [x.get("command", "") for x in h.get("hooks", {}).get("sessionStart", [])]
        after = [x.get("command", "") for x in h.get("hooks", {}).get("afterShellExecution", [])]
        ok = (
            any("intel-session" in c for c in starts)
            and any("post-ntest" in c for c in after)
            and any("kg-session" in c for c in starts)
        )
        return Check(
            "hooks",
            ok,
            f"sessionStart={len(starts)} afterShell={len(after)}",
            "" if ok else "fix hooks.json sessionStart + afterShellExecution",
        )
    except json.JSONDecodeError:
        return Check("hooks", False, "invalid JSON")


def _intel_layers() -> list[Check]:
    sys.path.insert(0, str(ROOT / "scripts/testing"))
    try:
        from sync_engine import is_stale, LAYER_OUTPUTS

        checks: list[Check] = []
        stale = [layer for layer in LAYER_OUTPUTS if is_stale(layer)]
        checks.append(
            Check(
                "intel_layers",
                len(stale) == 0,
                f"stale={stale or 'none'}",
                "bash scripts/bin/super-agent.sh sync" if stale else "",
            )
        )
        return checks
    except Exception as ex:
        return [Check("intel_layers", False, str(ex))]


def _hub_fresh() -> Check:
    hub = ROOT / ".cursor/workspace-intelligence-state.md"
    if not hub.is_file():
        return Check("hub", False, "missing", "python3 scripts/testing/sync_engine.py fast-session --quiet")
    age = int(time.time() - _mtime(hub))
    ok = age < 3600
    return Check(
        "hub",
        ok,
        f"age={age}s",
        "bash scripts/bin/super-agent.sh sync" if not ok else "",
    )


def _registry_ok() -> Check:
    reg = ROOT / "scripts/testing/registry.json"
    if not reg.is_file():
        return Check("registry", False, "missing")
    try:
        raw = json.loads(reg.read_text(encoding="utf-8"))
        n = sum(1 for k, v in raw.items() if not k.startswith("_") and isinstance(v, dict))
        return Check("registry", n > 0, f"{n} cases")
    except json.JSONDecodeError:
        return Check("registry", False, "invalid JSON")


def _test_map_ok() -> Check:
    tm = FLOW / "test_map.jsonl"
    if not tm.is_file():
        return Check("test_map", False, "missing", "bash scripts/bin/sync-test-intelligence.sh --fast")
    n = len(_load_jsonl(tm))
    return Check("test_map", n > 0, f"{n} rows")


def _money_proof_gaps() -> Check:
    gaps = 0
    for row in _load_jsonl(FLOW / "test_coverage.jsonl"):
        if row.get("money") and row.get("gaps"):
            gaps += 1
    ok = gaps < 20
    return Check(
        "money_proof_gaps",
        ok,
        f"{gaps} money APIs with gaps",
        "super-agent.sh gaps --money" if gaps else "",
    )


def _orch_index_ok() -> Check:
    idx = FLOW / "orch_api_index.json"
    if not idx.is_file():
        return Check("orch_index", False, "missing", "python3 scripts/testing/orch_index.py --rebuild")
    try:
        data = json.loads(idx.read_text(encoding="utf-8"))
        return Check("orch_index", True, f"{data.get('count')} apis · money={data.get('money_count')}")
    except json.JSONDecodeError:
        return Check("orch_index", False, "invalid JSON", "python3 scripts/testing/orch_index.py --rebuild")


def _pending_ship() -> Check:
    pending = ROOT / ".cursor/.pending-ship-work.json"
    kg_pending = ROOT / ".cursor/.pending-kg-rebuild"
    parts = []
    if pending.is_file():
        parts.append("ship_work")
    if kg_pending.is_file():
        parts.append("kg_rebuild")
    if parts:
        return Check(
            "pending_work",
            True,
            "+".join(parts),
            "bash scripts/bin/workspace-close.sh --from-pending",
        )
    return Check("pending_work", True, "none")


def _ops_state() -> Check:
    ops = ROOT / ".cursor/workspace-ops-state.md"
    if not ops.is_file():
        return Check("ops_state", False, "missing", "bash scripts/bin/agent-ops.sh preflight")
    age = int(time.time() - _mtime(ops))
    return Check("ops_state", age < 86400, f"age={age}s", "agent-ops.sh preflight" if age >= 86400 else "")


def _bus_recent_failures() -> Check:
    fails = 0
    for row in _load_jsonl(FLOW / "learning_bus.jsonl")[-200:]:
        if row.get("type") in ("test_fail", "sanity_fail"):
            fails += 1
    return Check(
        "bus_failures",
        fails < 5,
        f"{fails} recent fail events (last 200 bus rows)",
        "super-agent.sh gaps --money" if fails >= 5 else "",
    )


def _registry_gap_sample() -> Check:
    sys.path.insert(0, str(ROOT / "scripts/testing"))
    try:
        from orch_index import load_index, registry_gaps

        load_index()
        gaps = registry_gaps(money_only=True)
        n = len(gaps)
        return Check(
            "registry_gaps_money",
            True,
            f"{n} money orch apis without registry case (informational)",
            "ftg.py registry-gaps --money --limit 20" if n > 300 else "",
        )
    except Exception as ex:
        return Check("registry_gaps_money", False, str(ex))


def _autopilot_verify() -> Check:
    try:
        p = subprocess.run(
            [sys.executable, str(ROOT / "scripts/testing/workspace_autopilot.py"), "verify", "--json"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if p.returncode != 0:
            return Check("autopilot", False, "verify failed", "workspace-autopilot.sh verify")
        data = json.loads(p.stdout or "{}")
        ok = data.get("ok", False)
        n = len(data.get("checks") or [])
        return Check("autopilot", ok, f"{n} checks", "" if ok else "workspace-autopilot.sh verify")
    except Exception as ex:
        return Check("autopilot", False, str(ex))


def _cross_branch_tooling() -> Check:
    fwd = ROOT / "scripts/bin/fwd-port.sh"
    train = ROOT / "scripts/lib/branch_train.py"
    if not fwd.is_file() or not os.access(fwd, os.X_OK):
        return Check(
            "cross_branch",
            False,
            "fwd-port.sh missing/not executable",
            "chmod +x scripts/bin/fwd-port.sh",
        )
    if not train.is_file():
        return Check("cross_branch", False, "branch_train.py missing")
    try:
        p = subprocess.run(
            [sys.executable, "-m", "unittest", "scripts.lib.test_branch_train"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ, "PYTHONPATH": str(ROOT / "scripts/lib")},
        )
        if p.returncode != 0:
            return Check(
                "cross_branch",
                False,
                "branch_train tests failed",
                "python3 -m unittest scripts.lib.test_branch_train -v",
            )
    except Exception as ex:
        return Check("cross_branch", False, str(ex))
    return Check("cross_branch", True, "fwd-port + fail-closed fixed-elsewhere tests")


def run(*, mode: str = "quick", emit_bus: bool = True) -> Report:
    t0 = time.time()
    checks: list[Check] = [
        _kg_state_ok(),
        _hooks_ok(),
        *_intel_layers(),
        _hub_fresh(),
        _registry_ok(),
        _test_map_ok(),
        _money_proof_gaps(),
        _orch_index_ok(),
        _pending_ship(),
        _ops_state(),
        _bus_recent_failures(),
        _cross_branch_tooling(),
    ]
    if mode == "full":
        checks.extend([_registry_gap_sample(), _autopilot_verify()])

    passed = sum(1 for c in checks if c.ok)
    total = len(checks)
    actions = []
    seen: set[str] = set()
    for c in checks:
        if c.action and c.action not in seen:
            seen.add(c.action)
            actions.append(c.action)

    report = Report(
        mode=mode,
        score=f"{passed}/{total}",
        passed=passed,
        total=total,
        elapsed_s=round(time.time() - t0, 2),
        checks=checks,
        actions=actions[:6],
    )

    CORRO_PATH.parent.mkdir(parents=True, exist_ok=True)
    CORRO_PATH.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")

    line = json.dumps({
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        **report.to_dict(),
    }, separators=(",", ":"))
    if not CORRO_LOG.is_file():
        CORRO_LOG.write_text("# Corroboration history\n", encoding="utf-8")
    with CORRO_LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")

    if emit_bus:
        sys.path.insert(0, str(ROOT / "scripts/testing"))
        try:
            from learning_bus import append_event

            failed = [c.id for c in checks if not c.ok]
            if failed:
                append_event(
                    "gap_discovered",
                    source="corroborate.py",
                    detail=f"failed={','.join(failed[:5])} score={report.score}",
                )
        except Exception:
            pass

    STAMP.parent.mkdir(parents=True, exist_ok=True)
    STAMP.write_text(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), encoding="utf-8")
    return report


def format_report(r: Report) -> str:
    lines = [
        f"# Corroboration ({r.mode}) — **{r.score}** in {r.elapsed_s}s",
        "",
    ]
    for c in r.checks:
        mark = "✓" if c.ok else "✗"
        act = f" → `{c.action}`" if c.action and not c.ok else ""
        lines.append(f"- {mark} **{c.id}:** {c.detail}{act}")
    if r.actions:
        lines.extend(["", "## Suggested actions", ""])
        for a in r.actions:
            lines.append(f"- `{a}`")
    lines.extend([
        "",
        "## Super machine entry",
        "```bash",
        "bash scripts/bin/super-machine.sh loop    # session + corroborate + status",
        "bash scripts/bin/workspace-autopilot.sh task \"<message>\"",
        "bash scripts/bin/super-agent.sh trace <api> --fast",
        "```",
    ])
    return "\n".join(lines)


def load_last() -> dict | None:
    if not CORRO_PATH.is_file():
        return None
    try:
        return json.loads(CORRO_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def main() -> int:
    import argparse

    p = argparse.ArgumentParser(description="Cross-layer corroboration")
    p.add_argument("--quick", action="store_true", default=True)
    p.add_argument("--full", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--no-bus", action="store_true")
    args = p.parse_args()
    mode = "full" if args.full else "quick"
    r = run(mode=mode, emit_bus=not args.no_bus)
    if args.json:
        print(json.dumps(r.to_dict(), indent=2))
    else:
        print(format_report(r))
    return 0 if r.passed == r.total else 1


if __name__ == "__main__":
    sys.exit(main())
