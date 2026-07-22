#!/usr/bin/env python3
"""Impact-scoped ntest case resolution for ship-loop (all domains, not DPI-only)."""
from __future__ import annotations

from typing import Callable

# Manual / CI / release — never auto-run on ship-loop
SHIP_NEVER_AUTO_TAGS = frozenset(
    {
        "regression",
        "certify",
        "doctor",
        "demo",
        "perf",
        "preflight",
        "integration",
        "release",
    }
)

# Flow cases added only when path hints match (not via api smoke sweep)
PATH_TRIGGERED_CASES = frozenset(
    {
        "foreclosure.individual_child",
        "foreclosure.dpi_waiver_smoke",
        "foreclosure.loan_prepayment_real",
        "foreclosure.sdcp10255_e2e",
        "reopening.child_payments_parity_sim",
        "dpic.go_live_ud",
        "dpic.grace_e2e",
        "dpic.multi_emi_installment_e2e",
        "dpic.repayment_e2e",
        "dpic.repayment_reversal_e2e",
        "dpic.part_prepayment_write_e2e",
        "dpic.foreclosure_write_e2e",
        "dpic.child_repayment_e2e",
        "dpic.foreclosure_details_flow",
        "dpic.cross_eod_replay_134497",
        "dpic.posting_calendar_regression",
        "dpic.eod_txn_regression",
        "dpic.two_emi_full_chain",
        "dpic.npa_dpi_movement_e2e",
    }
)

# Mandatory on any DPI money-path ship touching calc/booking/billing (SDCP-10497 harness gap)
_DPI_BOOKING_GUARD_CASES = frozenset(
    {
        "dpic.posting_calendar_regression",
        "dpic.cross_eod_replay_134497",
        "dpic.eod_txn_regression",
    }
)

_DPI_BILLING_GUARD_CASES = frozenset(
    {
        "dpic.billing_ud_next_emi",
        "dpic.post_maturity_billing",
        "dpic.post_maturity_billing_catchup",
    }
)

# One consolidated flow for money-tier workspace-close (replaces individual guard cases)
_DPI_SHIP_CLOSE_VERIFY = "dpic.ship_close_verify"
_DPI_GUARD_CASES_IN_SHIP_CLOSE = frozenset(
    {
        "dpic.posting_calendar_regression",
        "dpic.cross_eod_replay_134497",
        "dpic.eod_txn_regression",
        "dpic.billing_ud_next_emi",
        "dpic.post_maturity_billing",
        "dpic.post_maturity_billing_catchup",
        "dpic.grace_e2e",
    }
)

_DPI_FULL_SUITE_CASES = frozenset(
    {
        "dpic.ud_compliance",
        "dpic.dpi_sanity",
        "dpic.extended_regression",
        "dpic.dpi_max_regression",
        "dpic.dpi_regression",
        "dpic.full",
        "dpic.demo.all",
        "dpic.demo.phase1",
        "dpic.demo.phase2",
        "dpic.demo.phase3",
        "dpic.demo.phase4",
        "dpic.integration_smoke",
        "dpic.batch_perf_10k",
        "dpic.regression_preflight",
        "dpic.certify_scenarios",
        "dpic.verify_certified",
        "dpic.full_regression",
    }
)

_CASE_TYPE_RANK = {"batch": 0, "api": 1, "health": 2, "flow": 3}


def path_blob(paths: list[str] | None) -> str:
    return " ".join(p.replace("\\", "/").lower() for p in (paths or []))


def is_ship_auto_case(cid: str, meta: dict) -> bool:
    """Whether ship-loop may run this case without explicit ntest invoke."""
    if not meta or cid.startswith("_"):
        return False
    if cid in _DPI_FULL_SUITE_CASES:
        return False
    if cid.startswith("workspace.doctor"):
        return False
    if cid in ("disbursement.jlg", "disbursement.shg"):
        return False
    scope = meta.get("ship_scope")
    if scope in ("manual", "release", "ci"):
        return False
    if meta.get("ship_auto") is True:
        return True
    if meta.get("ship_auto") is False:
        return False
    tags = set(meta.get("tags") or [])
    if tags & SHIP_NEVER_AUTO_TAGS:
        return False
    ctype = meta.get("type") or ""
    if ctype == "batch":
        return True
    if ctype == "health":
        return True
    if ctype == "flow" and meta.get("quick"):
        return True
    if ctype == "api" and meta.get("quick"):
        # DPI/restructuring read APIs — path-triggered only, not every ship touching shared util
        if tags & {"dpi", "restructuring", "foreclosure"}:
            return meta.get("ship_default") is True
        return True
    if ctype == "flow" and meta.get("ship_default"):
        return True
    return False


