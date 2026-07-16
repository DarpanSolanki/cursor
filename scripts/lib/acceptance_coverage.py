#!/usr/bin/env python3
"""Fail-closed acceptance-coverage gate (any money/service ship — not DFC-only).

Required dimensions (when a domain opts into enforcement):
  happy_path | boundary_zero | dirty_state | replay_idempotency |
  partial_failure | downstream_ui | adjacent_sibling

A changed money path resolves to domain(s) via accounting_flow_domains.json.
Each required dimension must be covered by a registry case that declares it
under ``acceptance.dimensions``, with verify_mode runtime|stage_partial|orch_sibling_sim|
processor_mirror_sim. Explicit N/A needs ``acceptance.na`` with evidence.

Anti-patterns in case notes/scripts that allow a known QA fail mode also FAIL.

Usage:
  python3 scripts/lib/acceptance_coverage.py check --domain death_foreclosure
  python3 scripts/lib/acceptance_coverage.py check --from-pending
  python3 scripts/lib/acceptance_coverage.py report --missing
  python3 scripts/lib/acceptance_coverage.py self-test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOMAINS = ROOT / "scripts" / "lib" / "accounting_flow_domains.json"
REGISTRY = ROOT / "scripts" / "testing" / "registry.json"
MANIFEST = ROOT / "scripts" / "lib" / "acceptance_coverage_manifest.json"
PENDING = ROOT / ".cursor" / ".pending-ship-work.json"

ALL_DIMENSIONS = (
    "happy_path",
    "boundary_zero",
    "dirty_state",
    "replay_idempotency",
    "partial_failure",
    "downstream_ui",
    "adjacent_sibling",
)

VERIFY_OK = frozenset(
    {
        "runtime",
        "stage_partial",
        "orch_sibling_sim",
        "processor_mirror_sim",
        "RUNTIME_VERIFIED",
        "STAGE_PARTIAL",
        "ORCH_SIBLING_SIM",
        "PROCESSOR_MIRROR_SIM",
    }
)

# Substrings that mean "this assert allows the exact QA fail mode" (subset Pass).
NOTE_ANTIPATTERNS = (
    "OK A2 netting is acceptable",
    "allow prin > amount",
    "subset verification is enough",
    "webapp verified (partial)",
    "overview-only verified",
    "skip webapp APIs",
)

# Webapp-bound APIs that ship gates treat as UI impact when touched / declared.
WEBAPP_UI_APIS = frozenset(
    {
        "getloanaccountsummarydetails",
        "getloanaccountoverviewdetails",
        "getloanaccountstatement",
        "getdeathforeclosuredetails",
        "getloanaccountdetails",
        "getloanaccountrepaymentscheduledetails",
        "gettransactionpartitiondetails",
        "fetchloanforeclosuresimulationdetails",
    }
)

# ui_fields tokens that count as webapp-bound field coverage (not SQL-only).
WEBAPP_UI_FIELD_MARKERS = (
    "interest_details.accrued_amount",
    "interest_details.original_amount",
    "getLoanAccountSummaryDetails",
    "getLoanAccountOverviewDetails",
    "getLoanAccountStatement",
    "DFC_PRTL_BILL",
    "payment_details_list",
    "account_overview_list",
    "transaction_list",
)


def _load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest() -> dict:
    m = _load_json(MANIFEST)
    if not m:
        # Sensible defaults when manifest not yet present
        return {
            "version": 1,
            "required_dimensions_default": [
                "happy_path",
                "dirty_state",
                "replay_idempotency",
                "downstream_ui",
            ],
            "enforced_domains": ["death_foreclosure"],
            "backlog_domains": {},
        }
    return m


def _domains() -> dict:
    return (_load_json(DOMAINS).get("domains") or {})


def _registry() -> dict:
    return _load_json(REGISTRY)


def case_acceptance(case: dict) -> dict:
    acc = case.get("acceptance")
    if isinstance(acc, dict):
        return acc
    return {}


def covered_dimensions(case_id: str, case: dict) -> set[str]:
    acc = case_acceptance(case)
    dims = set(acc.get("dimensions") or [])
    # Legacy: verify_mode alone does not imply dimension coverage.
    return {d for d in dims if d in ALL_DIMENSIONS}


def case_verify_mode(case: dict) -> str:
    acc = case_acceptance(case)
    vm = (acc.get("verify_mode") or case.get("verify_mode") or "").strip()
    return vm


def note_antipatterns(case_id: str, case: dict) -> list[str]:
    blob = " ".join(
        [
            str(case.get("note") or ""),
            str(case_acceptance(case).get("note") or ""),
        ]
    )
    hits = [p for p in NOTE_ANTIPATTERNS if p in blob]
    return [f"{case_id}: note anti-pattern {h!r}" for h in hits]


def ui_fields_ok(case: dict) -> list[str]:
    """downstream_ui requires explicit ui_fields (webapp-bound) or ui_asserted=true with fields.

    UI-impacting money ships must name webapp API response fields — SQL-only ui_fields
    that never appear on summary/overview/statement fail closed when webapp_required.
    """
    acc = case_acceptance(case)
    dims = set(acc.get("dimensions") or [])
    if "downstream_ui" not in dims:
        return []
    fields = [str(f) for f in (acc.get("ui_fields") or [])]
    if not fields and acc.get("ui_asserted") is not True:
        return [
            "downstream_ui claimed without ui_fields[] or ui_asserted=true "
            "(cannot claim webapp verified on subset)"
        ]
    if not fields and acc.get("ui_asserted") is True:
        return [
            "downstream_ui ui_asserted=true without ui_fields[] — list webapp response "
            "fields (summary Accrued/Original, statement DFC_PRTL_BILL, overview status)"
        ]
    # Prefer at least one webapp-bound marker so SQL-only lists cannot fake UI coverage.
    webapp_required = acc.get("webapp_required", True)
    if webapp_required and fields:
        blob = " ".join(fields)
        if not any(m in blob for m in WEBAPP_UI_FIELD_MARKERS):
            return [
                "downstream_ui ui_fields lack webapp-bound markers "
                f"(need one of {list(WEBAPP_UI_FIELD_MARKERS)[:5]}…) — "
                "SQL-only fields are not webapp verified"
            ]
    return []


def check_domain(domain: str, *, enforce: bool) -> list[str]:
    errors: list[str] = []
    man = _manifest()
    domains = _domains()
    reg = _registry()
    d = domains.get(domain) or {}
    if not d:
        return [f"unknown domain: {domain}"]

    required = list(
        (man.get("domain_required") or {}).get(domain)
        or man.get("required_dimensions_default")
        or ["happy_path"]
    )
    case_ids = []
    for key in ("impact_cases", "deep_cases", "release_cases"):
        case_ids.extend(d.get(key) or [])
    # de-dupe preserve order
    seen: set[str] = set()
    ordered: list[str] = []
    for c in case_ids:
        if c not in seen:
            seen.add(c)
            ordered.append(c)

    covered: set[str] = set()
    na: dict[str, str] = {}
    for cid in ordered:
        case = reg.get(cid) or {}
        if not case:
            errors.append(f"{domain}: registry missing case {cid}")
            continue
        errors.extend(note_antipatterns(cid, case))
        errors.extend([f"{cid}: {e}" for e in ui_fields_ok(case)])
        acc = case_acceptance(case)
        for dim, reason in (acc.get("na") or {}).items():
            if dim in ALL_DIMENSIONS and reason:
                na[dim] = f"{cid}: {reason}"
        dims = covered_dimensions(cid, case)
        vm = case_verify_mode(case)
        if dims and vm and vm not in VERIFY_OK:
            errors.append(f"{cid}: verify_mode {vm!r} not in {sorted(VERIFY_OK)}")
        covered |= dims

    missing = [dim for dim in required if dim not in covered and dim not in na]
    if missing and enforce:
        errors.append(
            f"{domain}: missing acceptance dimensions {missing} "
            f"(covered={sorted(covered)} na={sorted(na)}; "
            f"add acceptance.dimensions on impact/release cases or acceptance.na with evidence)"
        )
    elif missing and not enforce:
        # backlog — report only when --missing
        pass

    return errors


def domains_from_pending(pending: dict) -> list[str]:
    """Map pending files/apis to domain keys via path_hints / api_hints."""
    domains = _domains()
    files = " ".join(pending.get("files") or []).lower()
    apis = " ".join(pending.get("apis") or []).lower()
    blob = files + " " + apis
    hit: list[str] = []
    for name, d in domains.items():
        hints = [h.lower() for h in (d.get("path_hints") or [])]
        api_hints = [h.lower() for h in (d.get("api_hints") or [])]
        if any(h and h in blob for h in hints + api_hints):
            hit.append(name)
    return hit


def check_from_pending(*, hard: bool = True) -> int:
    pending = _load_json(PENDING)
    if not pending or not pending.get("files"):
        print("acceptance-coverage: nothing pending — OK")
        return 0
    tier = (pending.get("tier") or "workspace").lower()
    if tier not in ("money", "service"):
        print("acceptance-coverage: workspace-only — OK")
        return 0

    man = _manifest()
    enforced = set(man.get("enforced_domains") or [])
    backlog = man.get("backlog_domains") or {}
    targets = domains_from_pending(pending)
    if not targets:
        # Money ship with no domain match — fail closed for money tier
        if tier == "money":
            msg = (
                "acceptance-coverage FAIL: money pending but no domain matched "
                "files/apis — add path_hints or declare domain"
            )
            print(msg, file=sys.stderr)
            return 1 if hard else 0
        print("acceptance-coverage: no domain matched — OK")
        return 0

    errors: list[str] = []
    for dom in targets:
        enforce = dom in enforced
        if not enforce and dom in backlog:
            print(f"acceptance-coverage: {dom} backlog ({backlog[dom]}) — skip enforce")
            continue
        errors.extend(check_domain(dom, enforce=enforce or tier == "money" and dom in enforced))

    # Always scan note anti-patterns on resolved impact cases for matched domains
    if errors:
        print("acceptance-coverage FAIL:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1 if hard else 0
    print("acceptance-coverage PASS:", ", ".join(targets))
    return 0


def report_missing() -> int:
    man = _manifest()
    enforced = set(man.get("enforced_domains") or [])
    backlog = man.get("backlog_domains") or {}
    print("# Acceptance coverage report")
    for name in sorted(_domains()):
        status = "ENFORCED" if name in enforced else ("BACKLOG" if name in backlog else "UNTRACKED")
        errs = check_domain(name, enforce=True)
        missing = [e for e in errs if "missing acceptance dimensions" in e]
        other = [e for e in errs if e not in missing]
        print(f"\n## {name} [{status}]")
        if missing:
            for m in missing:
                print(f"  MISSING: {m}")
        elif not errs:
            print("  OK — required dimensions covered or N/A")
        for o in other:
            print(f"  ISSUE: {o}")
        if name in backlog:
            print(f"  backlog: {backlog[name]}")
    return 0


def self_test() -> int:
    """Prove subset-only verification is rejected; complete matrix passes."""
    # Synthetic domain check using fixture shapes (no pending file mutation).
    failures = 0

    # 1) Note anti-pattern detected
    bad_case = {
        "note": "OK A2 netting is acceptable for handoff",
        "acceptance": {"dimensions": ["happy_path"], "verify_mode": "runtime"},
    }
    hits = note_antipatterns("t.bad", bad_case)
    if not hits:
        print("SELF-TEST FAIL: anti-pattern note not detected")
        failures += 1
    else:
        print("SELF-TEST OK: anti-pattern note rejected")

    # 2) downstream_ui without fields rejected
    ui_case = {
        "acceptance": {
            "dimensions": ["downstream_ui"],
            "verify_mode": "runtime",
        }
    }
    ui_err = ui_fields_ok(ui_case)
    if not ui_err:
        print("SELF-TEST FAIL: webapp-without-fields not rejected")
        failures += 1
    else:
        print("SELF-TEST OK: webapp verified without ui_fields rejected")

    # 3) Complete acceptance accepted by covered_dimensions
    good = {
        "acceptance": {
            "dimensions": list(ALL_DIMENSIONS),
            "verify_mode": "runtime",
            "ui_fields": [
                "getLoanAccountSummaryDetails",
                "interest_details.accrued_amount",
                "interest_details.original_amount",
                "getLoanAccountStatement",
                "DFC_PRTL_BILL",
                "tm.original_amount",
                "lapd.principal_amount",
            ],
            "webapp_required": True,
        }
    }
    if covered_dimensions("t.good", good) != set(ALL_DIMENSIONS):
        print("SELF-TEST FAIL: full matrix not covered")
        failures += 1
    elif ui_fields_ok(good):
        print("SELF-TEST FAIL: good ui_fields still errored")
        failures += 1
    else:
        print("SELF-TEST OK: complete matrix accepted")

    # 4) Live death_foreclosure must be enforceable once registry annotated
    live = check_domain("death_foreclosure", enforce=True)
    if live:
        print("SELF-TEST WARN: death_foreclosure still has gaps (expected until registry annotated):")
        for e in live:
            print(f"  - {e}")
        # Not a hard self-test fail — annotation is separate step; gate unit proves mechanisms.
    else:
        print("SELF-TEST OK: death_foreclosure live coverage PASS")

    return 1 if failures else 0


def main() -> int:
    p = argparse.ArgumentParser(description="Acceptance coverage gate")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check")
    c.add_argument("--domain", action="append", default=[])
    c.add_argument("--from-pending", action="store_true")
    c.add_argument("--soft", action="store_true")

    sub.add_parser("report").add_argument(
        "--missing", action="store_true", help="Print per-domain missing dims"
    )
    sub.add_parser("self-test")

    args = p.parse_args()
    if args.cmd == "self-test":
        return self_test()
    if args.cmd == "report":
        return report_missing()
    if args.cmd == "check":
        if args.from_pending:
            return check_from_pending(hard=not args.soft)
        if not args.domain:
            print("pass --domain or --from-pending", file=sys.stderr)
            return 2
        man = _manifest()
        enforced = set(man.get("enforced_domains") or [])
        errs: list[str] = []
        for d in args.domain:
            errs.extend(check_domain(d, enforce=d in enforced or True))
        if errs:
            print("acceptance-coverage FAIL:", file=sys.stderr)
            for e in errs:
                print(f"  - {e}", file=sys.stderr)
            return 1 if not args.soft else 0
        print("acceptance-coverage PASS:", ", ".join(args.domain))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
