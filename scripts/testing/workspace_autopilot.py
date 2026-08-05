#!/usr/bin/env python3
"""
Workspace autopilot — classify tasks, detect mid-tab task shifts, auto preflight,
ship-and-continue (push after verified test without waiting for session end).
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / ".cursor/.autopilot-state.json"
sys.path.insert(0, str(ROOT / "scripts/testing"))
sys.path.insert(0, str(ROOT / "scripts/lib"))

from agent_router import classify  # noqa: E402
from ship_push_queue import (  # noqa: E402
    clear_queue,
    mark_pushed,
    mark_test_passed,
    queue_ready,
    self_check as queue_self_check,
)
from ship_push_lock import ship_push_lock  # noqa: E402


@dataclass
class Step:
    id: str
    cmd: str
    auto: bool = True
    tier: str = "fast"
    note: str = ""
    par: bool = False


@dataclass
class Plan:
    classification: str
    risk: str
    input: str
    api_hint: str | None
    skills: list[str]
    task_shift: bool = False
    shift_reason: str = ""
    steps: list[Step] = field(default_factory=list)
    end_steps: list[Step] = field(default_factory=list)
    agent_directives: list[str] = field(default_factory=list)


# Post-analysis option board — printed on BUG/RCA / INVESTIGATION / analyse / next-action plans.
# Agents must not end analysis with evidence-only next steps; every tier must be listed.
OPTIONS_BOARD_DIRECTIVE = (
    "OPTIONS BOARD (mandatory after analysis): emit **L0 + L1 + L2 + L3** before recommending "
    "a single next step. Include code/config/ops options when they exist — do not bury code fixes "
    "behind evidence-gathering. Format each tier: change / where / effort / risk / what it does NOT fix. "
    "Use `N/A — <one line>` only when a tier truly does not apply. Evidence/prod checks may be a "
    "prerequisite under a tier, never a substitute for the board. "
    "See `.cursor/skills/architect-thinking/tiered-solutions.md` + `.cursor/rules/00-workspace-core.mdc`."
)


def _needs_options_board(kind: str, text: str) -> bool:
    """True when the plan is analysis / RCA / ticket triage / next-action (not pure social)."""
    if kind in ("BUG/RCA", "INVESTIGATION", "FEATURE", "FIX+SHIP", "OPS_SQL", "CODE/DAO"):
        return True
    t = (text or "").lower()
    return bool(
        re.search(
            r"\b(analyse|analyze|analysis|rca|root.?cause|next.?action|action.?plan|jira|"
            r"performance|bottleneck|slowness|optimis|optimiz|what.?can.?we.?do|"
            r"options?|tiered|l0|hotfix|proper.?fix)\b",
            t,
        )
    )


def load_state() -> dict:
    if not STATE_PATH.is_file():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def is_continuation(text: str) -> bool:
    t = text.strip().lower()
    if len(t) > 80:
        return False
    return bool(
        re.match(
            r"^(yes|yep|yeah|ok|okay|go ahead|proceed|continue|implement( it)?|ship it|do it|looks good)\b",
            t,
        )
    )


def detect_task_shift(plan: Plan, state: dict) -> tuple[bool, str]:
    if is_continuation(plan.input):
        return False, "continuation — same task context"
    prev_kind = state.get("last_classification")
    if not prev_kind:
        return False, "first task in tab"
    reasons: list[str] = []
    if prev_kind != plan.classification:
        reasons.append(f"type {prev_kind}→{plan.classification}")
    prev_api = state.get("last_api_hint") or ""
    new_api = plan.api_hint or ""
    if prev_api != new_api:
        reasons.append(f"api {prev_api or '-'}→{new_api or '-'}")
    if plan.risk == "High" and state.get("last_risk") != "High":
        reasons.append("risk→High")
    if reasons:
        return True, "; ".join(reasons)
    return False, ""


def _enhance_kind(text: str, base: dict) -> dict:
    t = text.lower()
    kind = base["classification"]
    if re.search(r"\b(implement|add feature|enhance|build|create api)\b", t) and kind == "GENERAL":
        base["classification"] = "FEATURE"
    if re.search(r"\b(explain|how does|what is|walk me|understand)\b", t) and kind == "GENERAL":
        base["classification"] = "INVESTIGATION"
    if re.search(
        r"\b(improve workspace|workspace max|setup yourself|autopilot|performant|automate|full workspace|super machine|super agent|disappointed|manual)\b",
        t,
    ):
        base["classification"] = "WORKSPACE"
    if re.search(r"\b(release details|release mail)\b", t):
        base["classification"] = "RELEASE"
    # Prod/ops mutation SQL (CRR soft-archive, DTFC reset, adhoc UPDATE packs)
    if re.search(
        r"\b(prod\s+sql|ops\s+sql|adhoc\s+(sql|update)|soft-?archive\s+crr|"
        r"client_request_response_log|prod_neft|dtfc\s+reinit|prod\s+patch\s+sql)\b",
        t,
    ) or (
        "scripts/sql/adhoc" in t
        and re.search(r"\b(update|reset|archive|patch)\b", t)
    ):
        base["classification"] = "OPS_SQL"
        skills = list(base.get("skills") or [])
        if "prod-ops-sql-impact" not in skills:
            skills.insert(0, "prod-ops-sql-impact")
        if "open-final-file" not in skills:
            skills.append("open-final-file")
        base["skills"] = skills
    return base


def _fallback_api_hint(text: str) -> str | None:
    """Pick explicit API-looking tokens when the router catalogue has no match."""
    match = re.search(r"\b([a-z][A-Za-z0-9]*(?:Api|API))\b", text)
    if match:
        return match.group(1)
    match = re.search(r"\bapi(?:Name)?\s*[:=]?\s*`?([a-z][A-Za-z0-9]+)`?", text, re.I)
    return match.group(1) if match else None


def _kg_stale() -> bool:
    r = subprocess.run(
        ["bash", "scripts/bin/kg-quick-check.sh"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return r.returncode != 0


def build_plan(
    text: str,
    *,
    task_shift: bool = False,
    shift_reason: str = "",
    light_preflight: bool = False,
) -> Plan:
    base = _enhance_kind(text, classify(text))
    kind = base["classification"]
    api = base.get("api_hint") or _fallback_api_hint(text)
    skills = list(base.get("skills") or ["workspace-router"])

    if kind == "WORKSPACE":
        skills = ["workspace-self-improve", "super-agent"]
    elif kind == "RELEASE":
        skills = ["release-details", "capture-proof", "workspace-close"]
    elif kind == "OPS_SQL":
        skills = ["prod-ops-sql-impact", "open-final-file", "workspace-router"]
    elif kind == "FEATURE":
        skills = ["super-agent", "workspace-router"]
    elif kind in ("BUG/RCA", "FIX+SHIP"):
        if "capture-proof" not in skills:
            skills.append("capture-proof")

    steps: list[Step] = []
    train_plan: dict | None = None
    if not light_preflight:
        steps.append(
            Step(
                "preflight",
                "bash scripts/bin/agent-ops.sh preflight",
                auto=True,
                tier="fast",
                par=True,
            )
        )

    if not light_preflight:
        try:
            from train_sync import sync_plan  # type: ignore

            train_plan = sync_plan(text)
            if train_plan.get("train") and train_plan.get("needs_sync"):
                tr = train_plan["train"]
                dom = train_plan["domain"]
                steps.append(
                    Step(
                        "train_sync",
                        "python3 scripts/lib/train_sync.py apply "
                        f"--train {shlex.quote(tr)} --domain {shlex.quote(dom)}",
                        auto=True,
                        tier="slow",
                        note=(
                            f"User train {tr} ≠ live {train_plan.get('live_branch')} "
                            f"on {train_plan.get('primary_repo')}"
                        ),
                    )
                )
        except Exception:
            train_plan = None

    state = load_state()
    skip_kg = (
        not task_shift
        and not light_preflight
        and (time.time() - float(state.get("kg_validate_at") or 0) < 300)
    )
    if not skip_kg:
        steps.append(
            Step(
                "kg_validate",
                "python3 cursor-bundle/kg/bin/kg.py validate",
                auto=True,
                tier="fast",
                par=True,
            )
        )

    if task_shift:
        steps.append(
            Step(
                "task_shift_sync",
                "python3 scripts/testing/sync_engine.py fast-sync --quiet",
                auto=True,
                tier="fast",
                note=shift_reason,
            )
        )
        steps.append(
            Step(
                "kg_state",
                "head -n 25 .cursor/workspace-kg-state.md",
                auto=True,
                tier="fast",
                note="Re-read KG branch-set on task shift",
            )
        )
        if base.get("risk") == "High" or kind in ("FIX+SHIP", "TEST", "BUG/RCA", "WORKSPACE"):
            steps.append(
                Step(
                    "kg_fresh",
                    "bash scripts/bin/kg-ensure-fresh.sh --quiet",
                    auto=True,
                    tier="medium",
                )
            )
    elif not light_preflight and (
        kind in ("FIX+SHIP", "WORKSPACE", "BUG/RCA")
        or re.search(r"\b(kg|watermark|branch|train|accounting|disburse|foreclos|dpi)\b", text, re.I)
        or (time.time() - float(state.get("kg_validate_at") or 0) > 600)
        or _kg_stale()
    ):
        steps.append(
            Step(
                "kg_fresh",
                "bash scripts/bin/kg-ensure-fresh.sh --quiet",
                auto=True,
                tier="medium",
            )
        )

    if api and not light_preflight:
        if kind in ("BUG/RCA", "FEATURE", "FIX+SHIP", "TEST"):
            steps.append(
                Step(
                    "trace",
                    f"bash scripts/bin/super-agent.sh trace {api} --fast",
                    auto=True,
                    tier="fast",
                    note=f"API `{api}` (cross-repo)",
                )
            )
        branch_match = re.search(
            r"\b(?:mfi_(?:integration|release)_v)?(\d+(?:\.\d+){1,4})\b",
            text,
            re.I,
        ) or re.search(r"\b(mfi_(?:integration|release)_v\d+(?:\.\d+)+)\b", text, re.I)
        if kind in ("BUG/RCA", "FIX+SHIP") or branch_match:
            if branch_match:
                base_branch = (
                    branch_match.group(1)
                    if branch_match.group(1).startswith("mfi_")
                    else f"mfi_integration_v{branch_match.group(1)}"
                )
            else:
                base_branch = ""
            base_arg = f" --base {shlex.quote(base_branch)}" if base_branch else ""
            steps.append(
                Step(
                    "fixed_elsewhere",
                    "python3 cursor-bundle/kg/bin/kg.py fixed-elsewhere "
                    f"{shlex.quote(api)}{base_arg} --fetch-if-stale",
                    auto=True,
                    tier="fast",
                    note="Fail-closed reuse gate: only VERIFIED_FIXED_CLEAN may be proposed",
                )
            )
        elif kind not in ("WORKSPACE", "SYNC", "RELEASE"):
            steps.append(
                Step(
                    "orient",
                    f"bash scripts/bin/super-agent.sh orient {api} --fast",
                    auto=True,
                    tier="fast",
                    note=f"API `{api}`",
                )
            )

    if kind == "TEST":
        skills = ["autonomous-workspace-ops", "super-agent"]
        if api:
            steps.append(
                Step(
                    "before_test",
                    f"bash scripts/bin/agent-ops.sh before-test {api}",
                    auto=True,
                    tier="medium",
                )
            )
    elif kind == "BUG/RCA":
        skills = ["super-agent", "autonomous-workspace-ops"]
        if re.search(r"\b(dpi|delayed payment)\b", text, re.I):
            skills.insert(0, "dpi-feature-branch-gate")
    elif kind == "FIX+SHIP":
        skills = ["autonomous-workspace-ops", "capture-proof", "workspace-close"]
        steps.append(
            Step(
                "ship_test_plan",
                "python3 scripts/lib/ship_test_plan.py --from-pending --json",
                auto=True,
                tier="fast",
                note="Automated impact/deep/release plan",
            )
        )
        if base.get("risk") in ("High", "Medium") or api:
            steps.append(
                Step(
                    "hot_path_scan",
                    "bash scripts/bin/hot-path-scan.sh --from-pending",
                    auto=True,
                    tier="fast",
                    note="Workspace-wide perf heuristic (not batch-only)",
                )
            )
    elif kind == "FEATURE":
        if base.get("risk") in ("High", "Medium"):
            steps.append(
                Step(
                    "hot_path_scan",
                    "bash scripts/bin/hot-path-scan.sh --from-pending",
                    auto=True,
                    tier="fast",
                )
            )
    elif kind == "SYNC":
        steps.append(
            Step("intel_sync", "python3 scripts/testing/sync_engine.py fast-sync --quiet", auto=True)
        )
    elif kind == "WORKSPACE":
        skills = ["workspace-self-improve", "super-agent"]
        steps.extend([
            Step(
                "corroborate",
                "python3 scripts/testing/corroborate.py --quick --no-bus",
                auto=True,
                tier="fast",
            ),
            Step("max_pass", "bash scripts/bin/workspace-max-pass.sh", auto=True, tier="fast"),
            Step("status", "bash scripts/bin/super-agent.sh status", auto=True, tier="fast"),
        ])
    elif kind == "CODE/DAO":
        skills.append("reuse-queries-java-filter")
        steps.append(
            Step(
                "hot_path_scan",
                "bash scripts/bin/hot-path-scan.sh --from-pending",
                auto=True,
                tier="fast",
            )
        )

    end_steps: list[Step] = []
    if kind in ("FIX+SHIP", "WORKSPACE", "RELEASE") or re.search(
        r"\b(ship|fix|implement|commit)\b", text, re.I
    ):
        end_steps.extend([
            Step(
                "kg_watermark",
                "python3 scripts/lib/kg_watermark_gate.py check --block-verified",
                auto=True,
                tier="fast",
            ),
            Step(
                "close",
                "bash scripts/bin/workspace-close.sh --from-pending",
                auto=True,
                tier="medium",
            ),
        ])

    directives = [
        "Run autopilot on EVERY new user message in this tab — task type may have changed.",
        "Extended session: re-read `.cursor/workspace-kg-state.md` + run `kg watermark` when resuming after branch checkout.",
        "Do not ask the user to run scripts — autopilot + hooks handle ops.",
        "Hot-path perf gate (workspace-wide): no DAO/N+1 in loops; precompute before day loops — see .cursor/rules/10-quality-gates.mdc.",
        "After verified test + commit: push runs via ship-and-continue (do not wait for session end).",
    ]
    if task_shift:
        directives.insert(
            0,
            f"TASK SHIFT detected ({shift_reason}) — prior context may not apply; follow new skills.",
        )
    if base.get("risk") == "High":
        directives.append("Read gaps-and-risks.md for this area before proposing fixes.")
    if kind == "TEST" and api:
        directives.append(f"Run `ntest auto {api}`; on PASS hook queues push automatically.")
    if train_plan and train_plan.get("train"):
        tr = train_plan["train"]
        if train_plan.get("needs_sync"):
            directives.insert(
                0,
                f"TRAIN SYNC: message names {tr} — autopilot runs scoped sync-branches "
                f"(domain={train_plan.get('domain')}) before KG analysis. "
                "kg_align alone does NOT checkout branches.",
            )
        elif train_plan.get("aligned"):
            directives.insert(
                0,
                f"TRAIN: already on {tr} ({train_plan.get('primary_repo')}); "
                "kg_align/fresh apply to this checkout — not a branch switch.",
            )
    if kind == "OPS_SQL":
        directives.append(
            "OPS_SQL: run prod-ops-sql-impact skill; answer “is contract-native FAIL enough?” "
            "before soft-archive or LOCAL_RESET_ARCHIVED; output Minimal permanent / Contract-native / "
            "Anything lost / Code-proven checklist."
        )
    # Post-analysis OPTIONS BOARD — never end analysis with evidence-only / single next-step.
    # L0–L3 (or N/A one-liner) must appear so code/config/ops options are always selectable.
    if _needs_options_board(kind, text):
        directives.append(OPTIONS_BOARD_DIRECTIVE)
    if api and kind in ("BUG/RCA", "FEATURE", "FIX+SHIP", "TEST"):
        directives.append(
            "Trace already ran — do not re-run orient unless full crud/why needed."
        )
    if api and kind in ("BUG/RCA", "FIX+SHIP"):
        directives.append(
            "Cross-branch gate: REUSE_FORBIDDEN unless RESULT contains REUSE_ALLOWED / "
            "VERIFIED_FIXED_CLEAN. Never implement from FILE_TOUCH_HINTS or VERIFIED_FIXED_DIVERGED. "
            "Stale upstream refs / ✗ fixed_elsewhere = do not invent a port."
        )

    # Mixed-train banner (always computed from git-workspace-state.json)
    try:
        from train_banner import banner_and_stop  # type: ignore

        banner, stop = banner_and_stop(text, kind)
        directives.insert(0, banner)
        if stop:
            directives.insert(1, stop)
    except Exception as exc:  # noqa: BLE001
        directives.insert(0, f"TRAINS: (banner failed: {exc})")

    # KG watermark / provisional gate (Upgrade 6)
    try:
        from kg_state_banner import banner_and_stop as kg_banner_and_stop  # type: ignore

        kg_line, kg_stop = kg_banner_and_stop(text, kind)
        # Insert after train banner block
        insert_at = 0
        while insert_at < len(directives) and (
            directives[insert_at].startswith("TRAINS:")
            or directives[insert_at].startswith("HARD STOP [MIXED]")
        ):
            insert_at += 1
        directives.insert(insert_at, kg_line)
        if kg_stop:
            directives.insert(insert_at + 1, kg_stop)
    except Exception as exc:  # noqa: BLE001
        directives.insert(0, f"KG STATE: (banner failed: {exc})")

    # Process router PLAN (Upgrade 8) — speed by selection
    try:
        from process_router import compute_plan as proc_plan  # type: ignore

        already: set[str] = set()
        if not task_shift:
            try:
                from route_ledger import load as ledger_load

                led = ledger_load()
                if led.get("status") == "open":
                    already = {s.get("id") for s in led.get("ran") or [] if s.get("ok")}
                    already |= set(led.get("cached") or [])
            except Exception:
                already = set()

        pp = proc_plan(kind, text, api_hint=api, already_ran=already)
        directives.insert(0, pp["line"])
        directives.insert(1, pp["goal_line"] + "  (close with `route-ledger.sh close`)")
        if not light_preflight and not is_continuation(text):
            try:
                from route_ledger import open_task

                open_task(
                    process_class=pp["process_class"],
                    classification=kind,
                    text=text,
                    plan=pp,
                )
            except Exception:
                pass
        else:
            try:
                from route_ledger import resume_line

                rl = resume_line()
                if rl:
                    directives.insert(2, rl)
            except Exception:
                pass
        # Honor SKIP/CACHED: drop matching auto steps (never weaken money required — those stay RUN)
        skip_names = {n for n, _ in pp.get("skip") or []}
        cached_names = {n for n, _ in pp.get("cached") or []}
        filtered: list[Step] = []
        for s in steps:
            pname = STEP_TO_PROCESS.get(s.id)
            if pname and pname in skip_names:
                continue
            if pname and pname in cached_names:
                continue
            filtered.append(s)
        steps = filtered
    except Exception as exc:  # noqa: BLE001
        directives.insert(0, f"PLAN: (router failed: {exc})")

    return Plan(
        classification=kind,
        risk=base.get("risk", "Medium"),
        input=text,
        api_hint=api,
        skills=skills,
        task_shift=task_shift,
        shift_reason=shift_reason,
        steps=steps,
        end_steps=end_steps,
        agent_directives=directives,
    )


def _run_cmd(cmd: str, quiet: bool) -> tuple[int, str]:
    p = subprocess.run(cmd, shell=True, cwd=str(ROOT), capture_output=True, text=True, timeout=600)
    out = (p.stdout or "") + (p.stderr or "")
    if not quiet:
        print(out.rstrip())
    return p.returncode, out


# Steps the router may drop when its process is skipped/cached — a step here must be
# fully covered by that process, or dropping it silently loses work.
STEP_TO_PROCESS = {
    "kg_validate": "kg_validate",
    "kg_fresh": "kg_fresh_sync",
    "hot_path_scan": "hot_path_scan",
    "ship_test_plan": "ship_discipline",
    "before_test": "services_probe",
    "dpi_sanity": "dpi_sanity",
}

# Cost attribution only — never used to drop a step. `preflight` does more than probe
# services, so it is priced against services_probe but always runs when planned.
STEP_COST_KEY = {
    **STEP_TO_PROCESS,
    "preflight": "services_probe",
    "kg_state": "kg_watermark_gate",
    "impact_tests": "impact_tests",
    "compile": "compile_java",
}


def _record_step(step_id: str, ok: bool, elapsed: float) -> None:
    """Feed the measured cost back into the router weights and the task ledger.

    Autopilot step ids are commands; the matrix is keyed by process name. Record under the
    process name so the learned weight lands on the node the planner actually prices.
    """
    pname = STEP_COST_KEY.get(step_id, step_id)
    try:
        from route_ledger import note_step

        note_step(pname, ok=ok, elapsed_s=elapsed)
    except Exception:
        pass
    if not ok:
        return
    try:
        from process_router import load_matrix, stamp_ttl

        ttl_key = ((load_matrix().get("processes") or {}).get(pname) or {}).get("ttl_key")
        if ttl_key:
            stamp_ttl(ttl_key)
    except Exception:
        pass


def _run_batch(batch: list[Step], quiet: bool) -> list[dict]:
    """Run independent steps concurrently; output is buffered so it still reads in order."""
    if len(batch) == 1:
        step = batch[0]
        t0 = time.time()
        rc, out = _run_cmd(step.cmd, quiet=quiet)
        return [
            {
                "id": step.id,
                "rc": rc,
                "elapsed_s": round(time.time() - t0, 2),
                "ok": rc == 0,
                "_out": out,
            }
        ]
    with ThreadPoolExecutor(max_workers=min(len(batch), 4)) as pool:
        futures = {pool.submit(_timed_run, s): s for s in batch}
        done = {}
        for fut in as_completed(futures):
            step = futures[fut]
            try:
                done[step.id] = fut.result()
            except Exception as exc:  # noqa: BLE001
                done[step.id] = {"id": step.id, "rc": 1, "ok": False, "_out": str(exc)}
    ordered = [done[s.id] for s in batch if s.id in done]
    if not quiet:
        for r in ordered:
            if r.get("_out"):
                print(r["_out"], end="" if r["_out"].endswith("\n") else "\n")
    return ordered


def _timed_run(step: Step) -> dict:
    t0 = time.time()
    rc, out = _run_cmd(step.cmd, quiet=True)
    return {
        "id": step.id,
        "rc": rc,
        "elapsed_s": round(time.time() - t0, 2),
        "ok": rc == 0,
        "_out": out,
    }


def execute_steps(steps: list[Step], *, quiet: bool = False, dry_run: bool = False) -> list[dict]:
    results: list[dict] = []
    state = load_state()
    pending: list[Step] = []
    halt = False

    def flush() -> bool:
        nonlocal pending
        if not pending:
            return True
        batch_results = _run_batch(pending, quiet)
        pending = []
        keep_going = True
        for r in batch_results:
            out = r.pop("_out", "")
            results.append(r)
            _record_step(r["id"], r.get("ok", False), r.get("elapsed_s", 0))
            if r["id"] == "kg_validate" and r.get("rc") == 0:
                state["kg_validate_at"] = time.time()
            tier = next((s.tier for s in steps if s.id == r["id"]), "fast")
            if r.get("rc") != 0 and tier != "fast":
                r["tail"] = out[-800:]
                keep_going = False
        return keep_going

    for step in steps:
        if halt:
            break
        if not step.auto:
            if not flush():
                break
            results.append({"id": step.id, "skipped": True, "reason": "manual"})
            continue
        if dry_run:
            results.append({"id": step.id, "cmd": step.cmd, "dry_run": True})
            continue
        if step.par:
            pending.append(step)
            continue
        if not flush():
            halt = True
            break
        pending = [step]
        if not flush():
            halt = True
            break
    if not halt:
        flush()

    state["last_task_at"] = time.time()
    save_state(state)
    return results


def plan_to_dict(plan: Plan) -> dict[str, Any]:
    return {
        "classification": plan.classification,
        "risk": plan.risk,
        "task_shift": plan.task_shift,
        "shift_reason": plan.shift_reason,
        "input": plan.input,
        "api_hint": plan.api_hint,
        "skills": [f".cursor/skills/{s}/SKILL.md" for s in plan.skills],
        "steps": [asdict(s) for s in plan.steps],
        "end_steps": [asdict(s) for s in plan.end_steps],
        "agent_directives": plan.agent_directives,
    }


def ship_and_continue(*, force: bool = False, quiet: bool = False) -> dict[str, Any]:
    """Close if needed, push verified repo, clear queue — then agent can start next task."""
    with ship_push_lock() as locked:
        if not locked:
            return {"ok": True, "pushed": False, "reason": "ship-and-continue already running"}

        ready, msg = queue_ready(force=force)
        if not ready:
            return {"ok": True, "pushed": False, "reason": msg}

        repo = msg
        out: dict[str, Any] = {"repo": repo, "pushed": False}

        gate = ROOT / "scripts/lib/ship_push_gate.py"
        if (ROOT / ".cursor/.pending-ship-work.json").is_file():
            r = subprocess.run(["python3", str(gate), "--needs-close"], cwd=str(ROOT), capture_output=True)
            if r.returncode == 0:
                rc, close_out = _run_cmd(
                    "bash scripts/bin/workspace-close.sh --from-pending", quiet=quiet
                )
                out["close_rc"] = rc
                if rc != 0:
                    out["ok"] = False
                    out["reason"] = "workspace-close failed"
                    out["tail"] = close_out[-500:]
                    return out

        r = subprocess.run(
            ["bash", "scripts/bin/enrichment-audit.sh", "--pre-push"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            out["ok"] = False
            out["reason"] = "enrichment pre-push blocked (changelog?)"
            out["tail"] = (r.stdout + r.stderr)[-500:]
            return out

        push = subprocess.run(
            ["bash", "scripts/bin/push-origin.sh", "--repo", repo],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        if not quiet and push.stdout:
            print(push.stdout.rstrip())
        if push.returncode != 0:
            out["ok"] = False
            out["reason"] = "git push failed"
            out["tail"] = ((push.stdout or "") + (push.stderr or ""))[-500:]
            out["push_rc"] = push.returncode
            return out

        mark_pushed(repo)
        out["ok"] = True
        out["pushed"] = True
        out["reason"] = f"pushed {repo} to origin"
        return out


def cmd_task(args: argparse.Namespace) -> int:
    text = " ".join(args.words)
    state = load_state()
    continuation = is_continuation(text) and bool(state.get("last_classification"))

    if continuation:
        shifted, reason = False, "continuation — same task context"
        light = True
        plan = build_plan(
            state.get("last_input") or text,
            task_shift=False,
            shift_reason=reason,
            light_preflight=True,
        )
        # Keep prior classification for agent routing
        plan.classification = state["last_classification"]
        plan.api_hint = state.get("last_api_hint")
        plan.input = text
    else:
        draft = build_plan(text)
        shifted, reason = detect_task_shift(draft, state)
        light = (
            not shifted
            and state.get("last_classification") == draft.classification
            and (state.get("last_api_hint") or "") == (draft.api_hint or "")
            and (time.time() - float(state.get("last_task_at") or 0)) < 120
        )
        plan = build_plan(
            text,
            task_shift=shifted,
            shift_reason=reason,
            light_preflight=light,
        )

    results = execute_steps(plan.steps, quiet=args.quiet, dry_run=args.dry_run)

    state = load_state()
    if not continuation:
        state["last_classification"] = plan.classification
        state["last_api_hint"] = plan.api_hint
        state["last_risk"] = plan.risk
        state["last_input"] = text[:240]
        state["last_task_text"] = text[:240]
    save_state(state)
    # stamp TTLs for steps that ran successfully (CACHED short-circuit next task)
    try:
        from process_router import stamp_ttl

        for r in results:
            if r.get("ok") and r.get("id") in ("kg_validate", "kg_fresh", "preflight"):
                stamp_ttl("kg_fresh")
            if r.get("ok") and r.get("id") in ("services", "services_probe"):
                stamp_ttl("services")
    except Exception:
        pass

    state = load_state()
    state["task_count"] = int(state.get("task_count") or 0) + 1
    save_state(state)

    if args.json:
        print(json.dumps({"plan": plan_to_dict(plan), "executed": results}, indent=2))
        return 0

    print("## Workspace autopilot — task plan")
    # Always surface PLAN + train + KG banners first when present
    top_prefixes = ("PLAN [", "GOAL [", "RESUME [", "TRAINS:", "KG STATE:", "HARD STOP")
    top_lines = [d for d in plan.agent_directives if d.startswith(top_prefixes)]
    for line in top_lines:
        print(f"**{line}**")
    if plan.task_shift:
        print(f"**TASK SHIFT:** {plan.shift_reason}")
    elif light or continuation:
        print("**Light preflight** (same task / continuation)")
    print(f"**Classification:** {plan.classification}  **Risk:** {plan.risk}")
    if plan.api_hint:
        print(f"**API hint:** `{plan.api_hint}`")
    print("\n**Skills:**")
    for s in plan.skills:
        print(f"- `.cursor/skills/{s}/SKILL.md`")
    print("\n**Auto-ran:**")
    for r in results:
        mark = "✓" if r.get("ok") else ("·" if r.get("dry_run") else "✗")
        extra = f" ({r.get('elapsed_s')}s)" if r.get("elapsed_s") else ""
        print(f"  {mark} {r.get('id')}{extra}")
    if plan.end_steps:
        print("\n**After fix verified (auto):** close → cooldown → `ship-and-continue` → next task")
    print("\n**Directives:**")
    for d in plan.agent_directives:
        if d.startswith(top_prefixes):
            continue  # already printed at top
        print(f"- {d}")
    failed = [r for r in results if r.get("rc", 0) != 0 and not r.get("dry_run")]
    return 1 if failed else 0


def cmd_session(_: argparse.Namespace) -> int:
    execute_steps([Step("health", "bash scripts/bin/workspace-health.sh", auto=True)], quiet=True)
    hub = ROOT / ".cursor/workspace-intelligence-state.md"
    if not hub.is_file() or hub.stat().st_mtime < time.time() - 3600:
        execute_steps(
            [Step("hub", "python3 scripts/testing/sync_engine.py fast-session --quiet", auto=True)],
            quiet=True,
        )
    return 0


def cmd_end(args: argparse.Namespace) -> int:
    steps = [
        Step(
            "human_edit_fp",
            "python3 scripts/lib/human_edit_detect.py close",
            auto=True,
            tier="fast",
        ),
        Step("kg_fresh", "bash scripts/bin/kg-ensure-fresh.sh --quiet", auto=True, tier="medium"),
        Step(
            "kg_watermark",
            "python3 scripts/lib/kg_watermark_gate.py check --block-verified",
            auto=True,
            tier="fast",
        ),
        Step("disk_clean", "bash scripts/bin/workspace-disk-clean.sh --clean", auto=True),
        Step("hygiene", "bash scripts/bin/workspace-hygiene.sh --clean", auto=True),
    ]
    pending = ROOT / ".cursor/.pending-ship-work.json"
    # GC zombies before deciding close — empty pending must not FAIL end.
    try:
        sys.path.insert(0, str(ROOT / "scripts/lib"))
        from pending_ship_gc import gc_pending  # noqa: WPS433

        gc_pending(ROOT)
    except Exception:
        pass
    gate = ROOT / "scripts/lib/ship_push_gate.py"
    if pending.is_file():
        steps.append(
            Step("ntest_validate", "python3 scripts/testing/ntest.py validate", auto=True, tier="fast")
        )
        steps.append(
            Step(
                "registry_companion",
                "python3 scripts/lib/registry_companion_gate.py check --hard",
                auto=True,
                tier="fast",
            )
        )
        steps.append(
            Step(
                "ship_discipline",
                "python3 scripts/lib/ship_discipline_gate.py check",
                auto=True,
                tier="fast",
            )
        )
        r = subprocess.run(["python3", str(gate), "--satisfied"], cwd=str(ROOT), capture_output=True)
        if r.returncode != 0:
            steps.append(
                Step("close", "bash scripts/bin/workspace-close.sh --from-pending", auto=True, tier="medium")
            )
    steps.append(Step("hub", "bash scripts/bin/write-intelligence-hub.sh", auto=True))
    results = execute_steps(steps, quiet=args.quiet)

    # LEARN close (Upgrade 8) — capture → propose → enrichment decision
    try:
        from autonomy_loop import learn_close, wall_clock_log
        from process_router import map_class, stamp_ttl

        stamp_ttl("kg_fresh")
        last = load_state()
        text = str(last.get("last_task_text") or last.get("last_input") or "task end")
        kind = str(last.get("last_classification") or "GENERAL")
        t0 = time.time()
        learn = learn_close(text=text, classification=kind)
        elapsed = round(time.time() - t0, 2)
        wall_clock_log(map_class(kind, text), elapsed)
        results.append({"id": "learn_close", "ok": True, "elapsed_s": elapsed, **learn})
        if not args.quiet:
            print(
                f"  ✓ learn_close {learn.get('learning_id')} "
                f"tier={learn.get('enrichment_tier')} ({elapsed}s)"
            )
    except Exception as exc:  # noqa: BLE001
        results.append({"id": "learn_close", "ok": False, "error": str(exc)})
        if not args.quiet:
            print(f"  · learn_close skipped: {exc}")

    try:
        from route_ledger import close_task

        declared = {x.strip() for x in (args.declared or "").split(",") if x.strip()}
        closed = close_task(declared=declared, evidence_tier=args.evidence_tier)
        term = closed.get("terminal") or {}
        results.append({"id": "terminal_check", "ok": bool(term.get("ok")), **closed})
        if not args.quiet and term.get("results"):
            print(f"  {'✓' if term.get('ok') else '✗'} terminal_check "
                  f"[{term.get('process_class')}] {'MET' if term.get('ok') else 'UNMET'}")
            for r in term["results"]:
                if not r["ok"]:
                    print(f"      ✗ {r['predicate']} — {r['note']}")
    except Exception as exc:  # noqa: BLE001
        results.append({"id": "terminal_check", "ok": False, "error": str(exc)})

    ship = ship_and_continue(force=False, quiet=args.quiet)
    results.append({"id": "ship_and_continue", **ship})

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            if r.get("id") == "ship_and_continue":
                if r.get("pushed"):
                    print(f"  ✓ pushed {r.get('repo')}")
                elif r.get("reason"):
                    print(f"  · push: {r.get('reason')}")
            else:
                print(f"  {'✓' if r.get('ok') else '✗'} {r.get('id')}")
    failed = [r for r in results if r.get("rc", 0) not in (None, 0) and not r.get("skipped")]
    if ship.get("ok") is False:
        return 1
    return 1 if failed else 0


def cmd_mark_verified(args: argparse.Namespace) -> int:
    data = mark_test_passed(api=args.api or "", repo=args.repo or None)
    if args.json and not args.push:
        print(json.dumps(data, indent=2))
    elif not args.quiet and not args.push:
        print(
            f"verified: api={data.get('api') or '-'} repo={data.get('repo') or '-'} "
            f"push after {data.get('cooldown_sec')}s cooldown"
        )
    if args.push:
        if not args.force:
            wait = max(0.0, float(data.get("ready_after") or 0) - time.time())
            if wait > 0:
                time.sleep(wait)
        ship = ship_and_continue(force=args.force, quiet=args.quiet)
        if args.json:
            print(json.dumps({"verified": data, "ship": ship}, indent=2))
        elif not args.quiet:
            if ship.get("pushed"):
                print(f"  ✓ {ship.get('reason')}")
            elif ship.get("reason"):
                print(f"  · {ship.get('reason')}")
        return 0 if ship.get("ok", True) else 1
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Self-test autopilot stack — no push, no destructive ops."""
    checks: list[dict] = []
    fail = 0

    def add(cid: str, ok: bool, detail: str = "") -> None:
        nonlocal fail
        checks.append({"id": cid, "ok": ok, "detail": detail})
        if not ok:
            fail += 1

    # Binaries + hooks
    add("autopilot_sh", (ROOT / "scripts/bin/workspace-autopilot.sh").is_file())
    hooks = ROOT / ".cursor/hooks.json"
    add("hooks_json", hooks.is_file())
    if hooks.is_file():
        h = json.loads(hooks.read_text(encoding="utf-8"))
        starts = [x.get("command", "") for x in h.get("hooks", {}).get("sessionStart", [])]
        add("hook_kg_session", any("kg-session" in c for c in starts))
        add("hook_autopilot_session", any("workspace-autopilot-session" in c for c in starts))
        stops = [x.get("command", "") for x in h.get("hooks", {}).get("stop", [])]
        add("hook_stop_close", any("stop-ship" in c for c in stops))

    # Classify + shift logic (no subprocess)
    p1 = build_plan("explain disbursement flow")
    p2 = build_plan("run disburseLoan test")
    shifted, _ = detect_task_shift(p2, {"last_classification": p1.classification, "last_api_hint": None})
    add("task_shift_detect", shifted)
    cont, _ = detect_task_shift(build_plan("go ahead"), {"last_classification": "TEST"})
    add("continuation_skip_shift", not cont)
    # cmd_task continuation path (logic mirror)
    add("continuation_phrase", is_continuation("go ahead"))

    # Queue dry checks
    for qc in queue_self_check():
        add(f"queue_{qc['id']}", qc["ok"], str(qc.get("detail", "")))

    # Dry-run plan steps exist
    plan = build_plan("fix dpi billing", task_shift=True)
    add("plan_has_steps", len(plan.steps) >= 2, f"{len(plan.steps)} steps")
    cross_branch_plan = build_plan(
        "fix loanRecurringPaymentBatchApi on branch 3.7.1", task_shift=True
    )
    fixed_steps = [s for s in cross_branch_plan.steps if s.id == "fixed_elsewhere"]
    add(
        "plan_fixed_elsewhere",
        len(fixed_steps) == 1
        and "--base mfi_integration_v3.7.1" in fixed_steps[0].cmd
        and "|| echo" not in fixed_steps[0].cmd,
        fixed_steps[0].cmd if fixed_steps else "missing",
    )
    sys.path.insert(0, str(ROOT / "scripts/lib"))
    import train_sync as _train_sync_mod

    train_plan_msg = build_plan("parent-child INT ±1 on branch 3.4.2.4")
    train_steps = [s for s in train_plan_msg.steps if s.id == "train_sync"]
    add(
        "train_sync_module",
        _train_sync_mod.sync_plan("branch 3.4.2.4")["train"] == "mfi_integration_v3.4.2.4",
    )
    add(
        "plan_train_sync_step",
        len(train_steps) == 1
        or bool(
            train_plan_msg.agent_directives
            and any("TRAIN:" in d or "TRAIN SYNC:" in d for d in train_plan_msg.agent_directives)
        ),
        train_steps[0].cmd if train_steps else "aligned-or-missing",
    )

    # Ship gate import
    r = subprocess.run(
        ["python3", str(ROOT / "scripts/lib/ship_push_gate.py"), "--satisfied"],
        cwd=str(ROOT),
        capture_output=True,
    )
    add("ship_gate_cli", r.returncode in (0, 1), "satisfied or pending")

    # Corroborate module
    add("corroborate_py", (ROOT / "scripts/testing/corroborate.py").is_file())
    add("orch_index_py", (ROOT / "scripts/testing/orch_index.py").is_file())
    cr = subprocess.run(
        [sys.executable, str(ROOT / "scripts/testing/corroborate.py"), "--quick", "--no-bus", "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=15,
    )
    if cr.returncode in (0, 1) and cr.stdout.strip():
        try:
            cd = json.loads(cr.stdout)
            add("corroborate_quick", True, f"score={cd.get('score')}")
        except json.JSONDecodeError:
            add("corroborate_quick", cr.returncode == 0)
    else:
        add("corroborate_quick", False, "corroborate failed to run")

    # Lock acquire (isolated path — production lock may be held by background push)
    import os
    os.environ["SHIP_PUSH_LOCK_PATH"] = str(STATE_PATH.parent / ".ship-push-lock-verify")
    Path(os.environ["SHIP_PUSH_LOCK_PATH"]).unlink(missing_ok=True)
    with ship_push_lock(timeout_sec=2) as locked:
        add("ship_lock", locked, "acquired" if locked else "timeout")

    if args.json:
        print(json.dumps({"ok": fail == 0, "checks": checks}, indent=2))
    else:
        print("=== workspace autopilot verify ===")
        for c in checks:
            mark = "✓" if c["ok"] else "✗"
            d = f" — {c['detail']}" if c.get("detail") else ""
            print(f"  {mark} {c['id']}{d}")
        print(f"=== {'PASS' if fail == 0 else 'FAIL'} ({len(checks) - fail}/{len(checks)}) ===")
    return 1 if fail else 0


def cmd_ship(args: argparse.Namespace) -> int:
    ship = ship_and_continue(force=args.force, quiet=args.quiet)
    if args.json:
        print(json.dumps(ship, indent=2))
    elif ship.get("pushed"):
        print(f"ship-and-continue: {ship.get('reason')}")
    else:
        print(f"ship-and-continue: {ship.get('reason')}")
    return 0 if ship.get("ok", True) else 1


def cmd_plan(args: argparse.Namespace) -> int:
    plan = build_plan(" ".join(args.words))
    print(json.dumps(plan_to_dict(plan), indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Workspace autopilot")
    sub = p.add_subparsers(dest="cmd", required=True)

    pt = sub.add_parser("task")
    pt.add_argument("words", nargs="+")
    pt.add_argument("--json", action="store_true")
    pt.add_argument("--dry-run", action="store_true")
    pt.add_argument("--quiet", action="store_true")
    pt.set_defaults(func=cmd_task)

    sub.add_parser("session").set_defaults(func=cmd_session)

    pe = sub.add_parser("end")
    pe.add_argument("--json", action="store_true")
    pe.add_argument("--quiet", action="store_true")
    pe.add_argument(
        "--declared",
        default="",
        help="Comma-list of declared terminal predicates (evidence_cited,knowledge_loops,options_board)",
    )
    pe.add_argument(
        "--evidence-tier",
        default="UNSTATED",
        help="RUNTIME_VERIFIED | STAGE_PARTIAL | ORCH_SIBLING_SIM | PROCESSOR_MIRROR_SIM | NOT_VERIFIED",
    )
    pe.set_defaults(func=cmd_end)

    pm = sub.add_parser("mark-verified", help="Record test/sanity PASS; optional auto-push")
    pm.add_argument("--api", default="")
    pm.add_argument("--repo", default="")
    pm.add_argument("--push", action="store_true", help="Run ship-and-continue after cooldown")
    pm.add_argument("--force", action="store_true", help="Skip push cooldown")
    pm.add_argument("--json", action="store_true")
    pm.add_argument("--quiet", action="store_true")
    pm.set_defaults(func=cmd_mark_verified)

    ps = sub.add_parser("ship-and-continue", help="Close + push if verified queue ready")
    ps.add_argument("--force", action="store_true")
    ps.add_argument("--json", action="store_true")
    ps.add_argument("--quiet", action="store_true")
    ps.set_defaults(func=cmd_ship)

    pp = sub.add_parser("plan")
    pp.add_argument("words", nargs="+")
    pp.set_defaults(func=cmd_plan)

    pv = sub.add_parser("verify", help="Self-test autopilot stack (no push)")
    pv.add_argument("--json", action="store_true")
    pv.set_defaults(func=cmd_verify)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
