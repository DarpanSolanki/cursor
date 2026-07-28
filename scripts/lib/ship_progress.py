#!/usr/bin/env python3
"""Live ship-loop progress — stdout + .cursor/ship-progress.log (no silent >30s)."""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / ".cursor" / "ship-progress.log"
STATE = ROOT / ".cursor" / ".ship-progress-state.json"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_state() -> dict:
    if STATE.is_file():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_state(st: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")


def emit(line: str) -> None:
    line = line.rstrip()
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"{_utc()} {line}\n")


def fmt_dur(s: float) -> str:
    s = max(0, int(s))
    if s < 60:
        return f"{s}s"
    m, r = divmod(s, 60)
    if m < 60:
        return f"{m}m{r:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m"


def init_plan(cases: list[str], budgets: dict[str, int] | None = None) -> None:
    budgets = budgets or {}
    total_est = sum(int(budgets.get(c, 120)) for c in cases)
    st = {
        "started_at": time.time(),
        "cases": cases,
        "budgets": {c: int(budgets.get(c, 120)) for c in cases},
        "total_est_s": total_est,
        "idx": 0,
        "passed": 0,
        "failed": 0,
        "case_results": [],
        "running_wall_s": 0.0,
    }
    _save_state(st)
    LOG.write_text("", encoding="utf-8")  # fresh log for this run
    emit(
        f"SHIP-PROGRESS PLAN n={len(cases)} est_wall={fmt_dur(total_est)} "
        f"cases={' '.join(cases)}"
    )


def case_start(idx: int, n: int, case_id: str, budget_s: int) -> None:
    st = _load_state()
    st["idx"] = idx
    st["current"] = case_id
    st["case_started_at"] = time.time()
    st["case_budget_s"] = budget_s
    remaining = n - idx + 1
    done_wall = float(st.get("running_wall_s") or 0)
    est_total = float(st.get("total_est_s") or 0)
    emit(
        f"[{idx}/{n}] {case_id} START (budget {budget_s}s, "
        f"ETA total ~{fmt_dur(max(0, est_total - done_wall))}, {remaining} remain incl current)"
    )
    _save_state(st)


def case_phase(idx: int, n: int, case_id: str, phase: str, detail: str = "") -> None:
    extra = f" — {detail}" if detail else ""
    emit(f"[{idx}/{n}] {case_id} PHASE {phase}{extra}")


def case_heartbeat(
    idx: int,
    n: int,
    case_id: str,
    *,
    elapsed_s: float,
    budget_s: int,
    detail: str = "",
) -> None:
    extra = f" ({detail})" if detail else ""
    emit(
        f"[{idx}/{n}] {case_id} … {fmt_dur(elapsed_s)}/{budget_s}s{extra}"
    )


def case_end(
    idx: int,
    n: int,
    case_id: str,
    *,
    ok: bool,
    wall_s: float,
    phases: dict | None = None,
) -> None:
    st = _load_state()
    st["running_wall_s"] = float(st.get("running_wall_s") or 0) + wall_s
    if ok:
        st["passed"] = int(st.get("passed") or 0) + 1
        verdict = "PASS"
    else:
        st["failed"] = int(st.get("failed") or 0) + 1
        verdict = "FAIL"
    remain = max(0, n - idx)
    est = float(st.get("total_est_s") or 0)
    row = {
        "idx": idx,
        "case": case_id,
        "exit": 0 if ok else 1,
        "wall_s": round(wall_s, 1),
        "verdict": verdict,
        "phases": phases or {},
    }
    st.setdefault("case_results", []).append(row)
    st["current"] = None
    emit(
        f"[{idx}/{n}] {verdict} {case_id} {fmt_dur(wall_s)} "
        f"(running total {fmt_dur(st['running_wall_s'])}/est {fmt_dur(est)}, {remain} remain)"
    )
    if phases:
        parts = " | ".join(f"{k}={v}ms" for k, v in phases.items())
        emit(f"[{idx}/{n}] PHASES {case_id}: {parts}")
    _save_state(st)


def dump_table() -> str:
    st = _load_state()
    rows = st.get("case_results") or []
    lines = [
        "case | exit | wall_s | phases | verdict",
        "---|---:|---:|---|---",
    ]
    for r in rows:
        ph = r.get("phases") or {}
        ph_s = ";".join(f"{k}={v}" for k, v in ph.items()) if ph else "-"
        lines.append(
            f"{r.get('case')} | {r.get('exit')} | {r.get('wall_s')} | {ph_s} | {r.get('verdict')}"
        )
    return "\n".join(lines)


class HeartbeatWatch:
    """Background tick every ≤15s while a child subprocess runs."""

    def __init__(
        self,
        idx: int,
        n: int,
        case_id: str,
        budget_s: int,
        *,
        interval_s: float = 15.0,
        detail_fn=None,
    ):
        self.idx = idx
        self.n = n
        self.case_id = case_id
        self.budget_s = budget_s
        self.interval_s = interval_s
        self.detail_fn = detail_fn
        self._stop = threading.Event()
        self._t: threading.Thread | None = None
        self._started = time.time()

    def __enter__(self):
        self._started = time.time()
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self._t:
            self._t.join(timeout=2)
        return False

    def _run(self) -> None:
        while not self._stop.wait(self.interval_s):
            elapsed = time.time() - self._started
            detail = ""
            if self.detail_fn:
                try:
                    detail = self.detail_fn() or ""
                except Exception:
                    detail = ""
            case_heartbeat(
                self.idx,
                self.n,
                self.case_id,
                elapsed_s=elapsed,
                budget_s=self.budget_s,
                detail=detail,
            )


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: ship_progress.py init|start|phase|hb|end|table ...", file=sys.stderr)
        return 2
    cmd = sys.argv[1]
    if cmd == "init":
        # init --budget case=sec ... -- cases...
        budgets: dict[str, int] = {}
        cases: list[str] = []
        args = sys.argv[2:]
        i = 0
        while i < len(args):
            if args[i] == "--budget" and i + 1 < len(args):
                k, _, v = args[i + 1].partition("=")
                budgets[k] = int(v)
                i += 2
                continue
            if args[i] == "--":
                cases = args[i + 1 :]
                break
            cases.append(args[i])
            i += 1
        init_plan(cases, budgets)
        return 0
    if cmd == "start":
        case_start(int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], int(sys.argv[5]))
        return 0
    if cmd == "phase":
        case_phase(int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], sys.argv[5], sys.argv[6] if len(sys.argv) > 6 else "")
        return 0
    if cmd == "hb":
        case_heartbeat(
            int(sys.argv[2]),
            int(sys.argv[3]),
            sys.argv[4],
            elapsed_s=float(sys.argv[5]),
            budget_s=int(sys.argv[6]),
            detail=sys.argv[7] if len(sys.argv) > 7 else "",
        )
        return 0
    if cmd == "end":
        ok = sys.argv[5] in ("0", "PASS", "pass", "ok")
        phases = {}
        if len(sys.argv) > 7 and sys.argv[7].startswith("{"):
            phases = json.loads(sys.argv[7])
        case_end(
            int(sys.argv[2]),
            int(sys.argv[3]),
            sys.argv[4],
            ok=ok,
            wall_s=float(sys.argv[6]),
            phases=phases,
        )
        return 0
    if cmd == "table":
        print(dump_table())
        return 0
    print(f"unknown cmd {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