def _case_score(cid: str, case: dict) -> int:
    ctype = case.get("type") or ""
    score = (4 - _CASE_TYPE_RANK.get(ctype, 9)) * 100
    if case.get("quick"):
        score += 20
    if cid.startswith("batch."):
        score += 10
    if case.get("wait_batch") is not False and ctype == "batch":
        score += 5
    return score


def registry_case_for_api_ship(
    api: str, reg: dict, *, path_blob_s: str = ""
) -> str:
    """Best ship-eligible registry case for one apiName."""
    best_id = ""
    best_score = -1
    for cid, c in reg.items():
        if cid.startswith("_") or not isinstance(c, dict):
            continue
        if c.get("api") != api:
            continue
        if cid in PATH_TRIGGERED_CASES and not _path_triggered_now(cid, path_blob_s):
            continue
        if not is_ship_auto_case(cid, c) and cid not in PATH_TRIGGERED_CASES:
            continue
        score = _case_score(cid, c)
        if score > best_score:
            best_score = score
            best_id = cid
    return best_id


def _path_triggered_now(cid: str, blob: str) -> bool:
    """True when path hints justify a PATH_TRIGGERED case."""
    rules: dict[str, tuple[str, ...]] = {
        "foreclosure.individual_child": (
            "individualchildloanforeclosure",
            "childloanforeclosureprocessor",
            "childloanforeclosure",
        ),
        "foreclosure.dpi_waiver_smoke": (
            "deathforeclosure",
            "death_foreclosure",
            "loandeathforeclosure",
            "dcf_",
            "/death/",
        ),
        "dpic.go_live_ud": ("golive", "postgolive", "maturity", "overduebase", "verify_go_live"),
        "dpic.grace_e2e": ("grace", "ispastgracegate", "computoverduedate"),
        "dpic.multi_emi_installment_e2e": (
            "multi_emi",
            "latestunpaidintdue",
            "installment_id",
        ),
        "dpic.repayment_e2e": ("/repayment/", "/repay/", "loanrepayment"),
        "dpic.repayment_reversal_e2e": ("reversal", "transactionreversal"),
        "dpic.part_prepayment_write_e2e": ("partprepayment", "loanprepayment", "prepayment"),
        "dpic.foreclosure_write_e2e": (
            "foreclosurewrite",
            "loanforeclosureprocessor",
        ),
        "dpic.child_repayment_e2e": ("childrepayment", "child_repayment"),
        "dpic.foreclosure_details_flow": ("foreclosuredetails", "billed_dpi"),
        "dpic.cross_eod_replay_134497": ("134497", "cross_eod_replay", "client_ref"),
        "dpic.posting_calendar_regression": (
            "dpiaccrualbooking",
            "posting_calendar",
            "verify_dpi_posting",
            "replay_dpi_booking",
            "isaccrualpostingdate",
        ),
        "dpic.eod_txn_regression": (
            "dpiaccrualbooking",
            "dpibilling",
            "eod_txn",
            "verify_dpi_eod_txn",
            "month_end_job_time",
            "setup_qa1_month_end",
        ),
        "dpic.two_emi_full_chain": (
            "two_emi",
            "setup_two_emi",
            "verify_dpi_accrual_slice_integrity",
            "dpiaccrualbooking",
            "dpiaccrualcalculation",
        ),
        "dpic.npa_dpi_movement_e2e": (
            "assetclassif",
            "dpimovement",
            "loanaccountassetcriteria",
            "regular_to_npa",
            "npatoregular",
        ),
        "foreclosure.loan_prepayment_real": ("loanprepayment", "sdcp10255"),
        "foreclosure.sdcp10255_e2e": ("sdcp10255", "sdcp-10255"),
        "dcf.principal_split_sim": (
            "deathforeclosureinsurancewriter",
            "deathforeclosure",
            "dcf_principal_split",
            "dcf_sanity",
            "/death/",
        ),
        "reopening.child_payments_parity_sim": (
            "childloanreopening",
            "loanaccountreopening",
            "loanaccountpaymentsdetailsreversal",
            "tdpqa102",
            "reopening/",
            "group_mfi_orc",
        ),
    }
    hints = rules.get(cid)
    if not hints:
        return False
    return any(h in blob for h in hints)


