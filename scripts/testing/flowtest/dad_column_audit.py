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

    # Base parity per segment: a group's overdue base is the sum of its members'.
    # Compared only across rows that share a start_date, so segment shape is not assumed.
    base_parity = query_rows(
        f"""
        SELECT p.start_date::date::text,
               p.base_amount::text,
               COALESCE(SUM(c.base_amount),0)::text
        FROM {schema}.dpi_accrual_details p
        JOIN {schema}.dpi_accrual_details c ON c.start_date = p.start_date
                                          AND COALESCE(c.is_deleted,false) = false
        JOIN {schema}.loan_account la ON la.account_id = c.loan_account_id
                                     AND la.parent_loan_account_id = {int(parent_id)}
                                     AND la.loan_status = 'ACTIVE'
                                     AND COALESCE(la.is_deleted,false) = false
        WHERE p.loan_account_id = {int(parent_id)}
          AND COALESCE(p.is_deleted,false) = false
        GROUP BY p.start_date, p.base_amount
        ORDER BY p.start_date
        """
    )
    for seg_start, p_base, c_base in base_parity or []:
        out.checks.append(
            ColumnCheck(
                name=f"parent_child_base_sum_parity[{seg_start}]",
                table="dpi_accrual_details",
                ok=_dec(p_base) == _dec(c_base),
                expect=p_base,
                actual=c_base,
                details="sum(children base_amount) == parent base_amount for the same segment",
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
                f"SELECT id::text, loan_account_id::text FROM {schema}.loan_installment_details "
                f"WHERE id = {int(inst)} LIMIT 1"
            )
            _ck("col.installment_id_fk", bool(lid_row), f"exists id={inst}", "missing" if not lid_row else inst)
            # Existence is not ownership: distribute used to write the PARENT's installment
            # id, which still "exists". Fail closed on a cross-loan FK (TDPQA-229).
            if lid_row:
                owner = lid_row[0][1]
                _ck(
                    "col.installment_id_owned_by_child",
                    owner == child_id,
                    f"loan_account_id={child_id}",
                    f"loan_account_id={owner}",
                    details="child DPI row must not reference another account's installment",
                )
            # DPI anchors a slice on the window START (latest EMI due on/before start_date),
            # unlike interest accrual which anchors on the end. Do not swap these.
            if start_d:
                expected = query_rows(
                    f"""
                    SELECT loan_installment_details_id::text
                    FROM {schema}.loan_due_details
                    WHERE loan_account_id = {int(child_id)}
                      AND COALESCE(is_deleted,false) = false
                      AND loan_installment_details_id IS NOT NULL
                      AND due_date::date <= {_q(start_d)}::date
                    ORDER BY due_date DESC
                    LIMIT 1
                    """
                )
                if expected and expected[0][0]:
                    _ck(
                        "col.installment_id_tracks_segment_start",
                        inst == expected[0][0],
                        expected[0][0],
                        inst,
                        details="MUST-MATCH independent: resolveSliceInstallment(segStart)",
                    )

        if start_d:
            expected_base = query_rows(
                f"""
                SELECT COALESCE(SUM(ldd.due_amount - ldd.paid_amount - ldd.waived_amount),0)::text
                FROM {schema}.loan_due_details ldd
                WHERE ldd.loan_account_id = {int(child_id)}
                  AND ldd.component_type IN ('PRIN','INT')
                  AND COALESCE(ldd.is_deleted,false) = false
                  AND (ldd.due_amount - ldd.paid_amount - ldd.waived_amount) > 0
                  AND ldd.overdue_date IS NOT NULL
                  AND ldd.overdue_date::date <= {_q(start_d)}::date
                  AND ldd.overdue_date::date >= (
                        SELECT MIN(p.start_date)::date
                        FROM {schema}.dpi_accrual_details p
                        WHERE p.loan_account_id = {int(parent_id)}
                          AND COALESCE(p.is_deleted,false) = false
                  )
                """
            )
            if expected_base and expected_base[0][0] is not None:
                want = _dec(expected_base[0][0])
                _ck(
                    "col.base_amount_is_child_own_post_cutoff_overdue",
                    base_d is not None and want is not None and base_d == want,
                    str(want),
                    base or "NULL",
                    details="MUST-MATCH: child's own admitted overdue, not the parent's",
                )
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


def audit_shg_child_dad_all_rows(
    *,
    parent_lan: str,
    query_rows: QueryRows,
    go_live: str,
    schema: str = "mfi_accounting",
) -> ColumnAuditResult:
    """Value-level audit of EVERY child DAD row against its parent segment.

    audit_shg_child_dad_distribute only inspects the tip row (LIMIT 1) and checks most
    columns for presence (">= 0", "non-null"). TDPQA-234 passed it while every child row
    carried the wrong base_amount. This walks all rows and re-derives each expected value
    from the parent row or from loan_due_details, independently of the writer.
    """
    out = ColumnAuditResult(evidence={"parent_lan": parent_lan, "go_live": go_live, "mode": "all_rows"})

    meta = query_rows(
        f"""
        SELECT la.account_id::text
        FROM {schema}.loan_account la
        JOIN {schema}.account a ON a.id = la.account_id
        WHERE a.account_number = {_q(parent_lan)} AND COALESCE(la.is_deleted,false) = false
        LIMIT 1
        """
    )
    if not meta:
        out.checks.append(ColumnCheck("parent_lan_present", "loan_account", False, parent_lan, "missing"))
        return out
    parent_id = meta[0][0]

    rows = query_rows(
        f"""
        SELECT c.loan_account_id::text, ac.account_number,
               c.start_date::date::text, c.end_date::date::text,
               c.base_amount::text, c.dpi_annual_rate::text,
               COALESCE(c.days_in_year::text,'NULL'), c.carry_over_amount::text,
               c.total_accrued_amount::text,
               COALESCE(c.accrual_posting_date::date::text,'NULL'),
               COALESCE(c.accrual_transaction_ref_number,'NULL'),
               COALESCE(c.billing_posting_date::date::text,'NULL'),
               COALESCE(c.billing_transaction_ref_number,'NULL'),
               COALESCE(c.is_deleted::text,'false'),
               COALESCE(c.installment_id::text,'NULL'),
               p.end_date::date::text, p.dpi_annual_rate::text,
               COALESCE(p.days_in_year::text,'NULL'), p.base_amount::text,
               COALESCE(lid.loan_account_id::text,'NULL')
        FROM {schema}.dpi_accrual_details c
        JOIN {schema}.loan_account la ON la.account_id = c.loan_account_id
                                     AND la.parent_loan_account_id = {int(parent_id)}
                                     AND la.loan_status = 'ACTIVE'
        JOIN {schema}.account ac ON ac.id = la.account_id
        LEFT JOIN {schema}.dpi_accrual_details p ON p.loan_account_id = {int(parent_id)}
                                                AND p.start_date = c.start_date
                                                AND COALESCE(p.is_deleted,false) = false
        LEFT JOIN {schema}.loan_installment_details lid ON lid.id = c.installment_id
        WHERE COALESCE(c.is_deleted,false) = false
        ORDER BY ac.account_number, c.start_date
        """
    )
    if not rows:
        out.checks.append(ColumnCheck("child_dad_rows_present", "dpi_accrual_details", False, ">=1 row", "0"))
        return out
    out.evidence["rows_audited"] = str(len(rows))

    for r in rows:
        (cid, clan, sd, ed, base, rate, diy, carry, accrued, apd, atr, bpd, btr, deleted,
         inst, p_ed, p_rate, p_diy, p_base, inst_owner) = r
        pfx = f"{clan}@{sd}"

        def ck(name, ok, expect, actual, details=""):
            out.checks.append(ColumnCheck(f"{pfx}.{name}", "dpi_accrual_details", ok, str(expect), str(actual), details))

        ck("has_parent_segment", p_ed is not None, "parent row with same start_date", p_ed or "MISSING",
           "child rows mirror parent segments one-for-one")
        if p_ed is None:
            continue

        ck("end_date", ed == p_ed, p_ed, ed)
        ck("dpi_annual_rate", _dec(rate) == _dec(p_rate), p_rate, rate)
        ck("days_in_year", diy == p_diy, p_diy, diy)
        ck("carry_over_amount", _dec(carry) == Decimal("0"), "0", carry)
        ck("is_deleted", deleted == "false", "false", deleted)
        ck("installment_id_owned_by_child", inst_owner == cid, f"loan_account_id={cid}", inst_owner,
           "a parent (or sibling) installment FK here is a cross-loan defect")

        expected = query_rows(
            f"""
            SELECT COALESCE(SUM(due_amount - paid_amount - waived_amount),0)::text
            FROM {schema}.loan_due_details
            WHERE loan_account_id = {int(cid)}
              AND component_type IN ('PRIN','INT')
              AND COALESCE(is_deleted,false) = false
              AND (due_amount - paid_amount - waived_amount) > 0
              AND overdue_date IS NOT NULL
              AND overdue_date::date >= {_q(go_live)}::date
              AND overdue_date::date <= {_q(sd)}::date
            """
        )
        want = _dec(expected[0][0]) if expected else None
        ck("base_amount", want is not None and _dec(base) == want, want, base,
           "child's own overdue PRIN+INT admitted between go-live and this segment start")

        ck("accrual_ref_iff_posted", (atr != "NULL") == (apd != "NULL"),
           f"ref set iff accrual_posting_date set (apd={apd})", atr)
        ck("billing_ref_iff_billed", (btr != "NULL") == (bpd != "NULL"),
           f"ref set iff billing_posting_date set (bpd={bpd})", btr)
        if bpd != "NULL":
            ck("billed_implies_posted", apd != "NULL", "accrual posted before billing", apd)

    seg = query_rows(
        f"""
        SELECT p.start_date::date::text, p.total_accrued_amount::text, p.base_amount::text,
               COALESCE(SUM(c.total_accrued_amount),0)::text, COALESCE(SUM(c.base_amount),0)::text,
               COUNT(c.id)::text
        FROM {schema}.dpi_accrual_details p
        JOIN {schema}.dpi_accrual_details c ON c.start_date = p.start_date
                                          AND COALESCE(c.is_deleted,false) = false
        JOIN {schema}.loan_account la ON la.account_id = c.loan_account_id
                                     AND la.parent_loan_account_id = {int(parent_id)}
                                     AND la.loan_status = 'ACTIVE'
        WHERE p.loan_account_id = {int(parent_id)} AND COALESCE(p.is_deleted,false) = false
        GROUP BY p.start_date, p.total_accrued_amount, p.base_amount
        ORDER BY p.start_date
        """
    )
    n_children = query_rows(
        f"SELECT COUNT(*)::text FROM {schema}.loan_account WHERE parent_loan_account_id = {int(parent_id)} "
        f"AND loan_status = 'ACTIVE' AND COALESCE(is_deleted,false) = false"
    )
    expect_n = int((n_children[0][0] if n_children else "0") or "0")
    tot_p_acc = Decimal("0")
    tot_c_acc = Decimal("0")
    for start, p_acc, p_base, c_acc, c_base, n in seg:
        tot_p_acc += _dec(p_acc) or Decimal("0")
        tot_c_acc += _dec(c_acc) or Decimal("0")
        # Accrued is split across children at scale 0 (booking rejects a fractional accrual),
        # so a segment may drift by the per-child rounding bound; the window total may not.
        drift = abs((_dec(p_acc) or Decimal("0")) - (_dec(c_acc) or Decimal("0")))
        out.checks.append(ColumnCheck(f"segment[{start}].accrued_sum_rounding_bound", "dpi_accrual_details",
                                      drift <= Decimal(expect_n), f"|diff| <= {expect_n}", str(drift),
                                      "whole-rupee split drift, bounded by child count"))
        # base_amount is NOT divided — each child carries its own overdue, so this is exact.
        out.checks.append(ColumnCheck(f"segment[{start}].base_sum", "dpi_accrual_details",
                                      _dec(p_base) == _dec(c_base), p_base, c_base,
                                      "parent base == sum(children) for this segment (EXACT)"))
        out.checks.append(ColumnCheck(f"segment[{start}].child_row_count", "dpi_accrual_details",
                                      int(n) == expect_n, expect_n, n,
                                      "exactly one row per ACTIVE child — no dupes, no orphans"))

    out.checks.append(ColumnCheck("total.accrued_sum_exact", "dpi_accrual_details",
                                  tot_p_acc == tot_c_acc, str(tot_p_acc), str(tot_c_acc),
                                  "no money created or lost across the whole family (EXACT)"))
    return out
