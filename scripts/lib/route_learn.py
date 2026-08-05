#!/usr/bin/env python3
"""Route learn — tune the router from what tasks actually did. Report-only by design.

Reads `plan_computed` / `plan_escalation` / `task_closed` off the learning bus and reports where
the plan was wrong: classes that keep escalating (planned too light), gates whose measured cost has
drifted from the matrix seed, predicates that are chronically unmet at close, and evidence tiers
that reveal how much of the work was actually verified rather than asserted.

It never edits the matrix. Weakening a money cell is the one change that must stay a human
decision, and `process_router.check_money_ratchet` fails closed on it regardless.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
sys.path.insert(0, str(ROOT / "scripts" / "testing"))

COST_DRIFT_FACTOR = 2.0
MIN_SAMPLES = 3


def _events() -> list[dict]:
    try:
        from learning_bus import load_events

        rows = []
        for t in ("plan_computed", "plan_escalation", "task_closed"):
            rows.extend(load_events(limit=500, event_type=t))
        return rows
    except Exception:
        return []


def analyse() -> dict:
    rows = _events()
    closed = [r for r in rows if r.get("type") == "task_closed"]
    escal = [r for r in rows if r.get("type") == "plan_escalation"]
    planned = [r for r in rows if r.get("type") == "plan_computed"]

    findings: list[dict] = []

    escalation_pairs = Counter()
    for r in escal:
        m = r.get("meta") or {}
        escalation_pairs[(m.get("from"), m.get("to"))] += 1
    for (frm, to), n in escalation_pairs.most_common():
        if n >= MIN_SAMPLES:
            findings.append({
                "kind": "classifier_too_light",
                "detail": f"{frm} → {to} escalated {n}x — the words route lighter than the edits",
                "action": f"tighten map_class for {frm}: add the giveaway terms, or accept escalation as the guard",
            })

    unmet = Counter()
    tiers = Counter()
    for r in closed:
        m = r.get("meta") or {}
        tiers[m.get("evidence_tier") or "UNSTATED"] += 1
        for p in m.get("unmet") or []:
            unmet[p] += 1
    for pred, n in unmet.most_common():
        if n >= MIN_SAMPLES:
            findings.append({
                "kind": "predicate_chronically_unmet",
                "detail": f"{pred} unmet at close {n}x",
                "action": f"either the task genuinely is not reaching {pred}, or the gate that satisfies it is missing from the plan",
            })

    est_vs_actual: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for r in closed:
        m = r.get("meta") or {}
        est, act = m.get("est_s"), m.get("actual_step_s")
        if est and act:
            est_vs_actual[m.get("process_class") or "?"].append((float(est), float(act)))
    for pclass, pairs in est_vs_actual.items():
        if len(pairs) < MIN_SAMPLES:
            continue
        e = sum(p[0] for p in pairs) / len(pairs)
        a = sum(p[1] for p in pairs) / len(pairs)
        if e and (a > e * COST_DRIFT_FACTOR or e > a * COST_DRIFT_FACTOR):
            findings.append({
                "kind": "estimate_drift",
                "detail": f"{pclass}: estimate {e:.1f}s vs actual {a:.1f}s over {len(pairs)} tasks",
                "action": "weights are self-correcting via record_cost; investigate only if the gap persists",
            })

    try:
        from process_router import load_costs, load_matrix

        costs, man = load_costs(), load_matrix()
        for name, meta in (man.get("processes") or {}).items():
            seed = float(meta.get("cost_s") or 0)
            learned = (costs.get(name) or {})
            lc, samples = float(learned.get("cost_s") or 0), int(learned.get("samples") or 0)
            if samples >= MIN_SAMPLES and seed and lc and (
                lc > seed * COST_DRIFT_FACTOR or seed > lc * COST_DRIFT_FACTOR
            ):
                findings.append({
                    "kind": "seed_cost_stale",
                    "detail": f"{name}: matrix seed {seed}s vs measured {lc}s ({samples} samples)",
                    "action": f"update cost_s for {name} in process_matrix.json to ~{lc}s",
                })
    except Exception:
        pass

    return {
        "tasks_closed": len(closed),
        "plans": len(planned),
        "escalations": len(escal),
        "terminal_met": sum(1 for r in closed if (r.get("meta") or {}).get("terminal_met")),
        "evidence_tiers": dict(tiers),
        "findings": findings,
    }


def report(as_json: bool = False) -> int:
    res = analyse()
    if as_json:
        print(json.dumps(res, indent=2))
        return 0
    print("## Route learn — router tuning report (report-only)")
    print()
    if res["tasks_closed"] < MIN_SAMPLES:
        print(f"Insufficient data: {res['tasks_closed']} closed task(s); need {MIN_SAMPLES}.")
        print("The ledger records every task from now on — re-run after a few more.")
        return 0
    met = res["terminal_met"]
    total = res["tasks_closed"]
    pct = (100.0 * met / total) if total else 0.0
    print(f"- Tasks closed: **{total}** · terminal MET: **{met}** ({pct:.0f}%)")
    print(f"- Plans computed: {res['plans']} · escalations: {res['escalations']}")
    print(f"- Evidence tiers: {res['evidence_tiers']}")
    print()
    if not res["findings"]:
        print("No tuning findings — plans are matching reality.")
        return 0
    print("### Findings")
    for f in res["findings"]:
        print(f"- **{f['kind']}** — {f['detail']}")
        print(f"  - action: {f['action']}")
    print()
    print("Money-floor cells are never proposed for weakening; `process_router.py ratchet` enforces it.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="report", choices=["report"])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    return report(as_json=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