def expand_path_cases(blob: str, apis: set[str], reg: dict) -> list[str]:
    """Domain path hints → minimal extra cases beyond primary api case."""
    out: list[str] = []

    def add(cid: str) -> None:
        if cid not in reg or cid in out:
            return
        if cid == "foreclosure.dpi_waiver_smoke" and not _dpi_waiver_smoke_applicable():
            return
        meta = reg[cid]
        if cid in PATH_TRIGGERED_CASES and not _path_triggered_now(cid, blob):
            return
        if is_ship_auto_case(cid, meta):
            out.append(cid)
            return
        if cid in PATH_TRIGGERED_CASES:
            out.append(cid)

    if any(
        x in blob
        for x in (
            "disburseloan",
            "/disbursement/",
            "disbursement_details",
            "disburseloanapi",
            "neft",
            "dtfc",
            "clmt",
        )
    ):
        if "disburseLoan" in apis:
            add("disbursement.quick")

    if any(x in blob for x in ("dpdcalc", "loanaccountdpd", "dpd_calc")):
        add("batch.dpd_calc")

    for cid in PATH_TRIGGERED_CASES:
        if (
            cid == "dpic.foreclosure_write_e2e"
            and _path_triggered_now("foreclosure.individual_child", blob)
        ):
            continue
        add(cid)

    # Simulation read API — quick, only when foreclosure sim path (not full write)
    if any(x in blob for x in ("foreclosuresimulation", "fetchloanforeclosure")):
        if "fetchLoanForeclosureSimulationDetails" in apis:
            add("dpic.foreclosure_sim")

    # BPD day-window (DpiForeclosureBrokenPeriodService) — prefer code-backed sim
    if "dpiforeclosurebrokenperiod" in blob or "foreclosurebrokenperiod" in blob:
        add("dpic.foreclosure_bpd_day_window_sim")

    return out


def resolve_dpi_cases(
    blob: str,
    apis: set[str],
    base: list[str],
) -> list[str]:
    """DPI-specific path scoping (calc/booking/billing slices)."""
    scoped: list[str] = []

    def add(cid: str) -> None:
        if cid not in scoped and cid not in _DPI_FULL_SUITE_CASES:
            scoped.append(cid)

    calc = any(
        k in blob
        for k in (
            "dpiaccrualcalculation",
            "/dpi/calculation/",
            "dpicalculationservice",
            "dpigoliveresolver",
        )
    )
    booking = "dpiaccrualbooking" in blob or "/dpi/booking/" in blob
    billing = "dpibilling" in blob or "/dpi/billing/" in blob
    go_live = any(
        k in blob
        for k in (
            "golive",
            "postgolive",
            "maturity",
            "overduebase",
            "dpiaccrualcalculationitemreader",
        )
    )
    grace = any(k in blob for k in ("grace", "ispastgracegate", "computoverduedate"))
    multi = any(k in blob for k in ("multi_emi", "latestunpaidintdue", "installment_id"))
    posting = any(k in blob for k in ("isaccrualpostingdate", "postingdate"))

    if "dpiAccrualCalculation" in apis:
        calc = True
    if "dpiAccrualBooking" in apis:
        booking = True
    if "dpiBilling" in apis:
        billing = True

    if calc:
        add("batch.dpi_calc")
        if go_live:
            add("dpic.go_live_ud")
        if grace:
            add("dpic.grace_e2e")
        if multi:
            add("dpic.multi_emi_installment_e2e")
        add("dpic.two_emi_full_chain")
    if booking:
        add("batch.dpi_booking")
        if posting or go_live:
            add("dpic.go_live_ud")
        add("dpic.two_emi_full_chain")
    if billing:
        add("batch.dpi_billing")
        add("dpic.post_maturity_billing")
        add("dpic.post_maturity_billing_catchup")

    if calc or booking or billing:
        add(_DPI_SHIP_CLOSE_VERIFY)

    merged: list[str] = []
    ship_close = _DPI_SHIP_CLOSE_VERIFY in scoped
    for cid in scoped + base:
        if cid in _DPI_FULL_SUITE_CASES:
            continue
        if ship_close and cid in _DPI_GUARD_CASES_IN_SHIP_CLOSE:
            continue
        if ship_close and cid == "disbursement.quick":
            continue
        if cid not in merged:
            merged.append(cid)
    return merged if scoped else [c for c in base if c not in _DPI_FULL_SUITE_CASES]


