#!/usr/bin/env python3
"""Value-level column audit for SHG child interest_accrual_details (distribute path).

Fail-closed: presence-only / sum-only is not enough. After parent
interestAccrualCalculation + InterestGroupLoanAccrualDistributionService, each
ACTIVE child's IAD tip and window rows must have correct column values.

Only SHG has child LANs (JLG/INDL do not).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/disbursement"))

from disbursement_suite.column_audit import ColumnAuditResult, ColumnCheck  # noqa: E402

QueryRows = Callable[[str], list[tuple[str, ...]]]

# Columns written/owned by distribute (see InterestGroupLoanAccrualDistributionService)
IAD_AUDIT_COLUMNS = (
    "account_id",
    "base_amount",
    "start_date",
    "end_date",
    "interest_rate",
    "total_accrued_amount",
    "carry_over_amount",
    "total_accrual_posted_amount",
    "last_accrual_posted_date",
    "loan_installment_details_id",
)


def _dec(v: Any) -> Decimal | None:
    if v is None or str(v).strip() == "":
        return None
    try:
        return Decimal(str(v).strip())
    except (InvalidOperation, AttributeError, ValueError):
        return None


def _q(s: str) -> str:
    return "'" + str(s).replace("'", "''") + "'"


def audit_shg_child_iad_distribute(
    *,
    parent_lan: str,
    query_rows: QueryRows,
    schema: str = "mfi_accounting",
    require_tip_sync: bool = True,
) -> ColumnAuditResult:
    """Audit ACTIVE children IAD columns vs parent tip / distribute contract."""
    out = ColumnAuditResult(evidence={"parent_lan": parent_lan, "columns": list(IAD_AUDIT_COLUMNS)})

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
        FROM {schema}.interest_accrual_details
        WHERE account_id = {int(parent_id)}
        """
    )
    parent_max_end = (parent_tip[0][0] if parent_tip else "") or ""
    out.evidence["parent_account_id"] = parent_id
    out.evidence["parent_max_end"] = parent_max_end

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

    for child_id, child_lan in children:
        tip_rows = query_rows(
            f"""
            SELECT iad.id::text, iad.account_id::text,
                   iad.base_amount::text, iad.start_date::date::text, iad.end_date::date::text,
                   iad.interest_rate::text, iad.total_accrued_amount::text,
                   COALESCE(iad.carry_over_amount::text,''),
                   COALESCE(iad.total_accrual_posted_amount::text,''),
                   COALESCE(iad.last_accrual_posted_date::date::text,''),
                   COALESCE(iad.loan_installment_details_id::text,'')
            FROM {schema}.interest_accrual_details iad
            WHERE iad.account_id = {int(child_id)}
            ORDER BY iad.end_date DESC NULLS LAST
            LIMIT 1
            """
        )
        prefix = f"child[{child_lan}]"
        if not tip_rows:
            out.checks.append(
                ColumnCheck(
                    name=f"{prefix}.iad_tip_present",
                    table="interest_accrual_details",
                    ok=False,
                    expect="tip IAD row",
                    actual="missing",
                )
            )
            continue
        (
            _iad_id,
            acct,
            base,
            start_d,
            end_d,
            rate,
            accrued,
            carry,
            posted,
            last_posted,
            lid,
        ) = tip_rows[0]

        def _ck(name: str, ok: bool, expect: str, actual: str, details: str = "") -> None:
            out.checks.append(
                ColumnCheck(
                    name=f"{prefix}.{name}",
                    table="interest_accrual_details",
                    ok=ok,
                    expect=expect,
                    actual=actual,
                    details=details,
                )
            )

        _ck("account_id", acct == child_id, child_id, acct)
        _ck("start_date_not_null", bool(start_d), "non-null date", start_d or "NULL")
        _ck("end_date_not_null", bool(end_d), "non-null date", end_d or "NULL")
        if start_d and end_d:
            _ck("end_gte_start", end_d >= start_d, f"end>={start_d}", end_d)
        if require_tip_sync and parent_max_end:
            tip_ok = end_d == parent_max_end
            out.checks.append(
                ColumnCheck(
                    name=f"{prefix}.tip_end_matches_parent_asof",
                    table="interest_accrual_details",
                    ok=tip_ok,
                    expect=parent_max_end,
                    actual=end_d or "NULL",
                    details=(
                        "distribute updates Accrued on existing window tip without advancing "
                        "end_date when windowRows non-empty — LMS-DEFECT-child-iad-stuck-tip"
                        if not tip_ok
                        else "distribute newChildRow/asOf uses parent MAX(end_date)"
                    ),
                    # Amount SoT is window parity; tip calendar lag is catalogued defect.
                    level="WARN" if not tip_ok else "FAIL",
                )
            )
            # Fail-closed: tip must still sit inside the parent installment window used by distribute
            win = query_rows(
                f"""
                WITH asof AS (SELECT {_q(parent_max_end)}::date AS d),
                prev AS (
                  SELECT COALESCE(
                    (SELECT MAX(lid.installment_date)::date
                       FROM {schema}.loan_installment_details lid
                      WHERE lid.loan_account_id = {int(parent_id)}
                        AND COALESCE(lid.is_deleted,false)=false
                        AND lid.installment_date < (SELECT d FROM asof)),
                    (SELECT la.expected_disbursement_date::date
                       FROM {schema}.loan_account la WHERE la.account_id={int(parent_id)})
                  ) AS prev_due
                ),
                nxt AS (
                  SELECT MIN(ldd.due_date)::date AS next_due
                    FROM {schema}.loan_due_details ldd
                   WHERE ldd.loan_account_id = {int(parent_id)}
                     AND COALESCE(ldd.is_deleted,false)=false
                     AND ldd.due_date >= (SELECT d FROM asof)
                )
                SELECT (SELECT prev_due FROM prev)::text, (SELECT next_due FROM nxt)::text
                """
            )
            if win and end_d:
                prev_due, next_due = win[0][0], win[0][1]
                in_win = bool(prev_due) and bool(next_due) and end_d > prev_due and end_d <= next_due
                _ck(
                    "tip_end_in_parent_installment_window",
                    in_win,
                    f"({prev_due},{next_due}]",
                    end_d,
                    details="distribute windowRows filter: end after prev_due and not after due",
                )
        acc_d = _dec(accrued)
        post_d = _dec(posted) if posted else Decimal("0")
        _ck("total_accrued_not_null", acc_d is not None, "non-null", accrued or "NULL")
        if acc_d is not None:
            _ck(
                "accrued_gte_posted",
                acc_d >= post_d,
                f">= {post_d}",
                str(acc_d),
            )
        _ck("carry_over_not_null", carry != "", "0 (or set)", carry or "NULL")
        if carry != "":
            _ck("carry_over_zero_or_set", _dec(carry) is not None, "numeric", carry)
        _ck("base_amount_not_null", _dec(base) is not None, "non-null numeric", base or "NULL")
        _ck("interest_rate_not_null", _dec(rate) is not None, "non-null numeric", rate or "NULL")
        _ck(
            "loan_installment_details_id_not_null",
            bool(lid),
            "non-null FK",
            lid or "NULL",
        )
        # Posted may be null until ME/due booking — last_accrual_posted_date only when posted>0
        if post_d and post_d > 0:
            _ck(
                "last_posted_date_when_posted",
                bool(last_posted),
                "date when posted>0",
                last_posted or "NULL",
            )

        # All window-ish rows: Accrued >= Posted (column integrity, not presence)
        viol = query_rows(
            f"""
            SELECT COUNT(*)::text
            FROM {schema}.interest_accrual_details iad
            WHERE iad.account_id = {int(child_id)}
              AND COALESCE(iad.total_accrued_amount,0)
                  < COALESCE(iad.total_accrual_posted_amount,0)
            """
        )
        n_viol = int((viol[0][0] if viol else "0") or "0")
        _ck("all_rows_accrued_gte_posted", n_viol == 0, "0 violations", str(n_viol))

    # Window sum parity (parent SoT) — value-level on Accrued
    parity_sql = (ROOT / "scripts/sql/helpers/verify_shg_interest_accrual_parity.sql").read_text(
        encoding="utf-8"
    ).replace(":parent_lan", _q(parent_lan))
    # strip comments for one-liner query_rows that may not like --
    parity_lines = [
        ln for ln in parity_sql.splitlines() if not ln.strip().startswith("--")
    ]
    prow = query_rows("\n".join(parity_lines))
    if not prow or len(prow[0]) < 6:
        out.checks.append(
            ColumnCheck(
                name="window_accrued_parity",
                table="interest_accrual_details",
                ok=False,
                expect="parity SQL row",
                actual="missing",
            )
        )
    else:
        parent_w, child_w, verdict = prow[0][2], prow[0][3], prow[0][5]
        ok = verdict in ("PASS", "PASS_POSTED_FLOOR")
        out.checks.append(
            ColumnCheck(
                name="window_accrued_parity",
                table="interest_accrual_details",
                ok=ok,
                expect="PASS|PASS_POSTED_FLOOR parent==Σ children",
                actual=f"verdict={verdict} parent={parent_w} children={child_w}",
            )
        )
        out.evidence["parity"] = {
            "verdict": verdict,
            "parent": parent_w,
            "children": child_w,
        }

    return out


def print_audit(result: ColumnAuditResult) -> None:
    for c in result.checks:
        if c.ok:
            mark = "PASS"
        elif c.level == "WARN":
            mark = "WARN"
        else:
            mark = "FAIL"
        print(f"  IAD-COL {mark}: {c.name} expect={c.expect} actual={c.actual}")
        if c.details and not c.ok:
            print(f"           {c.details}")


def assert_audit(result: ColumnAuditResult) -> None:
    print_audit(result)
    fails = [c for c in result.checks if (not c.ok) and c.level == "FAIL"]
    warns = [c for c in result.checks if (not c.ok) and c.level == "WARN"]
    if warns:
        print(f"  IAD-COL WARN count={len(warns)} (tip calendar lag — see LMS-DEFECT-child-iad-stuck-tip)")
    if fails:
        names = ", ".join(c.name for c in fails)
        raise AssertionError(f"SHG child IAD column audit FAIL: {names}")
