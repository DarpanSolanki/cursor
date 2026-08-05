#!/usr/bin/env python3
"""Route ledger — plan/outcome record for one task, and the terminal-state check that closes it.

The router picks the minimal ordered path; this module remembers which path was picked, what
actually ran, whether reality diverged from the plan mid-task, and whether the goal predicates
for the class were met at close. Plan and outcome land on the learning bus as `plan_computed`,
`plan_escalation` and `task_closed`, which is the data `route_learn.py` tunes the weights from.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / ".cursor" / ".task-state.json"

sys.path.insert(0, str(ROOT / "scripts" / "lib"))
sys.path.insert(0, str(ROOT / "scripts" / "testing"))

CLASS_RANK = {
    "question": 0,
    "docs-kb": 0,
    "read-only-rca": 1,
    "non-money-fix": 2,
    "batch-dpi": 3,
    "release": 3,
    "money-fix": 4,
}


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _bus(event_type: str, **kw):
    try:
        from learning_bus import append_event

        return append_event(event_type, **kw)
    except Exception:
        return {}


def load() -> dict:
    if STATE.is_file():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def save(data: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def open_task(*, process_class: str, classification: str, text: str, plan: dict) -> dict:
    data = {
        "opened_at": _utc(),
        "opened_ts": time.time(),
        "process_class": process_class,
        "classification": classification,
        "text": (text or "")[:240],
        "planned": list(plan.get("run") or []),
        "cached": [n for n, _ in plan.get("cached") or []],
        "est_s": plan.get("est_s"),
        "terminal_state": list(plan.get("terminal_state") or []),
        "ran": [],
        "escalations": [],
        "status": "open",
    }
    save(data)
    _bus(
        "plan_computed",
        source="route_ledger",
        detail=f"{process_class} est={plan.get('est_s')}s steps={len(data['planned'])}",
        meta={
            "process_class": process_class,
            "planned": data["planned"],
            "cached": data["cached"],
            "est_s": plan.get("est_s"),
        },
    )
    return data


def note_step(name: str, *, ok: bool, elapsed_s: float = 0.0) -> dict:
    data = load()
    if not data:
        return {}
    data.setdefault("ran", []).append(
        {"id": name, "ok": bool(ok), "elapsed_s": round(float(elapsed_s or 0), 2)}
    )
    save(data)
    try:
        from process_router import record_cost

        if elapsed_s:
            record_cost(name, float(elapsed_s))
    except Exception:
        pass
    return data


def escalate(*, to_class: str, reason: str, path: str = "") -> dict:
    """Reality outranked the plan — record the delta gates the heavier class demands."""
    data = load()
    if not data:
        return {"escalated": False, "reason": "no open task"}
    frm = data.get("process_class") or "question"
    if CLASS_RANK.get(to_class, 0) <= CLASS_RANK.get(frm, 0):
        return {"escalated": False, "from": frm, "to": to_class, "reason": "not heavier"}
    delta: list[str] = []
    try:
        from process_router import compute_plan

        old = set(data.get("planned") or []) | set(data.get("cached") or [])
        new_plan = compute_plan(
            data.get("classification") or "FIX+SHIP",
            data.get("text") or "",
            force_class=to_class,
        )
        for name in new_plan.get("run") or []:
            if name not in old:
                delta.append(name)
    except Exception:
        pass
    entry = {
        "at": _utc(),
        "from": frm,
        "to": to_class,
        "reason": reason,
        "path": path,
        "delta_gates": delta,
    }
    data["process_class"] = to_class
    data.setdefault("escalations", []).append(entry)
    try:
        from process_router import terminal_state

        data["terminal_state"] = terminal_state(to_class)
    except Exception:
        pass
    save(data)
    _bus(
        "plan_escalation",
        source="route_ledger",
        detail=f"{frm} → {to_class}: {reason}",
        evidence=path or None,
        meta=entry,
    )
    return {"escalated": True, **entry}


def _check_auto(name: str, how: str) -> tuple[bool, str]:
    if how.startswith("ttl:"):
        try:
            from process_router import load_matrix, ttl_fresh

            fresh, utc = ttl_fresh(how[4:], (load_matrix().get("ttls_seconds") or {}))
            return fresh, (f"fresh @{utc}" if fresh else "TTL expired")
        except Exception as exc:
            return False, f"check failed: {exc}"
    if how.startswith("file:"):
        p = ROOT / how[5:]
        return p.is_file(), (f"present {how[5:]}" if p.is_file() else f"missing {how[5:]}")
    if how.startswith("cmd:"):
        try:
            r = subprocess.run(
                how[4:], shell=True, cwd=str(ROOT), capture_output=True, text=True, timeout=120
            )
            out = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
            return r.returncode == 0, (out[-1][:120] if out else f"rc={r.returncode}")
        except Exception as exc:
            return False, f"cmd failed: {exc}"
    if how == "pending_ship_satisfied":
        pending = ROOT / ".cursor" / ".pending-ship-work.json"
        if not pending.is_file():
            return True, "no pending ship work"
        gate = ROOT / "scripts" / "lib" / "ship_push_gate.py"
        if not gate.is_file():
            return False, "pending present, gate missing"
        r = subprocess.run(
            ["python3", str(gate), "--satisfied"], cwd=str(ROOT), capture_output=True
        )
        return r.returncode == 0, ("pending satisfied" if r.returncode == 0 else "pending unsatisfied")
    return False, f"unknown predicate check {how!r}"


def check_terminal(declared: set[str] | None = None, *, cheap: bool = False) -> dict:
    """Verify the goal predicates for the open task's class. Declared ones need the agent's word.

    `cheap` skips subprocess-backed predicates so per-turn resume stays free; close never does.
    """
    data = load()
    if not data:
        return {"ok": False, "reason": "no open task", "results": []}
    declared = declared or set()
    results = []
    try:
        from process_router import predicate_meta
    except Exception:
        return {"ok": False, "reason": "router unavailable", "results": []}
    for name in data.get("terminal_state") or []:
        meta = predicate_meta(name)
        kind = meta.get("check") or "declared"
        how = meta.get("how") or ""
        if kind == "auto" and cheap and (how.startswith("cmd:") or how == "pending_ship_satisfied"):
            results.append({"predicate": name, "check": kind, "ok": False, "note": "not checked (cheap)"})
            continue
        if kind == "auto":
            ok, note = _check_auto(name, how)
        else:
            ok = name in declared
            note = "declared by agent" if ok else "NOT declared"
        results.append({"predicate": name, "check": kind, "ok": ok, "note": note})
    met = all(r["ok"] for r in results) if results else True
    return {"ok": met, "results": results, "process_class": data.get("process_class")}


def close_task(*, declared: set[str] | None = None, evidence_tier: str = "UNSTATED") -> dict:
    data = load()
    if not data:
        return {"ok": False, "reason": "no open task"}
    term = check_terminal(declared)
    wall = round(time.time() - float(data.get("opened_ts") or time.time()), 1)
    actual = round(sum(float(s.get("elapsed_s") or 0) for s in data.get("ran") or []), 1)
    data["status"] = "closed"
    data["closed_at"] = _utc()
    data["wall_s"] = wall
    data["actual_step_s"] = actual
    data["terminal_met"] = term["ok"]
    data["terminal_results"] = term["results"]
    data["evidence_tier"] = evidence_tier
    save(data)
    _bus(
        "task_closed",
        source="route_ledger",
        detail=(
            f"{data.get('process_class')} terminal={'MET' if term['ok'] else 'UNMET'} "
            f"est={data.get('est_s')}s actual={actual}s evidence={evidence_tier}"
        ),
        meta={
            "process_class": data.get("process_class"),
            "planned": data.get("planned"),
            "ran": [s.get("id") for s in data.get("ran") or []],
            "escalations": len(data.get("escalations") or []),
            "est_s": data.get("est_s"),
            "actual_step_s": actual,
            "wall_s": wall,
            "terminal_met": term["ok"],
            "unmet": [r["predicate"] for r in term["results"] if not r["ok"]],
            "evidence_tier": evidence_tier,
        },
    )
    return {"ok": True, "terminal": term, "wall_s": wall, "actual_step_s": actual}


def resume_line() -> str:
    data = load()
    if not data or data.get("status") != "open":
        return ""
    ran = {s.get("id") for s in data.get("ran") or []}
    remaining = [n for n in data.get("planned") or [] if n not in ran]
    unmet = [
        r["predicate"] for r in (check_terminal(cheap=True).get("results") or []) if not r["ok"]
    ]
    return (
        f"RESUME [{data.get('process_class')}] opened@{data.get('opened_at')} · "
        f"done {len(ran)}/{len(data.get('planned') or [])} · "
        f"remaining {','.join(remaining) or '—'} · unmet {','.join(unmet) or '—'}"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["status", "terminal", "close", "escalate", "resume"])
    ap.add_argument("--declared", default="")
    ap.add_argument("--evidence-tier", default="UNSTATED")
    ap.add_argument("--to-class", default="money-fix")
    ap.add_argument("--reason", default="")
    ap.add_argument("--path", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    declared = {x.strip() for x in args.declared.split(",") if x.strip()}

    if args.cmd == "status":
        print(json.dumps(load(), indent=2))
        return 0
    if args.cmd == "resume":
        line = resume_line()
        print(line or "no open task")
        return 0
    if args.cmd == "terminal":
        res = check_terminal(declared)
        if args.json:
            print(json.dumps(res, indent=2))
            return 0
        print(f"TERMINAL [{res.get('process_class')}]: {'MET' if res['ok'] else 'UNMET'}")
        for r in res.get("results") or []:
            print(f"  {'✓' if r['ok'] else '✗'} {r['predicate']} ({r['check']}) — {r['note']}")
        return 0 if res["ok"] else 1
    if args.cmd == "escalate":
        res = escalate(to_class=args.to_class, reason=args.reason, path=args.path)
        print(json.dumps(res, indent=2))
        return 0
    if args.cmd == "close":
        res = close_task(declared=declared, evidence_tier=args.evidence_tier)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            t = res.get("terminal") or {}
            print(f"CLOSE: terminal={'MET' if t.get('ok') else 'UNMET'} wall={res.get('wall_s')}s")
            for r in t.get("results") or []:
                print(f"  {'✓' if r['ok'] else '✗'} {r['predicate']} — {r['note']}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