def touches_dpi_blob(blob: str, apis: set[str]) -> bool:
    if apis & {"dpiAccrualCalculation", "dpiAccrualBooking", "dpiBilling"}:
        return True
    hints = (
        "/loan/dpi/",
        "/dpi/",
        "dpiaccrual",
        "dpibilling",
        "dpicalculation",
    )
    return any(h in blob for h in hints)


def _dpi_waiver_smoke_applicable() -> bool:
    """DPI waiver smoke needs dpiAccrualCalculation on the DPI feature branch."""
    try:
        from infer_ship_apis import dpi_money_smoke_applicable

        return dpi_money_smoke_applicable()
    except Exception:
        return False


def resolve_ship_cases(
    paths: list[str] | None,
    apis: list[str],
    tier: str,
    reg: dict,
    *,
    focus_apis: Callable[[list[str], list[str]], list[str]] | None = None,
) -> list[str]:
    """Single entry: minimal ntest cases for changed paths (workspace-wide)."""
    if tier == "workspace":
        return []

    blob = path_blob(paths)
    api_list = list(apis)
    if focus_apis and paths:
        api_list = focus_apis(paths, api_list)
    api_set = set(api_list)

    cases: list[str] = []
    for api in api_list:
        cid = registry_case_for_api_ship(api, reg, path_blob_s=blob)
        if cid == "foreclosure.dpi_waiver_smoke" and not _dpi_waiver_smoke_applicable():
            cid = ""
        if cid and cid not in cases:
            cases.append(cid)

    for cid in expand_path_cases(blob, api_set, reg):
        if cid not in cases:
            cases.append(cid)

    repos: list[str] = []
    for p in paths or []:
        pl = p.replace("\\", "/").lower()
        if "trustt-platform-accounting" in pl:
            repos.append("trustt-platform-accounting")

    try:
        from accounting_flow_domains import (  # noqa: WPS433
            resolve_accounting_domain_cases,
            touches_accounting,
        )

        if tier in ("money", "service") and touches_accounting(blob, api_set, repos):
            cases = resolve_accounting_domain_cases(
                blob, api_set, cases, tier=tier, reg=reg, paths=paths
            )
    except ImportError:
        pass

    if tier == "money" and touches_dpi_blob(blob, api_set):
        cases = resolve_dpi_cases(blob, api_set, cases)

  # Drop manual-suite stragglers
    accounting_guards: frozenset[str] = frozenset()
    try:
        from accounting_flow_domains import all_guard_cases  # noqa: WPS433

        accounting_guards = all_guard_cases()
    except ImportError:
        pass

    out: list[str] = []
    for cid in cases:
        if cid in _DPI_FULL_SUITE_CASES:
            continue
        if cid == "foreclosure.dpi_waiver_smoke" and not _dpi_waiver_smoke_applicable():
            continue
        meta = reg.get(cid) or {}
        if is_ship_auto_case(cid, meta):
            out.append(cid)
        elif cid in PATH_TRIGGERED_CASES and _path_triggered_now(cid, blob):
            out.append(cid)
        elif cid in accounting_guards:
            out.append(cid)
    return out
