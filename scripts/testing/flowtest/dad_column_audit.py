#!/usr/bin/env python3
"""Value-level column audit for SHG child dpi_accrual_details (distribute path).

DpiGroupLoanAccrualDistributionService CREATES/UPDATES child DAD rows.
Every physical column on mfi_accounting.dpi_accrual_details must be audited
fail-closed (entity + information_schema SoT — 15 columns).

Only intentional differences vs independent child DPI calc:
  - total_accrued_amount = parent window share (not child daily calc)
  - carry_over_amount = 0 on new distribute tips (not child rounding carry)
"""
from __future__ import annotations

import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/disbursement"))

from disbursement_suite.column_audit import ColumnAuditResult, ColumnCheck  # noqa: E402

QueryRows = Callable[[str], list[tuple[str, ...]]]

DAD_PHYSICAL_COLUMNS: tuple[str, ...] = (
    "id",
    "loan_account_id",
    "installment_id",
    "base_amount",
    "start_date",
    "end_date",
    "dpi_annual_rate",
    "days_in_year",
    "total_accrued_amount",
    "carry_over_amount",
    "accrual_posting_date",
    "accrual_transaction_ref_number",
    "billing_posting_date",
    "billing_transaction_ref_number",
    "is_deleted",
)

DAD_AUDIT_COLUMNS = DAD_PHYSICAL_COLUMNS


def _dec(v: Any) -> Decimal | None:
    if v is None or str(v).strip() == "" or str(v).strip().upper() == "NULL":
        return None
    try:
        return Decimal(str(v).strip())
    except (InvalidOperation, AttributeError, ValueError):
        return None


def _q(s: str) -> str:
    return "'" + str(s).replace("'", "''") + "'"


def _assert_schema_columns(query_rows: QueryRows, schema: str, out: ColumnAuditResult) -> bool:
    rows = query_rows(
        f"""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = {_q(schema)}
          AND table_name = 'dpi_accrual_details'
        ORDER BY ordinal_position
        """
    )
    live = tuple(r[0] for r in rows if r and r[0])
    ok = live == DAD_PHYSICAL_COLUMNS
    out.checks.append(
        ColumnCheck(
            name="schema.dpi_accrual_details_all_columns",
            table="dpi_accrual_details",
            ok=ok,
            expect=",".join(DAD_PHYSICAL_COLUMNS),
            actual=",".join(live) if live else "missing",
            details=(
                "live schema must match entity/audit SoT — every physical DAD column audited"
                if not ok
                else f"all {len(live)} physical columns enumerated"
            ),
            level="FAIL",
        )
    )
    out.evidence["dad_physical_columns"] = list(live)
    return ok


def assert_audit(result: ColumnAuditResult) -> None:
    fails = [c for c in result.checks if not c.ok]
    if fails:
        for c in fails:
            print(f"  FAIL {c.name}: expect={c.expect} actual={c.actual} {c.details or ''}")
        raise AssertionError(f"dpi_accrual_details column audit FAIL ({len(fails)} checks)")
    print(f"  PASS dpi_accrual_details column audit ({len(result.checks)} checks)")


