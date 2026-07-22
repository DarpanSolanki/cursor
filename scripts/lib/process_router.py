#!/usr/bin/env python3
"""Process router — select gates by task class; TTL short-circuit; money-cell ratchet (U8)."""
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
    "RELEASE": "release",
}

MONEY_WORDS = (
    "disburse", "repay", "foreclos", "death", "dfc", "dpi", "money", "ledger",
    "gl ", "neft", "accounting", "payment", "loan", "billing", "accrual",
)
QA_ENV = re.compile(r"\b(qa[1-6]|uat|mfi_qa)\b", re.I)


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_matrix() -> dict:
    return json.loads(MATRIX.read_text(encoding="utf-8"))


def map_class(classification: str, text: str = "") -> str:
    """Fail-closed: ambiguous/money words escalate."""
    t = (text or "").lower()
    c = (classification or "GENERAL").upper()
    base = CLASS_MAP.get(c, "read-only-rca")  # unknown → heavier than question
    if c == "BUG/RCA" and any(w in t for w in ("fix", "implement", "ship", "patch")):
        base = "money-fix" if any(w in t for w in MONEY_WORDS) else "non-money-fix"
    if c in ("FIX+SHIP", "FEATURE") and any(w in t for w in MONEY_WORDS):
        base = "money-fix"
    if c == "TEST" and "dpi" not in t and "batch" not in t and "eod" not in t:
        # generic test without dpi/batch → still batch-dpi column (heavier) if money words
        if any(w in t for w in MONEY_WORDS):
            base = "batch-dpi"
        else:
            base = "non-money-fix"
    if c == "OPS_SQL":
        base = "money-fix"
    if base == "question" and any(w in t for w in MONEY_WORDS):
        base = "read-only-rca"  # escalate
    return base


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


def eval_trigger(trigger: str, text: str, ctx: dict) -> bool:
    t = (text or "").lower()
    if trigger == "api_or_flow_named":
        return bool(ctx.get("api_hint") or re.search(r"\b[a-z]+[A-Z][a-zA-Z]+\b", text or ""))
    if trigger == "code_touch":
        return bool(ctx.get("code_touch") or "fix" in t or "implement" in t)
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
) -> dict:
    man = load_matrix()
    pclass = map_class(classification, text)
    ctx = dict(ctx or {})
    if api_hint:
        ctx["api_hint"] = api_hint
    ttls = man.get("ttls_seconds") or {}
    run: list[str] = []
    skip: list[tuple[str, str]] = []
    cached: list[tuple[str, str]] = []

    for name, meta in (man.get("processes") or {}).items():
        cell = (meta.get("cells") or {}).get(pclass, "required")  # missing → heavier
        decision = resolve_cell(cell, text, ctx)
        if decision == "skip":
            reason = cell if cell == "skip" else f"trigger unmet ({cell})"
            skip.append((name, reason))
            continue
        ttl_key = meta.get("ttl_key")
        fresh, utc = ttl_fresh(ttl_key, ttls)
        if fresh:
            cached.append((name, utc))
            continue
        run.append(name)

    line = (
        f"PLAN [{pclass}]: RUN {','.join(run) or '—'} · "
        f"SKIP {';'.join(f'{n}({r})' for n,r in skip) or '—'} · "
        f"CACHED {';'.join(f'{n}(@{u})' for n,u in cached) or '—'}"
    )
    return {
        "process_class": pclass,
        "classification": classification,
        "run": run,
        "skip": skip,
        "cached": cached,
        "line": line,
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
    ap.add_argument("cmd", choices=["plan", "ratchet", "stamp", "diff", "map-class"])
    ap.add_argument("--class", dest="cls", default="GENERAL")
    ap.add_argument("--text", default="")
    ap.add_argument("--api", default="")
    ap.add_argument("--ttl-key", default="")
    ap.add_argument("--other-class", default="FIX+SHIP")
    ap.add_argument("--other-text", default="money fix disbursement")
    args = ap.parse_args()
    if args.cmd == "plan":
        p = compute_plan(args.cls, args.text, api_hint=args.api or None)
        print(p["line"])
        return 0
    if args.cmd == "ratchet":
        errs = check_money_ratchet()
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
