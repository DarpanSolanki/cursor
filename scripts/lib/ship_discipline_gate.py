#!/usr/bin/env python3
"""Machine-enforced ship discipline — minimal fix, hot-path, verify mode, KG, no guesses.

Agents write `.cursor/.ship-discipline.json` before money-tier ship-loop / workspace-close.
Soft rules failed repeatedly; this gate FAILS closed when pending money work exists.

Usage:
  python3 scripts/lib/ship_discipline_gate.py check
  python3 scripts/lib/ship_discipline_gate.py write --minimal-fix "..." --verify-mode ORCH_SIBLING_SIM \\
      --hot-path PASS --kg SKIP --read-path No --assumptions-none
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PENDING = ROOT / ".cursor" / ".pending-ship-work.json"
DISCIPLINE = ROOT / ".cursor" / ".ship-discipline.json"

REQUIRED_KEYS = (
    "minimal_fix",
    "read_path_change",
    "hot_path_scan",
    "verify_mode",
    "kg_enrichment",
    "assumptions",
)

# Money/service money-repo: fail closed without a written impact matrix (2026-07-19 / 2026-07-22).
IMPACT_REQUIRED_KEYS = (
    "entry_paths",
    "scenario_modes",
    "callers",
    "downstream",
    "modes",
    "account_field",
    "error_codes",
    "happy_path",
    "blast_radius",
    "out_of_scope",
)

MONEY_SERVICE_REPOS = frozenset(
    {
        "trustt-platform-accounting",
        "trustt-platform-payments",
        "trustt-platform-los",
        "novopay-platform-accounting-v2",
        "novopay-platform-payments",
    }
)

VERIFY_MODES = frozenset(
    {
        "RUNTIME_VERIFIED",
        "STAGE_PARTIAL",
        "ORCH_SIBLING_SIM",
        "PROCESSOR_MIRROR_SIM",
        "WORKSPACE_ONLY",
    }
)
HOT_PATH = frozenset({"PASS", "WARN", "N/A"})
KG = frozenset({"FULL", "CASES", "SKIP"})
READ_PATH = frozenset({"Yes", "No"})


def _load(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _pending_looks_money(pending: dict) -> bool:
    files = " ".join(pending.get("files") or []).lower()
    return any(
        h in files
        for h in (
            "/loan/",
            "disburse",
            "foreclos",
            "reopen",
            "repayment",
            "dpi",
            "mandate",
        )
    )


def _pending_money_service_repo(pending: dict) -> bool:
    repos = {r for r in (pending.get("repos") or []) if r}
    if repos & MONEY_SERVICE_REPOS:
        return True
    files = " ".join(pending.get("files") or [])
    return any(r in files for r in MONEY_SERVICE_REPOS)


def _needs_impact_analysis(pending: dict, disc: dict) -> bool:
    tier = (pending.get("tier") or disc.get("tier") or "").lower()
    if tier == "money":
        return True
    if tier == "service" and _pending_money_service_repo(pending):
        return True
    return _pending_looks_money(pending)


def _check_impact_analysis(disc: dict) -> list[str]:
    errors: list[str] = []
    impact = disc.get("impact_analysis")
    if not isinstance(impact, dict):
        errors.append(
            "missing impact_analysis — money/service ships need entry_paths/scenario_modes/"
            "callers/downstream/modes/account_field/error_codes/happy_path/blast_radius/"
            "out_of_scope (see feedback_full_impact_analysis_before_money_ship.md)"
        )
        return errors
    for key in IMPACT_REQUIRED_KEYS:
        val = impact.get(key)
        text = (val if isinstance(val, str) else str(val or "")).strip()
        if len(text) < 8:
            errors.append(f"impact_analysis.{key} missing or too short (min 8 chars)")
    return errors


def needs_discipline(pending: dict) -> bool:
    tier = (pending.get("tier") or "workspace").lower()
    if tier in ("money", "service"):
        return True
    files = " ".join(pending.get("files") or []).lower()
    return any(
        h in files
        for h in (
            "/loan/",
            "orchestration/",
            "processor.java",
            "batch",
            "disburse",
            "foreclos",
            "reopen",
            "dpi",
        )
    )


def check(*, hard: bool = True) -> int:
    pending = _load(PENDING)
    if not pending or not pending.get("files"):
        print("ship-discipline: nothing pending — OK")
        return 0
    if not needs_discipline(pending):
        print("ship-discipline: workspace-only pending — OK (no money discipline)")
        return 0

    disc = _load(DISCIPLINE)
    errors: list[str] = []
    if not disc:
        errors.append(
            f"missing {DISCIPLINE.name} — run: bash scripts/bin/ship-discipline.sh write ..."
        )
    else:
        pend_u = pending.get("updated_at") or ""
        disc_u = disc.get("pending_updated_at") or ""
        if pend_u and disc_u and disc_u < pend_u:
            errors.append(
                f"discipline stale vs pending (discipline={disc_u} pending={pend_u}) — re-write"
            )
        for k in REQUIRED_KEYS:
            if k not in disc:
                errors.append(f"missing key: {k}")
        mf = (disc.get("minimal_fix") or "").strip()
        if len(mf) < 12:
            errors.append("minimal_fix too short (one concrete sentence required)")
        if disc.get("read_path_change") not in READ_PATH:
            errors.append("read_path_change must be Yes|No")
        if disc.get("hot_path_scan") not in HOT_PATH:
            errors.append("hot_path_scan must be PASS|WARN|N/A")
        if disc.get("verify_mode") not in VERIFY_MODES:
            errors.append(f"verify_mode must be one of {sorted(VERIFY_MODES)}")
        if disc.get("kg_enrichment") not in KG:
            errors.append("kg_enrichment must be FULL|CASES|SKIP")
        assumptions = disc.get("assumptions")
        if assumptions is None:
            errors.append("assumptions required (use [] if none)")
        elif assumptions:
            # Guesses not allowed without evidence citation on each item
            for a in assumptions:
                if isinstance(a, dict):
                    if not (a.get("claim") and a.get("evidence")):
                        errors.append(f"assumption needs claim+evidence: {a}")
                else:
                    errors.append(
                        f"assumption must be {{claim, evidence}} not a bare string: {a!r}"
                    )
        if disc.get("overengineering") is True:
            errors.append("overengineering=true is blocked — drop layers and re-write")

        # Money tier, service on accounting/payments/LOS, or money-path files: impact matrix.
        if _needs_impact_analysis(pending, disc):
            errors.extend(_check_impact_analysis(disc))

    # Fail-closed acceptance matrix (any money/service flow — see acceptance_coverage.py).
    import subprocess

    acc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "lib" / "acceptance_coverage.py"), "check", "--from-pending"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if acc.returncode != 0:
        detail = (acc.stderr or acc.stdout or "").strip().splitlines()
        errors.append(
            "acceptance-coverage failed — "
            + (detail[-1] if detail else "required dimensions missing / anti-pattern")
        )

    # Money cases must declare verify_mode (Upgrade 7); domain money ships fail if any
    # touched domain's money impact cases lack verify_mode.
    try:
        import registry_proposals

        vm_errs = registry_proposals.check_money_verify_modes()
        if vm_errs and (pending.get("tier") or "").lower() == "money":
            errors.extend(vm_errs[:12])
            if len(vm_errs) > 12:
                errors.append(f"… +{len(vm_errs) - 12} more money cases missing verify_mode")
        # Ratchet on every money/service check
        if (pending.get("tier") or "").lower() in ("money", "service", "workspace"):
            errors.extend(registry_proposals.check_ratchet())
        try:
            from process_router import check_money_ratchet

            errors.extend(check_money_ratchet())
        except Exception as exc2:  # pragma: no cover
            errors.append(f"money-cell ratchet error: {exc2}")
    except Exception as exc:  # pragma: no cover
        errors.append(f"verify_mode/ratchet gate error: {exc}")

    # Fail-closed reuse-query gate for any *Repository.java / *DAOService.java query change.
    try:
        import reuse_query_gate

        errors.extend(reuse_query_gate.check(pending, disc, root=ROOT))
    except Exception as exc:  # pragma: no cover - defensive
        errors.append(f"reuse-query gate error: {exc}")

    # Local-parity (Upgrade 8 TASK E): schema/masterdata/DDL hand-patch must be migration-backed
    try:
        import local_parity_gate

        if local_parity_gate.schema_or_masterdata_touched(pending):
            pr = local_parity_gate.check_parity(pending)
            print(pr.get("summary") or "")
            if not pr.get("ok"):
                errors.extend(pr.get("errors") or ["local-parity failed"])
            elif disc is not None and disc:
                # stamp ship summary for agents / release notes
                disc = dict(disc)
                disc["local_parity"] = pr.get("summary")
                try:
                    DISCIPLINE.write_text(json.dumps(disc, indent=2) + "\n", encoding="utf-8")
                except OSError:
                    pass
    except Exception as exc:  # pragma: no cover
        errors.append(f"local-parity gate error: {exc}")

    if errors:
        print("ship-discipline FAIL:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        print(
            "Standing: minimal permanent fix · no guesses · hot-path · verify_mode · KG honest.",
            file=sys.stderr,
        )
        return 1 if hard else 0

    print(
        "ship-discipline PASS:",
        disc.get("verify_mode"),
        "|",
        (disc.get("minimal_fix") or "")[:80],
    )
    if disc.get("local_parity"):
        print(disc["local_parity"])
    return 0


def write(args: argparse.Namespace) -> int:
    pending = _load(PENDING)
    assumptions: list = []
    if args.assumptions_none:
        assumptions = []
    elif args.assumption:
        for pair in args.assumption:
            if "=" not in pair:
                print("assumption format claim=evidence", file=sys.stderr)
                return 2
            claim, evidence = pair.split("=", 1)
            assumptions.append({"claim": claim.strip(), "evidence": evidence.strip()})

    data = {
        "written_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pending_updated_at": pending.get("updated_at") or "",
        "tier": pending.get("tier") or args.tier,
        "minimal_fix": args.minimal_fix.strip(),
        "read_path_change": args.read_path,
        "hot_path_scan": args.hot_path,
        "verify_mode": args.verify_mode,
        "kg_enrichment": args.kg,
        "assumptions": assumptions,
        "layers_dropped": args.layers_dropped or "",
        "overengineering": False,
        "apis": pending.get("apis") or [],
    }

    if args.reuse_step:
        data["reuse_query"] = {
            "reuse_queries_step": int(args.reuse_step),
            "existing_methods_checked": list(args.reuse_existing or []),
            "callers_checked": list(args.reuse_caller or []),
            "new_query_justification": (args.reuse_justification or "").strip(),
            "performance_impact": (args.reuse_perf or "").strip(),
        }

    impact = {
        "entry_paths": (args.impact_entry_paths or "").strip(),
        "scenario_modes": (args.impact_scenario_modes or "").strip(),
        "callers": (args.impact_callers or "").strip(),
        "downstream": (args.impact_downstream or "").strip(),
        "modes": (args.impact_modes or "").strip(),
        "account_field": (args.impact_account_field or "").strip(),
        "error_codes": (args.impact_error_codes or "").strip(),
        "happy_path": (args.impact_happy_path or "").strip(),
        "blast_radius": (args.impact_blast_radius or "").strip(),
        "out_of_scope": (args.impact_out_of_scope or "").strip(),
    }
    if any(impact.values()):
        data["impact_analysis"] = impact

    DISCIPLINE.parent.mkdir(parents=True, exist_ok=True)
    DISCIPLINE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {DISCIPLINE}")
    return check(hard=True)


def main() -> int:
    p = argparse.ArgumentParser(description="Ship discipline gate")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check")
    c.add_argument("--soft", action="store_true", help="Warn only")

    w = sub.add_parser("write")
    w.add_argument("--minimal-fix", required=True)
    w.add_argument("--read-path", choices=sorted(READ_PATH), required=True)
    w.add_argument("--hot-path", choices=sorted(HOT_PATH), required=True)
    w.add_argument("--verify-mode", choices=sorted(VERIFY_MODES), required=True)
    w.add_argument("--kg", choices=sorted(KG), required=True)
    w.add_argument("--assumptions-none", action="store_true")
    w.add_argument(
        "--assumption",
        action="append",
        default=[],
        help="claim=evidence (repeatable); prefer --assumptions-none",
    )
    w.add_argument("--layers-dropped", default="")
    w.add_argument("--tier", default="money")
    w.add_argument(
        "--reuse-step",
        choices=["1", "2", "3"],
        help="Reuse-query ladder step used (required if a *Repository/*DAOService query changed)",
    )
    w.add_argument("--reuse-existing", action="append", default=[], help="Existing method checked (repeatable)")
    w.add_argument("--reuse-caller", action="append", default=[], help="Caller verified (repeatable)")
    w.add_argument("--reuse-justification", default="", help="New @Query justification (step 3)")
    w.add_argument("--reuse-perf", default="", help="Performance impact note (index/scan/limit)")
    w.add_argument("--impact-entry-paths", default="", help="Impact matrix: orch APIs/jobs/consumers")
    w.add_argument(
        "--impact-scenario-modes",
        default="",
        help="Impact matrix: last-child / non-last / standalone / replay",
    )
    w.add_argument("--impact-callers", default="", help="Impact matrix: callers (grep changed methods)")
    w.add_argument(
        "--impact-downstream",
        default="",
        help="Impact matrix: webapp APIs, GL, events, registry cases",
    )
    w.add_argument("--impact-modes", default="", help="Impact matrix: CASH vs DIRDR/ACH etc")
    w.add_argument(
        "--impact-out-of-scope",
        default="",
        help="Impact matrix: explicit Out-of-scope rows with evidence",
    )
    w.add_argument("--impact-account-field", default="", help="Impact matrix: account field compared")
    w.add_argument("--impact-error-codes", default="", help="Impact matrix: error codes")
    w.add_argument("--impact-happy-path", default="", help="Impact matrix: happy path still passes")
    w.add_argument("--impact-blast-radius", default="", help="Impact matrix: blast radius")

    args = p.parse_args()
    if args.cmd == "check":
        return check(hard=not args.soft)
    if args.cmd == "write":
        if not args.assumptions_none and not args.assumption:
            print("pass --assumptions-none or --assumption claim=evidence", file=sys.stderr)
            return 2
        return write(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
