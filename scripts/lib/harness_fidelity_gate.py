#!/usr/bin/env python3
"""Harness fidelity gate — ntest must drive real prod/QA entry paths.

Problem: green ntest that SQL-seeds money state, truncates failure tables, or
soft-fails FAILED batches → PASS locally while QA/prod FAIL on the real flow.

Policy (fail closed on mask patterns; declare smart bypasses):
  REAL     — fire real apiName / batch job / orch Request; wait COMPLETED; DB value asserts
  SEEDED   — allowed only when declared under case.fidelity.seeded with reason
             (quarantine, fixture restore, labd gap, synthetic job_time)
  FORBIDDEN as undeclared default for smoke_tier=money + verify_mode runtime|RUNTIME_VERIFIED:
             truncate/delete batch_failure_audit, SQL mutate Accrued/Posted,
             soft_fail=True on money batch waits, ACCEPTANCE_STRICT=0 as Pass path

Smart bypass OK when declared (not required to resolve for the flow under test).
Masking a known prod failure mode is NOT smart bypass — use a separate dirty case
or fidelity.out_of_scope with explicit reason.

Usage:
  python3 scripts/lib/harness_fidelity_gate.py check
  python3 scripts/lib/harness_fidelity_gate.py check --hard
  python3 scripts/lib/harness_fidelity_gate.py report
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "scripts/testing/registry.json"

# Undeclared hits of these in the case cmd/script → error for money runtime cases.
FORBIDDEN_UNDECLARED: list[tuple[str, re.Pattern[str], str]] = [
    (
        "audit_truncate",
        re.compile(
            r"TRUNCATE\s+TABLE\s+\S*batch_failure_audit|"
            r"DELETE\s+FROM\s+\S*batch_failure_audit|"
            r"CLEAR_BATCH_FAILURE_AUDIT\s*[:=]\s*[\"']?1",
            re.I,
        ),
        "Clears batch_failure_audit / enables CLEAR_BATCH_FAILURE_AUDIT=1 — "
        "masks SkipListener/ClassCast poison that QA/prod still hit. "
        "Declare fidelity.seeded=[audit_clear] only for debug; default must be 0.",
    ),
    (
        "sql_mutate_accrued",
        re.compile(
            r"UPDATE\s+mfi_accounting\.interest_accrual_details|"
            r"SET\s+total_accrued_amount\s*=|"
            r"SET\s+total_accrual_posted_amount\s*=",
            re.I,
        ),
        "SQL-mutates Accrued/Posted — bypasses interestAccrualCalculation/Posting. "
        "Declare fidelity.seeded=[iad_sql_scale] only when the case is NOT claiming calc/posting correctness.",
    ),
    (
        "sql_delete_labd",
        re.compile(r"DELETE\s+FROM\s+\S*loan_account_billing_details", re.I),
        "Deletes LABD rows to open a billing boundary — declare "
        "fidelity.seeded=[labd_gap_for_billing_boundary] (smart bypass OK).",
    ),
    (
        "soft_fail_money_batch",
        re.compile(r"soft_fail\s*=\s*True"),
        "soft_fail=True swallows FAILED batches — money cases must use soft_fail=False "
        "or declare fidelity.seeded=[soft_fail_allowed] with out_of_scope reason.",
    ),
    (
        "acceptance_strict_off",
        re.compile(r"ACCEPTANCE_STRICT\s*=\s*[\"']?0"),
        "ACCEPTANCE_STRICT=0 must never be the Pass path for money runtime cases.",
    ),
]

# Declared seeded keys that neutralize a forbidden pattern family.
SEEDED_ALLOWS: dict[str, frozenset[str]] = {
    "audit_truncate": frozenset({"audit_clear", "audit_truncate"}),
    "sql_mutate_accrued": frozenset({"iad_sql_scale", "iad_seed"}),
    "sql_delete_labd": frozenset({"labd_gap_for_billing_boundary"}),
    "soft_fail_money_batch": frozenset({"soft_fail_allowed"}),
    "acceptance_strict_off": frozenset({"acceptance_strict_off_debug"}),
}

ALLOWED_SEEDED_HINTS = frozenset(
    {
        "quarantine_portfolio",
        "fixture_snapshot_restore",
        "labd_gap_for_billing_boundary",
        "job_time_synthetic",
        "stack_ensure_skip_restart",
        "audit_clear",
        "audit_truncate",
        "iad_sql_scale",
        "iad_seed",
        "soft_fail_allowed",
        "acceptance_strict_off_debug",
        "aging_seed",
        "excess_seed",
        "docs_stub_payload",
        # EOD chain fired on selected days instead of every calendar day. Only valid
        # when the reduced cadence is PROVEN to reproduce the same defects as the full
        # daily walk — posting-days-only under-fires SHG distribute and hides the
        # per-segment break, whereas +1 intermediate calc per gap does not.
        "roll_cadence_hop",
        # LOS-side row the sync consumer updates (mfi_los.disburse_loan_process). Seeding the
        # target row is fixture, not outcome — the failure_reason under assert is still written
        # by DisbursementSyncService, never by the harness.
        "los_disburse_process_seed",
        # Prior loans for the payload's customers closed before each scenario. Without it the
        # second scenario for a customer dies on 134494 (active loan for product) before the
        # validation under test runs, and the matrix silently degrades into codes that prove
        # nothing. Must drain the disburse consumer to lag 0 first — resetting mid-flight wedges
        # it on a Yugabyte row lock.
        "customer_loans_closed_reset",
    }
)

MONEY_VERIFY = frozenset({"runtime", "RUNTIME_VERIFIED", "stage_partial", "STAGE_PARTIAL"})


def _load_registry() -> dict[str, Any]:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def _is_money_runtime(case: dict[str, Any]) -> bool:
    if case.get("smoke_tier") != "money":
        return False
    vm = (case.get("verify_mode") or case.get("acceptance", {}).get("verify_mode") or "").strip()
    return vm in MONEY_VERIFY or vm.lower() in {"runtime", "runtime_verified", "stage_partial"}


def _resolve_script(case: dict[str, Any]) -> Path | None:
    cmd = (case.get("cmd") or "").strip()
    if not cmd:
        return None
    # e.g. bash scripts/testing/flowtest/run_foo.sh
    parts = cmd.split()
    for p in parts:
        if p.endswith(".sh") or p.endswith(".py"):
            path = ROOT / p if not p.startswith("/") else Path(p)
            if path.is_file():
                return path
            # run_*.sh → sibling scenarios/*.py
            if path.name.startswith("run_") and path.suffix == ".sh":
                scen = path.parent / "scenarios" / (path.stem.replace("run_", "", 1) + ".py")
                if scen.is_file():
                    return scen
    return None


def _script_bundle_text(script: Path) -> str:
    texts = [script.read_text(encoding="utf-8", errors="replace")]
    # If shell wrapper, also read invoked python scenario
    if script.suffix == ".sh":
        m = re.search(r'(scripts/testing/flowtest/scenarios/\S+\.py)', texts[0])
        if m:
            py = ROOT / m.group(1)
            if py.is_file():
                texts.append(py.read_text(encoding="utf-8", errors="replace"))
        # also default mapping run_X.sh → scenarios/X.py
        scen = script.parent / "scenarios" / (script.stem.replace("run_", "", 1) + ".py")
        if scen.is_file() and scen.read_text(encoding="utf-8", errors="replace") not in texts:
            texts.append(scen.read_text(encoding="utf-8", errors="replace"))
    # defaults in registry checked separately
    return "\n".join(texts)


def _seeded_keys(case: dict[str, Any]) -> set[str]:
    fid = case.get("fidelity") or {}
    seeded = fid.get("seeded") or []
    out: set[str] = set()
    for item in seeded:
        if isinstance(item, str):
            out.add(item)
        elif isinstance(item, dict) and item.get("key"):
            out.add(str(item["key"]))
    return out


def check_case(cid: str, case: dict[str, Any]) -> list[str]:
    if not _is_money_runtime(case):
        return []
    errs: list[str] = []
    fid = case.get("fidelity")
    seeded = _seeded_keys(case)

    if not isinstance(fid, dict):
        errs.append(
            f"{cid}: money runtime case missing fidelity block "
            f"(entry/apis/seeded/out_of_scope) — see harness_fidelity_gate.py"
        )
    else:
        entry = (fid.get("entry") or "").strip()
        if entry not in {"batch_api", "http_api", "orch_request", "kafka", "mixed", "sim"}:
            errs.append(
                f"{cid}: fidelity.entry must be batch_api|http_api|orch_request|kafka|mixed|sim "
                f"(got {entry!r})"
            )
        if entry == "sim" and (case.get("verify_mode") or "").lower() in {
            "runtime",
            "runtime_verified",
        }:
            errs.append(
                f"{cid}: fidelity.entry=sim conflicts with verify_mode runtime — "
                "use orch_sibling_sim / processor_mirror_sim verify_mode"
            )
        for k in seeded:
            if k not in ALLOWED_SEEDED_HINTS:
                errs.append(
                    f"{cid}: fidelity.seeded unknown key {k!r} — "
                    f"extend ALLOWED_SEEDED_HINTS or use a listed key"
                )

    # Scan defaults + script for forbidden masks
    blob = json.dumps(case.get("defaults") or {}) + "\n"
    script = _resolve_script(case)
    if script is not None:
        blob += _script_bundle_text(script)

    for family, rx, msg in FORBIDDEN_UNDECLARED:
        if not rx.search(blob):
            continue
        allow = SEEDED_ALLOWS.get(family, frozenset())
        if seeded & allow:
            # Special: audit_clear allowed only if default CLEAR is 0 or documented debug
            if family == "audit_truncate":
                defaults = case.get("defaults") or {}
                if str(defaults.get("CLEAR_BATCH_FAILURE_AUDIT", "0")) == "1":
                    errs.append(
                        f"{cid}: CLEAR_BATCH_FAILURE_AUDIT default must be \"0\" for money "
                        f"runtime Pass; set =1 only ad-hoc for debug (still declare "
                        f"fidelity.seeded audit_clear). {msg}"
                    )
            continue
        errs.append(f"{cid}: undeclared {family}: {msg}")

    return errs


def check(*, hard: bool = False) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). hard promotes missing-fidelity warnings if already present."""
    reg = _load_registry()
    errors: list[str] = []
    warnings: list[str] = []
    for cid, case in reg.items():
        if cid.startswith("_") or not isinstance(case, dict):
            continue
        case_errs = check_case(cid, case)
        for e in case_errs:
            if "missing fidelity block" in e and not hard:
                warnings.append(e)
            else:
                errors.append(e)
    return errors, warnings