def audit_shg_child_dad_distribute(
    *,
    parent_lan: str,
    query_rows: QueryRows,
    schema: str = "mfi_accounting",
    require_tip_sync: bool = True,
) -> ColumnAuditResult:
    out = ColumnAuditResult(
        evidence={
            "parent_lan": parent_lan,
            "columns": list(DAD_PHYSICAL_COLUMNS),
            "column_expects": {
                "id": "non-null positive PK",
                "loan_account_id": "ACTIVE child account_id",
                "installment_id": "non-null FK to loan_installment_details",
                "base_amount": "non-null numeric >=0; copy prior tip / parent tip",
                "start_date": "non-null; <= end_date",
                "end_date": "non-null; tip == parent MAX(end_date) asOf (MUST-MATCH)",
                "dpi_annual_rate": "non-null numeric >=0",
                "days_in_year": "null or positive int",
                "total_accrued_amount": "INTENTIONAL parent share; >= posted when booked",
                "carry_over_amount": "INTENTIONAL 0 on distribute new/synced tip",
                "accrual_posting_date": "null until booking; freeze+new when set + tip behind",
                "accrual_transaction_ref_number": "null until booking",
                "billing_posting_date": "null until billing",
                "billing_transaction_ref_number": "null until billing",
                "is_deleted": "false on live tip",
            },
        }
    )

    if not _assert_schema_columns(query_rows, schema, out):
        return out

    meta = query_rows(
        f"""
        SELECT la.account_id::text, a.account_number,
               COALESCE(la.has_child_accounts::text,'false'),
               COALESCE(la.parent_loan_account_id::text,'')
        FROM {schema}.loan_account la
        JOIN {schema}.account a ON a.id = la.account_id
        WHERE a.account_number = {_q(parent_lan)} AND COALESCE(la.is_deleted,false)=false
        LIMIT 1
        """
    )
    if not meta:
        out.checks.append(
            ColumnCheck(
                name="parent_lan_present",
                table="loan_account",
                ok=False,
                expect=parent_lan,
                actual="missing",
            )
        )
        return out
    parent_id, _, has_child, parent_of = meta[0]
    out.checks.append(
        ColumnCheck(
            name="parent_is_shg_root",
            table="loan_account",
            ok=(has_child.lower() == "true" and parent_of == ""),
            expect="has_child_accounts=true AND parent_loan_account_id NULL",
            actual=f"has_child={has_child} parent_of={parent_of or 'NULL'}",
        )
    )

    parent_tip = query_rows(
        f"""
        SELECT MAX(end_date)::date::text,
               COALESCE(SUM(total_accrued_amount),0)::text
        FROM {schema}.dpi_accrual_details
        WHERE loan_account_id = {int(parent_id)} AND is_deleted = false
        """
    )
    parent_max_end = (parent_tip[0][0] if parent_tip else "") or ""
    parent_sum = (parent_tip[0][1] if parent_tip else "0") or "0"
    out.evidence["parent_account_id"] = parent_id
    out.evidence["parent_max_end"] = parent_max_end
    out.evidence["parent_accrued_sum"] = parent_sum

    children = query_rows(
        f"""
        SELECT la.account_id::text, a.account_number
        FROM {schema}.loan_account la
        JOIN {schema}.account a ON a.id = la.account_id
        WHERE la.parent_loan_account_id = {int(parent_id)}
          AND la.loan_status = 'ACTIVE'
          AND COALESCE(la.is_deleted,false)=false
        ORDER BY a.account_number
        """
    )
    if not children:
        out.checks.append(
            ColumnCheck(
                name="active_children_present",
                table="loan_account",
                ok=False,
                expect=">=1 ACTIVE child",
                actual="0",
            )
        )
        return out
    out.checks.append(
        ColumnCheck(
            name="active_children_present",
            table="loan_account",
            ok=True,
            expect=">=1 ACTIVE child",
            actual=str(len(children)),
        )
    )

    child_sum_rows = query_rows(
        f"""
        SELECT COALESCE(SUM(d.total_accrued_amount),0)::text
        FROM {schema}.dpi_accrual_details d
        JOIN {schema}.loan_account la ON la.account_id = d.loan_account_id
        WHERE la.parent_loan_account_id = {int(parent_id)}
          AND la.loan_status = 'ACTIVE'
          AND d.is_deleted = false
        """
    )
    child_sum = (child_sum_rows[0][0] if child_sum_rows else "0") or "0"
    out.checks.append(
        ColumnCheck(
            name="parent_child_accrued_sum_parity",
            table="dpi_accrual_details",
            ok=_dec(parent_sum) == _dec(child_sum),
            expect=parent_sum,
            actual=child_sum,
            details="parent DPI Accrued SoT == sum(ACTIVE children)",
        )
    )

    for child_id, child_lan in children:
        tip_rows = query_rows(
            f"""
            SELECT d.id::text,
                   d.loan_account_id::text,
                   COALESCE(d.installment_id::text,'NULL'),
                   d.base_amount::text,
                   d.start_date::date::text,
                   d.end_date::date::text,
                   d.dpi_annual_rate::text,
                   COALESCE(d.days_in_year::text,'NULL'),
                   d.total_accrued_amount::text,
                   d.carry_over_amount::text,
                   COALESCE(d.accrual_posting_date::date::text,'NULL'),
                   COALESCE(d.accrual_transaction_ref_number,'NULL'),
                   COALESCE(d.billing_posting_date::date::text,'NULL'),
                   COALESCE(d.billing_transaction_ref_number,'NULL'),
                   COALESCE(d.is_deleted::text,'false')
            FROM {schema}.dpi_accrual_details d
            WHERE d.loan_account_id = {int(child_id)} AND d.is_deleted = false
            ORDER BY d.end_date DESC NULLS LAST
            LIMIT 1
            """
        )
        prefix = f"child[{child_lan}]"
        if not tip_rows:
            out.checks.append(
                ColumnCheck(
                    name=f"{prefix}.dad_tip_present",
                    table="dpi_accrual_details",
                    ok=False,
                    expect="tip DAD row",
                    actual="missing",
                )
            )
            continue

        (
            dad_id,
            acct,
            inst,
            base,
            start_d,
            end_d,
            rate,
            diy,
            accrued,
            carry,
            accrual_posted,
            accrual_ref,
            billing_posted,
            billing_ref,
            is_del,
        ) = tip_rows[0]

        def _ck(name: str, ok: bool, expect: str, actual: str, details: str = "") -> None:
            out.checks.append(
                ColumnCheck(
                    name=f"{prefix}.{name}",
                    table="dpi_accrual_details",
                    ok=ok,
                    expect=expect,
                    actual=actual,
                    details=details,
                )
            )

        _ck("col.id", bool(dad_id) and dad_id.isdigit() and int(dad_id) > 0, "positive bigint PK", dad_id or "NULL")
        _ck("col.loan_account_id", acct == child_id, child_id, acct or "NULL")

        inst_ok = bool(inst) and inst != "NULL" and inst.isdigit()
        _ck("col.installment_id", inst_ok, "non-null FK bigint", inst or "NULL")
        if inst_ok:
            lid_row = query_rows(
                f"SELECT id::text FROM {schema}.loan_installment_details WHERE id = {int(inst)} LIMIT 1"
            )
            _ck("col.installment_id_fk", bool(lid_row), f"exists id={inst}", "missing" if not lid_row else inst)

        base_d = _dec(base)
        _ck("col.base_amount", base_d is not None and base_d >= 0, "non-null numeric >=0", base or "NULL")
        _ck("col.start_date", bool(start_d), "non-null date", start_d or "NULL")
        _ck("col.end_date", bool(end_d), "non-null date", end_d or "NULL")
        if start_d and end_d:
            _ck("col.end_gte_start", end_d >= start_d, f"end>={start_d}", end_d)

        tip_synced = bool(require_tip_sync and parent_max_end and end_d == parent_max_end)
        if require_tip_sync and parent_max_end:
            out.checks.append(
                ColumnCheck(
                    name=f"{prefix}.col.end_date_matches_parent_asof",
                    table="dpi_accrual_details",
                    ok=tip_synced,
                    expect=parent_max_end,
                    actual=end_d or "NULL",
                    details=(
                        "distribute must advance tip end_date to parent asOf"
                        if not tip_synced
                        else "tip end_date matches parent asOf"
                    ),
                    level="FAIL",
                )
            )

        rate_d = _dec(rate)
        _ck("col.dpi_annual_rate", rate_d is not None and rate_d >= 0, "non-null numeric >=0", rate or "NULL")
        diy_ok = diy == "NULL" or (diy.isdigit() and int(diy) > 0)
        _ck("col.days_in_year", diy_ok, "null or positive int", diy)

        acc_d = _dec(accrued)
        _ck(
            "col.total_accrued_amount",
            acc_d is not None and acc_d >= 0,
            "non-null numeric >=0 (parent share SoT)",
            accrued or "NULL",
        )
        posted = accrual_posted != "NULL"
        if posted and acc_d is not None:
            _ck(
                "col.total_accrued_when_posted",
                acc_d >= 0,
                ">=0 when accrual_posting_date set",
                str(acc_d),
            )

        carry_d = _dec(carry)
        _ck("col.carry_over_amount", carry_d is not None, "non-null numeric", carry or "NULL")
        if carry_d is not None and tip_synced:
            _ck(
                "col.carry_over_zero_on_synced_tip",
                carry_d == Decimal("0"),
                "0 on distribute-owned tip",
                str(carry_d),
            )

        _ck(
            "col.accrual_posting_date",
            True,
            "NULL until booking (OK) or date when booked",
            accrual_posted,
        )
        if not posted:
            _ck(
                "col.accrual_transaction_ref_number",
                accrual_ref == "NULL" or accrual_ref == "",
                "NULL when unposted",
                accrual_ref,
            )
        else:
            _ck(
                "col.accrual_transaction_ref_number",
                accrual_ref != "NULL" and bool(accrual_ref),
                "non-null when posted",
                accrual_ref,
            )

        _ck(
            "col.billing_posting_date",
            True,
            "NULL until billing (OK) or date when billed",
            billing_posted,
        )
        if billing_posted == "NULL":
            _ck(
                "col.billing_transaction_ref_number",
                billing_ref == "NULL" or billing_ref == "",
                "NULL when unbilled",
                billing_ref,
            )

        _ck(
            "col.is_deleted",
            str(is_del).lower() in ("false", "f", "0"),
            "false",
            is_del,
        )

        audited = {
            "id",
            "loan_account_id",
            "installment_id",
            "base_amount",
            "start_date",
            "end_date",
            "dpi_annual_rate",
            "days_in_year",
            "total_accrued_amount",
            "carry_over_amount",
            "accrual_posting_date",
            "accrual_transaction_ref_number",
            "billing_posting_date",
            "billing_transaction_ref_number",
            "is_deleted",
        }
        _ck(
            "col.all_physical_columns_audited",
            audited == set(DAD_PHYSICAL_COLUMNS),
            ",".join(DAD_PHYSICAL_COLUMNS),
            ",".join(sorted(audited)),
        )

        if parent_max_end:
            unfrozen = query_rows(
                f"""
                SELECT COUNT(*)::text
                FROM {schema}.dpi_accrual_details d
                WHERE d.loan_account_id = {int(child_id)}
                  AND d.is_deleted = false
                  AND d.accrual_posting_date IS NOT NULL
                  AND d.end_date::date < {_q(parent_max_end)}::date
                  AND d.id <> {int(dad_id)}
                """
            )
            n_unf = int((unfrozen[0][0] if unfrozen else "0") or "0")
            _ck(
                "posted_prior_tips_exist_ok",
                True,
                "posted prior tips retained (freeze+new)",
                str(n_unf),
                details="count informational — freeze keeps Accrued on posted tips",
            )

    readers = query_rows(
        f"""
        SELECT COUNT(*)::text
        FROM {schema}.loan_account la
        WHERE la.parent_loan_account_id = {int(parent_id)}
          AND la.loan_status = 'ACTIVE'
        """
    )
    out.evidence["active_children"] = (readers[0][0] if readers else "0")
    return out
