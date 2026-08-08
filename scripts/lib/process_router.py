#!/usr/bin/env python3
"""Process router — minimal ordered gate path by task class; TTL short-circuit; money-cell ratchet.

v2: the matrix is a weighted DAG. `cost_s` seeds each node, `requires` supplies the edges,
and observed run times relax the weights (EWMA) into `.cursor/.process-costs.json`. A plan is
the cheapest ordered set of nodes that satisfies the class contract — TTL-cached nodes cost 0.
`terminal_state` names the goal predicates the task must reach for that class.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "scripts" / "lib" / "process_matrix.json"
OPS = ROOT / ".cursor" / "workspace-ops-state.md"
TTL_STATE = ROOT / ".cursor" / ".process-ttl-state.json"
MONEY_FLOOR_SNAP = ROOT / ".cursor" / ".process-money-floor.json"
COST_STATE = ROOT / ".cursor" / ".process-costs.json"

COST_ALPHA = 0.3
PHASE_RANK = {"orient": 0, "gate": 1, "verify": 2, "close": 3}

# Map autopilot / agent-router kinds → matrix columns
CLASS_MAP = {
    "GENERAL": "question",
    "INVESTIGATION": "question",
    "COMMS": "docs-kb",
    "WORKSPACE": "docs-kb",
    "SYNC": "docs-kb",
    "PR_REVIEW": "non-money-fix",
    "CODE/DAO": "non-money-fix",
    "OPS_SQL": "money-fix",  # fail-closed heavier
    "BUG/RCA": "read-only-rca",
    "FIX+SHIP": "non-money-fix",
    "FEATURE": "non-money-fix",
    "TEST": "batch-dpi",
    # Prod/UAT batch|API slowness — same gate column as batch-dpi (train-delta + hot-path).
    "PERF_RCA": "batch-dpi",
    "RELEASE": "release",
}

# Process-matrix columns — CLI `--class` with one of these forces the plan class.
PROCESS_CLASSES = frozenset({
    "question",
    "read-only-rca",
    "non-money-fix",
    "money-fix",
    "batch-dpi",
    "release",
    "docs-kb",
})

MONEY_WORDS = (
    "disburse", "repay", "foreclos", "death", "dfc", "dcf", "dpi", "money", "ledger",
    "gl ", "neft", "accounting", "payment", "loan", "billing", "accrual",
)
# TEST tasks that are money/batch even when the word "batch" is absent.
BATCH_TEST_MARKERS = ("dpi", "batch", "eod", "dcf", "dfc", "death")
QA_ENV = re.compile(r"\b(qa[1-6]|uat|mfi_qa)\b", re.I)


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_matrix() -> dict:
    return json.loads(MATRIX.read_text(encoding="utf-8"))


def map_class(classification: str, text: str = "") -> str:
    """Fail-closed: ambiguous/money words escalate."""
    t = (text or "").lower()
    c = (classification or "GENERAL").upper()
    # CLI / callers may pass a matrix column directly — honour it.
    if (classification or "") in PROCESS_CLASSES:
        return classification
    base = CLASS_MAP.get(c, "read-only-rca")  # unknown → heavier than question
    if c == "BUG/RCA" and any(w in t for w in ("fix", "implement", "ship", "patch")):
        base = "money-fix" if any(w in t for w in MONEY_WORDS) else "non-money-fix"
    if c in ("FIX+SHIP", "FEATURE") and any(w in t for w in MONEY_WORDS):
        base = "money-fix"
    if c == "TEST":
        if any(m in t for m in BATCH_TEST_MARKERS) or any(w in t for w in MONEY_WORDS):
            base = "batch-dpi"
        else:
            base = "non-money-fix"
    if c == "OPS_SQL":
        base = "money-fix"
    if base == "question" and any(w in t for w in MONEY_WORDS):
        base = "read-only-rca"  # escalate
    return base


def validate_dag(matrix: dict | None = None) -> list[str]:
    """Structural invariants for `process_matrix.json` — cycles, unknown deps, phase order.

    `order_path` / `plan_waves` assume these; without this check a broken matrix still
    produces a plan that looks correct and runs gates in the wrong order.
    """
    man = matrix if matrix is not None else load_matrix()
    procs = man.get("processes") or {}
    errors: list[str] = []

    for name, meta in procs.items():
        name_phase = meta.get("phase") or "orient"
        name_rank = PHASE_RANK.get(name_phase, 0)
        for dep in meta.get("requires") or []:
            if dep not in procs:
                errors.append(f"unknown dependency: {name} requires {dep}")
                continue
            dep_phase = (procs[dep].get("phase") or "orient")
            dep_rank = PHASE_RANK.get(dep_phase, 0)
            if dep_rank > name_rank:
                errors.append(
                    f"phase inversion: {name} ({name_phase}) requires {dep} ({dep_phase})"
                )

    # Cycle detection on the requires graph (edge = depends-on).
    color: dict[str, int] = {n: 0 for n in procs}  # 0=white 1=gray 2=black

    def dfs(u: str, stack: list[str]) -> None:
        color[u] = 1
        stack.append(u)
        for v in (procs[u].get("requires") or []):
            if v not in procs:
                continue
            if color[v] == 1:
                i = stack.index(v)
                errors.append("cycle: " + " → ".join(stack[i:] + [v]))
            elif color[v] == 0:
                dfs(v, stack)
        stack.pop()
        color[u] = 2

    for n in procs:
        if color[n] == 0:
            dfs(n, [])

    return errors


def load_ttl_state() -> dict:
    if TTL_STATE.is_file():
        try:
            return json.loads(TTL_STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_ttl_state(state: dict) -> None:
    TTL_STATE.parent.mkdir(parents=True, exist_ok=True)
    TTL_STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def stamp_ttl(key: str) -> None:
    st = load_ttl_state()
    st[key] = {"ts": time.time(), "utc": _utc()}
    save_ttl_state(st)


def ttl_fresh(key: str | None, ttls: dict) -> tuple[bool, str]:
    if not key:
        return False, ""
    max_age = int(ttls.get(key) or 0)
    if max_age <= 0:
        return False, ""
    st = load_ttl_state().get(key) or {}
    ts = float(st.get("ts") or 0)
    if not ts:
        # parse ops-state Updated for services/env as soft cache
        if OPS.is_file() and key in ("services", "env_smoke"):
            text = OPS.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"Updated:\s*(\d{4}-\d{2}-\d{2}T[\d:]+Z)", text)
            if m:
                try:
                    ts = calendar_ts(m.group(1))
                except Exception:
                    ts = 0
    if not ts:
        return False, ""
    age = time.time() - ts
    if age <= max_age:
        utc = st.get("utc") or datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return True, utc
    return False, ""


def calendar_ts(utc: str) -> float:
    return datetime.strptime(utc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()


def load_costs() -> dict:
    if COST_STATE.is_file():
        try:
            return json.loads(COST_STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def record_cost(name: str, elapsed_s: float) -> float:
    """Relax the node weight toward what the run actually cost."""
    if not name or elapsed_s is None or elapsed_s < 0:
        return 0.0
    costs = load_costs()
    prev = costs.get(name) or {}
    old = float(prev.get("cost_s") or 0)
    new = elapsed_s if old <= 0 else (COST_ALPHA * elapsed_s + (1 - COST_ALPHA) * old)
    costs[name] = {
        "cost_s": round(new, 2),
        "samples": int(prev.get("samples") or 0) + 1,
        "last_s": round(elapsed_s, 2),
        "utc": _utc(),
    }
    COST_STATE.parent.mkdir(parents=True, exist_ok=True)
    COST_STATE.write_text(json.dumps(costs, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return round(new, 2)


def cost_of(name: str, meta: dict, costs: dict) -> float:
    learned = (costs.get(name) or {}).get("cost_s")
    if learned:
        return float(learned)
    return float(meta.get("cost_s") or 1.0)


def order_path(names: list[str], procs: dict, costs: dict) -> list[str]:
    """Topological order over `requires`, phase-ranked, cheapest-first among equals."""
    selected = set(names)
    indeg = {n: 0 for n in names}
    for n in names:
        for dep in (procs.get(n) or {}).get("requires") or []:
            if dep in selected:
                indeg[n] += 1

    def sort_key(n: str) -> tuple:
        meta = procs.get(n) or {}
        return (PHASE_RANK.get(meta.get("phase") or "orient", 0), cost_of(n, meta, costs), n)

    ready = sorted([n for n in names if indeg[n] == 0], key=sort_key)
    out: list[str] = []
    while ready:
        node = ready.pop(0)
        out.append(node)
        for other in names:
            if other in out or other in ready:
                continue
            deps = (procs.get(other) or {}).get("requires") or []
            if node in deps:
                indeg[other] -= 1
                if indeg[other] <= 0:
                    ready.append(other)
        ready = sorted(ready, key=sort_key)
    for n in names:
        if n not in out:
            out.append(n)
    return out


def plan_waves(names: list[str], procs: dict, costs: dict) -> list[list[str]]:
    """Group the ordered path into dependency waves — a wave runs concurrently.

    Every selected gate still runs; only the idle waiting between independent gates is removed,
    so wall time falls to the sum of per-wave maxima without changing what was verified.
    """
    selected = set(names)
    depth: dict[str, int] = {}

    def resolve(node: str, seen: frozenset[str] = frozenset()) -> int:
        if node in depth:
            return depth[node]
        if node in seen:
            return 0
        deps = [d for d in ((procs.get(node) or {}).get("requires") or []) if d in selected]
        d = 0 if not deps else 1 + max(resolve(x, seen | {node}) for x in deps)
        depth[node] = d
        return d

    for n in names:
        resolve(n)

    phase_of = {n: PHASE_RANK.get((procs.get(n) or {}).get("phase") or "orient", 0) for n in names}
    buckets: dict[tuple[int, int], list[str]] = {}
    for n in names:
        buckets.setdefault((phase_of[n], depth[n]), []).append(n)
    waves = []
    for key in sorted(buckets):
        wave = sorted(buckets[key], key=lambda n: -cost_of(n, procs.get(n) or {}, costs))
        waves.append(wave)
    return waves


def terminal_state(pclass: str, matrix: dict | None = None) -> list[str]:
    man = matrix or load_matrix()
    return list((man.get("terminal_state") or {}).get(pclass) or [])


def predicate_meta(name: str, matrix: dict | None = None) -> dict:
    man = matrix or load_matrix()
    return dict((man.get("predicates") or {}).get(name) or {})


def eval_trigger(trigger: str, text: str, ctx: dict) -> bool:
    t = (text or "").lower()
    if trigger == "api_or_flow_named":
        return bool(ctx.get("api_hint") or re.search(r"\b[a-z]+[A-Z][a-zA-Z]+\b", text or ""))
    if trigger == "code_touch" or trigger == "code_touched":
        return bool(ctx.get("code_touch") or ctx.get("code_touched") or "fix" in t or "implement" in t)
    if trigger == "query_touched":
        if ctx.get("query_touched"):
            return True
        try:
            from query_plan_gate import query_touched as _qt

            return bool(_qt())
        except Exception:
            return "@query" in t or "nativequery" in t or "repository" in t
    if trigger == "cross_service_or_money_words":
        return any(w in t for w in MONEY_WORDS) or "cross" in t or "kafka" in t
    if trigger == "multi_repo":
        return "multi" in t or "cross-repo" in t or "sync-branches" in t
    if trigger == "qa_env_named":
        return bool(QA_ENV.search(text or ""))
    if trigger == "needs_runtime":
        return "ntest" in t or "runtime" in t or "e2e" in t
    if trigger == "java_changed":
        return bool(ctx.get("java_changed"))
    if trigger == "money_domain":
        return any(w in t for w in MONEY_WORDS)
    if trigger == "pending_ship":
        return (ROOT / ".cursor" / ".pending-ship-work.json").is_file()
    if trigger == "dpi_words":
        return "dpi" in t or "delayed_payment" in t
    if trigger == "dpi_in_release":
        return "dpi" in t
    if trigger == "flyway_touched":
        return "flyway" in t or "migration" in t
    if trigger == "schema_or_masterdata_touched":
        if any(
            x in t
            for x in (
                "flyway",
                "migration",
                "masterdata",
                "initial-setup",
                "local_setup",
                "schema",
                "add column",
            )
        ):
            return True
        try:
            from local_parity_gate import schema_or_masterdata_touched

            return schema_or_masterdata_touched()
        except Exception:
            return False
    if trigger == "jira_handoff":
        return "jira" in t or "handoff" in t or "dev test" in t
    if trigger == "shipped_code":
        return "ship" in t or "push" in t or "commit" in t
    if trigger == "money_in_release":
        return any(w in t for w in MONEY_WORDS)
    if trigger == "brain_changelog":
        return "changelog" in t or "brain" in t
    if trigger == "new_gotcha":
        return "gotcha" in t or "learn" in t
    if trigger == "kb_change":
        return "docs" in t or "kb" in t or "rule" in t
    return False  # unknown trigger → don't run (but money required cells never use unknown)


def resolve_cell(cell: str, text: str, ctx: dict) -> str:
    if cell == "required":
        return "run"
    if cell == "skip":
        return "skip"
    if cell.startswith("conditional(") and cell.endswith(")"):
        trig = cell[len("conditional(") : -1]
        return "run" if eval_trigger(trig, text, ctx) else "skip"
    return "run"  # fail-closed unknown cell syntax


def compute_plan(
    classification: str,
    text: str = "",
    *,
    api_hint: str | None = None,
    ctx: dict | None = None,
    force_class: str | None = None,
    already_ran: set[str] | list[str] | None = None,
) -> dict:
    man = load_matrix()
    pclass = force_class or map_class(classification, text)
    ctx = dict(ctx or {})
    if api_hint:
        ctx["api_hint"] = api_hint
    ttls = man.get("ttls_seconds") or {}
    procs = man.get("processes") or {}
    costs = load_costs()
    dedup_phases = set((man.get("dedup_phases") or {}).get("phases") or [])
    already = set(already_ran or [])
    run: list[str] = []
    skip: list[tuple[str, str]] = []
    cached: list[tuple[str, str]] = []

    for name, meta in procs.items():
        cell = (meta.get("cells") or {}).get(pclass, "required")  # missing → heavier
        decision = resolve_cell(cell, text, ctx)
        if decision == "skip":
            reason = cell if cell == "skip" else f"trigger unmet ({cell})"
            skip.append((name, reason))
            continue
        if name in already and (meta.get("phase") or "orient") in dedup_phases:
            cached.append((name, "this task"))
            continue
        ttl_key = meta.get("ttl_key")
        fresh, utc = ttl_fresh(ttl_key, ttls)
        if fresh:
            cached.append((name, utc))
            continue
        run.append(name)

    run = order_path(run, procs, costs)
    waves = plan_waves(run, procs, costs)
    est_s = round(sum(cost_of(n, procs.get(n) or {}, costs) for n in run), 1)
    wave_s = round(
        sum(max((cost_of(n, procs.get(n) or {}, costs) for n in w), default=0) for w in waves), 1
    )
    saved_s = round(sum(cost_of(n, procs.get(n) or {}, costs) for n, _ in cached), 1)
    goal = terminal_state(pclass, man)

    line = (
        f"PLAN [{pclass}] ~{wave_s}s ({len(waves)} waves, serial {est_s}s): "
        f"RUN {','.join(run) or '—'} · "
        f"SKIP {';'.join(f'{n}({r})' for n,r in skip) or '—'} · "
        f"CACHED {';'.join(f'{n}(@{u})' for n,u in cached) or '—'}"
        + (f" (saved ~{saved_s}s)" if saved_s else "")
    )
    return {
        "process_class": pclass,
        "classification": classification,
        "run": run,
        "waves": waves,
        "skip": skip,
        "cached": cached,
        "est_s": est_s,
        "wave_s": wave_s,
        "saved_s": saved_s,
        "terminal_state": goal,
        "line": line,
        "goal_line": f"GOAL [{pclass}]: {' + '.join(goal) if goal else '—'}",
        "money_floor": list((man.get("money_floor") or {}).get("processes") or []),
    }


def check_money_ratchet(proposed_matrix: dict | None = None) -> list[str]:
    """Fail if money-fix cells for money_floor processes weakened vs snap / required."""
    man = proposed_matrix or load_matrix()
    floor = list((man.get("money_floor") or {}).get("processes") or [])
    errors = []
    # Baseline snap: first-seen required set
    snap = {}
    if MONEY_FLOOR_SNAP.is_file():
        try:
            snap = json.loads(MONEY_FLOOR_SNAP.read_text(encoding="utf-8"))
        except Exception:
            snap = {}
    procs = man.get("processes") or {}
    for name in floor:
        cell = ((procs.get(name) or {}).get("cells") or {}).get("money-fix")
        if cell != "required":
            errors.append(
                f"money-cell ratchet FAIL: {name}.money-fix={cell!r} must stay required"
            )
        prev = snap.get(name)
        if prev == "required" and cell != "required":
            errors.append(f"money-cell ratchet FAIL: {name} weakened from required → {cell}")
    # Update snap only when clean
    if not errors and not proposed_matrix:
        new_snap = {
            n: ((procs.get(n) or {}).get("cells") or {}).get("money-fix") for n in floor
        }
        MONEY_FLOOR_SNAP.write_text(json.dumps(new_snap, indent=2) + "\n", encoding="utf-8")
    return errors


def plan_diff(class_a: str, text_a: str, class_b: str, text_b: str) -> str:
    pa = compute_plan(class_a, text_a)
    pb = compute_plan(class_b, text_b)
    extra = sorted(set(pb["run"]) - set(pa["run"]))
    dropped = sorted(set(pa["run"]) - set(pb["run"]))
    return (
        f"PLAN DIFF {pa['process_class']} → {pb['process_class']}: "
        f"+RUN {','.join(extra) or '—'} · -RUN {','.join(dropped) or '—'}"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "cmd",
        choices=["plan", "ratchet", "stamp", "diff", "map-class", "terminal", "record-cost", "costs"],
    )
    ap.add_argument("--class", dest="cls", default="GENERAL")
    ap.add_argument("--text", default="")
    ap.add_argument("--api", default="")
    ap.add_argument("--ttl-key", default="")
    ap.add_argument("--other-class", default="FIX+SHIP")
    ap.add_argument("--other-text", default="money fix disbursement")
    ap.add_argument("--process", default="")
    ap.add_argument("--elapsed", type=float, default=0.0)
    args = ap.parse_args()
    if args.cmd == "plan":
        force = args.cls if args.cls in PROCESS_CLASSES else None
        p = compute_plan(
            args.cls if force is None else "GENERAL",
            args.text,
            api_hint=args.api or None,
            force_class=force,
        )
        print(p["line"])
        print(p["goal_line"])
        return 0
    if args.cmd == "terminal":
        pclass = args.cls if args.cls in PROCESS_CLASSES else map_class(args.cls, args.text)
        for name in terminal_state(pclass):
            meta = predicate_meta(name)
            print(f"{name}\t{meta.get('check','declared')}\t{meta.get('label','')}")
        return 0
    if args.cmd == "record-cost":
        new = record_cost(args.process, args.elapsed)
        print(f"{args.process} cost_s={new}")
        return 0
    if args.cmd == "costs":
        print(json.dumps(load_costs(), indent=2, sort_keys=True))
        return 0
    if args.cmd == "ratchet":
        errs = check_money_ratchet()
        errs.extend(validate_dag())
        stray = MATRIX.parent / "process-matrix.json"
        if stray.is_file():
            errs.append(
                f"matrix drift: {stray.relative_to(ROOT)} is back — process_matrix.json is the only SoT"
            )
        if errs:
            print("MONEY-CELL RATCHET FAIL:")
            for e in errs:
                print(f"  - {e}")
            return 1
        print("MONEY-CELL RATCHET OK")
        return 0
    if args.cmd == "stamp":
        stamp_ttl(args.ttl_key or "kg_fresh")
        print(f"stamped {args.ttl_key or 'kg_fresh'} @ {_utc()}")
        return 0
    if args.cmd == "diff":
        print(plan_diff(args.cls, args.text, args.other_class, args.other_text))
        return 0
    if args.cmd == "map-class":
        print(map_class(args.cls, args.text))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
