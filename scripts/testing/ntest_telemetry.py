#!/usr/bin/env python3
"""ntest case telemetry — rotating log + flaky detection (Upgrade 7)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "scripts" / "scratch" / "logs" / "ntest-telemetry.log"
MAX_LINES = 500
QUARANTINE = ROOT / "scripts" / "testing" / "registry-proposals.json"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_case_result(case_id: str, passed: bool, duration_s: float) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"{_utc()} | {case_id} | {'pass' if passed else 'fail'} | {duration_s:.2f}s\n"
    prev = LOG.read_text(encoding="utf-8").splitlines() if LOG.is_file() else []
    prev.append(line.rstrip())
    LOG.write_text("\n".join(prev[-MAX_LINES:]) + "\n", encoding="utf-8")


def flaky_cases(window: int = 10, min_fails: int = 2) -> list[tuple[str, int, int]]:
    """Return (case_id, fails, runs) for cases with ≥min_fails in last window runs of that case."""
    if not LOG.is_file():
        return []
    by: dict[str, list[str]] = {}
    for ln in LOG.read_text(encoding="utf-8").splitlines():
        parts = [p.strip() for p in ln.split("|")]
        if len(parts) < 3:
            continue
        cid, result = parts[1], parts[2]
        by.setdefault(cid, []).append(result)
    out = []
    for cid, results in by.items():
        recent = results[-window:]
        fails = sum(1 for r in recent if r == "fail")
        if fails >= min_fails:
            out.append((cid, fails, len(recent)))
    return sorted(out, key=lambda x: -x[1])


def emit_quarantine_proposals(money_ids: set[str] | None = None) -> list[str]:
    """Append quarantine PROPOSALS for flaky cases — money never auto-skipped."""
    import json

    money_ids = money_ids or set()
    flaky = flaky_cases()
    if not flaky:
        return []
    data = {"version": 1, "updated": _utc(), "proposals": []}
    if QUARANTINE.is_file():
        try:
            data = json.loads(QUARANTINE.read_text(encoding="utf-8"))
        except Exception:
            pass
    known = {p.get("id") for p in data.get("proposals") or []}
    added = []
    for cid, fails, runs in flaky:
        pid = f"quarantine.{cid}"
        if pid in known:
            continue
        money = cid in money_ids or cid.startswith(("disbursement.", "dcf.", "dpic.", "foreclosure."))
        data.setdefault("proposals", []).append(
            {
                "id": pid,
                "status": "quarantine_proposal",
                "source": "ntest_telemetry",
                "created_at": _utc(),
                "case_id": cid,
                "money": money,
                "note": (
                    f"Flaky: {fails}/{runs} fails in last window — "
                    + ("MONEY: flag only, never auto-skip" if money else "propose quarantine after human review")
                ),
            }
        )
        added.append(pid)
    data["updated"] = _utc()
    QUARANTINE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return added


def doctor_report() -> str:
    flaky = flaky_cases()
    if not flaky:
        return "none flaky"
    lines = [f"{cid}: {fails}/{runs} fails" for cid, fails, runs in flaky[:15]]
    return "flaky: " + "; ".join(lines)