def report() -> int:
    reg = _load_registry()
    rows = []
    for cid, case in sorted(reg.items()):
        if cid.startswith("_") or not isinstance(case, dict):
            continue
        if not _is_money_runtime(case):
            continue
        fid = case.get("fidelity") or {}
        script = _resolve_script(case)
        rows.append(
            {
                "id": cid,
                "verify_mode": case.get("verify_mode"),
                "has_fidelity": bool(case.get("fidelity")),
                "entry": fid.get("entry"),
                "seeded": list(_seeded_keys(case)),
                "script": str(script.relative_to(ROOT)) if script else None,
                "issues": check_case(cid, case),
            }
        )
    out = {
        "generated_by": "harness_fidelity_gate.py",
        "money_runtime_cases": len(rows),
        "with_fidelity": sum(1 for r in rows if r["has_fidelity"]),
        "with_issues": sum(1 for r in rows if r["issues"]),
        "cases": rows,
    }
    dest = ROOT / "scripts/testing/harness_fidelity_inventory.json"
    dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {dest} ({out['money_runtime_cases']} money runtime cases, "
          f"{out['with_issues']} with issues)")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Harness fidelity gate")
    p.add_argument("cmd", nargs="?", default="check", choices=["check", "report"])
    p.add_argument(
        "--hard",
        action="store_true",
        help="Missing fidelity block is ERROR (default: WARN until ratchet complete)",
    )
    p.add_argument(
        "--fail-on-warn",
        action="store_true",
        help="Exit 1 if warnings present",
    )
    args = p.parse_args()
    if args.cmd == "report":
        return report()

    errors, warnings = check(hard=args.hard)
    for w in warnings:
        print(f"WARN: {w}")
    if errors:
        print("harness-fidelity FAIL:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(
        f"harness-fidelity PASS"
        + (f" ({len(warnings)} warn)" if warnings else "")
    )
    if args.fail_on_warn and warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
