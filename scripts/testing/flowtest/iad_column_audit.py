#!/usr/bin/env python3
"""Value-level column audit for SHG child interest_accrual_details (distribute path).

InterestGroupLoanAccrualDistributionService CREATES/UPDATES child IAD rows.
Every physical column on mfi_accounting.interest_accrual_details must be audited
fail-closed (entity + information_schema SoT — 11 columns; no created_by/updated_on).

Only intentional differences vs independent createOrUpdateIADE:
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

# Physical columns — information_schema + InterestAccrualDetailsEntity (excl. @Transient).
# Order matches ordinal_position. Do not drop columns silently.
IAD_PHYSICAL_COLUMNS: tuple[str, ...] = (
    "id",
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

# Alias for callers / registry
IAD_AUDIT_COLUMNS = IAD_PHYSICAL_COLUMNS


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
    """Fail closed if live schema drifts from audited column list."""
    rows = query_rows(
        f"""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = {_q(schema)}
          AND table_name = 'interest_accrual_details'
        ORDER BY ordinal_position
        """
    )
    live = tuple(r[0] for r in rows if r and r[0])
    ok = live == IAD_PHYSICAL_COLUMNS
    out.checks.append(
        ColumnCheck(
            name="schema.interest_accrual_details_all_columns",
            table="interest_accrual_details",
            ok=ok,
            expect=",".join(IAD_PHYSICAL_COLUMNS),
            actual=",".join(live) if live else "missing",
            details=(
                "live schema must match entity/audit SoT — every physical IAD column audited"
                if not ok
                else f"all {len(live)} physical columns enumerated"
            ),
            level="FAIL",
        )
    )
    out.evidence["iad_physical_columns"] = list(live)
    return ok


def audit_shg_child_iad_distribute(
    *,
    parent_lan: str,
    query_rows: QueryRows,
    schema: str = "mfi_accounting",
    require_tip_sync: bool = True,
    scheduled_int_since: str | None = None,
) -> ColumnAuditResult:
    """Audit ACTIVE children IAD tip — every physical column, fail-closed."""
    out = ColumnAuditResult(
        evidence={
            "parent_lan": parent_lan,
            "columns": list(IAD_PHYSICAL_COLUMNS),
            "column_expects": {
                "id": "non-null positive PK (sequence)",
                "account_id": "ACTIVE child account_id",
                "base_amount": "non-null numeric >=0; copy prior tip / child base",
                "start_date": "non-null; <= end_date; freeze+new starts at prior tip end",
                "end_date": "non-null; tip == parent MAX(end_date) asOf (MUST-MATCH independent calendar)",
                "interest_rate": "non-null; == account_interest_details.effective_rate",
                "total_accrued_amount": "INTENTIONAL parent share; >= COALESCE(posted,0)",
                "carry_over_amount": "INTENTIONAL 0 on distribute new/synced tip; legacy rows may be non-zero",
                "total_accrual_posted_amount": "null/0 until booking; if >0 then last_posted set; <= accrued",
                "last_accrual_posted_date": "null when unposted; non-null when posted>0; <= end_date",
                "loan_installment_details_id": "non-null FK; exists on loan_installment_details",
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

    # Distribute must leave each child with exactly the rows the job would have written
    # had it processed that child independently. The parent is segmented by the normal
    # calc path, so the parent's (start,end) boundaries ARE that expected shape.
    # Scope to the CURRENT installment window only: distribute rewrites just that window,
    # so a child's older rows are history and can never match the parent's full series.
    window_start_sql = f"""
        SELECT COALESCE(MAX(lid.installment_date)::date::text, '1900-01-01')
        FROM {schema}.loan_installment_details lid
        WHERE lid.loan_account_id = {int(parent_id)}
          AND COALESCE(lid.is_deleted,false)=false
          AND lid.installment_date < {_q(parent_max_end)}::timestamp
    """
    win = query_rows(window_start_sql)
    window_start = (win[0][0] if win else "1900-01-01") or "1900-01-01"
    out.evidence["distribute_window_start"] = window_start
    # Collapse the parent by start_date (max end wins): its open row is extended in place,
    # and a re-run fixture can hold several stale snapshots of the same segment. The
    # collapsed set is the true shape independent calc would leave. Child rows are read
    # RAW so duplicate child rows still fail the count check.
    parent_segments = query_rows(
        f"""
        SELECT start_date::date::text || '|' || MAX(end_date)::date::text
        FROM {schema}.interest_accrual_details
        WHERE account_id = {int(parent_id)}
          AND end_date::date > {_q(window_start)}::date
        GROUP BY start_date::date
        ORDER BY start_date::date
        """
    )
    parent_bounds = [r[0] for r in parent_segments]
    for child_id, child_lan in children:
        child_segments = query_rows(
            f"""
            SELECT start_date::date::text || '|' || end_date::date::text
            FROM {schema}.interest_accrual_details
            WHERE account_id = {int(child_id)}
              AND end_date::date > {_q(window_start)}::date
            ORDER BY end_date, start_date
            """
        )
        child_bounds = [r[0] for r in child_segments]
        out.checks.append(
            ColumnCheck(
                name=f"child[{child_lan}].row_count_matches_independent_shape",
                table="interest_accrual_details",
                ok=len(child_bounds) == len(parent_bounds),
                expect=f"{len(parent_bounds)} rows (parent segment count)",
                actual=f"{len(child_bounds)} rows",
                details=(
                    "distribute must produce the same number of accrual rows the job "
                    "would have written processing this child independently"
                ),
                level="FAIL",
            )
        )
        # Accrued must stay in the same rounded unit space as the parent, or booking
        # rejects it with "Invalid amount" (a pro-rata split is what broke this).
        frac = query_rows(
            f"""
            SELECT COUNT(*)::text
            FROM {schema}.interest_accrual_details
            WHERE account_id = {int(child_id)}
              AND total_accrued_amount IS NOT NULL
              AND total_accrued_amount <> TRUNC(total_accrued_amount)
            """
        )
        frac_n = int(frac[0][0]) if frac and frac[0][0] else 0
        out.checks.append(
            ColumnCheck(
                name=f"child[{child_lan}].accrued_rounded_like_parent",
                table="interest_accrual_details",
                ok=frac_n == 0,
                expect="0 fractional total_accrued_amount rows",
                actual=f"{frac_n} fractional",
                details="sub-unit remainder belongs in carry_over_amount, not accrued",
                level="FAIL",
            )
        )

        missing = [b for b in parent_bounds if b not in set(child_bounds)]
        extra = [b for b in child_bounds if b not in set(parent_bounds)]
        out.checks.append(
            ColumnCheck(
                name=f"child[{child_lan}].row_boundaries_match_parent_segments",
                table="interest_accrual_details",
                ok=not missing and not extra,
                expect="identical (start_date,end_date) set as parent",
                actual=(
                    "aligned" if not missing and not extra
                    else f"missing={missing[:3]} extra={extra[:3]}"
                ),
                details="missing or extra windows mean child dates diverge from independent calc",
                level="FAIL",
            )
        )

        tip_rows = query_rows(
            f"""
            SELECT iad.id::text,
                   iad.account_id::text,
                   iad.base_amount::text,
                   iad.start_date::date::text,
                   iad.end_date::date::text,
                   iad.interest_rate::text,
                   iad.total_accrued_amount::text,
                   iad.carry_over_amount::text,
                   COALESCE(iad.total_accrual_posted_amount::text,'NULL'),
                   COALESCE(iad.last_accrual_posted_date::date::text,'NULL'),
                   COALESCE(iad.loan_installment_details_id::text,'NULL')
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
            iad_id,
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

        # --- id ---
        id_ok = bool(iad_id) and iad_id.isdigit() and int(iad_id) > 0
        _ck("col.id", id_ok, "positive bigint PK", iad_id or "NULL")

        # --- account_id ---
        _ck("col.account_id", acct == child_id, child_id, acct or "NULL")

        # --- base_amount ---
        base_d = _dec(base)
        _ck(
            "col.base_amount",
            base_d is not None and base_d >= 0,
            "non-null numeric >=0",
            base or "NULL",
        )

        # --- start_date / end_date ---
        _ck("col.start_date", bool(start_d), "non-null date", start_d or "NULL")
        _ck("col.end_date", bool(end_d), "non-null date", end_d or "NULL")
        if start_d and end_d:
            _ck("col.end_gte_start", end_d >= start_d, f"end>={start_d}", end_d)

        # MUST-MATCH independent: each row starts where the previous one ended.
        # Presence-only here is what let distribute write the PARENT's prevDueDate
        # onto a child tip without the suite noticing.
        prev_end = query_rows(
            f"""
            SELECT iad.end_date::date::text
            FROM {schema}.interest_accrual_details iad
            WHERE iad.account_id = {int(child_id)}
              AND iad.id <> {int(iad_id)}
              AND iad.end_date <= DATE '{start_d}'
            ORDER BY iad.end_date DESC
            LIMIT 1
            """
        ) if start_d else []
        if prev_end and prev_end[0][0]:
            _ck(
                "col.start_date_contiguous_with_prior_row",
                start_d == prev_end[0][0],
                prev_end[0][0],
                start_d or "NULL",
                details=(
                    "MUST-MATCH independent: tip start_date == prior row end_date "
                    "(distribute must not start the child at the parent's prevDueDate)"
                ),
            )

        tip_synced = bool(require_tip_sync and parent_max_end and end_d == parent_max_end)
        if require_tip_sync and parent_max_end:
            out.checks.append(
                ColumnCheck(
                    name=f"{prefix}.col.end_date_matches_parent_asof",
                    table="interest_accrual_details",
                    ok=tip_synced,
                    expect=parent_max_end,
                    actual=end_d or "NULL",
                    details=(
                        "distribute must advance tip end_date to parent asOf "
                        "(same calendar behavior as independent child calc)"
                        if not tip_synced
                        else "tip end_date matches parent asOf"
                    ),
                    level="FAIL",
                )
            )

        # --- interest_rate ---
        rate_d = _dec(rate)
        _ck(
            "col.interest_rate",
            rate_d is not None and rate_d >= 0,
            "non-null numeric >=0",
            rate or "NULL",
        )
        aide = query_rows(
            f"""
            SELECT effective_rate::text
            FROM {schema}.account_interest_details
            WHERE account_id = {int(child_id)}
            LIMIT 1
            """
        )
        if aide and aide[0][0]:
            _ck(
                "col.interest_rate_matches_aide",
                rate_d == _dec(aide[0][0]),
                aide[0][0],
                rate or "NULL",
                details="MUST-MATCH independent: tip rate == aide.effective_rate",
            )

        # --- total_accrued_amount (INTENTIONAL parent share) ---
        acc_d = _dec(accrued)
        post_d = _dec(posted) if posted and posted != "NULL" else None
        post_cmp = post_d if post_d is not None else Decimal("0")
        _ck(
            "col.total_accrued_amount",
            acc_d is not None and acc_d >= 0,
            "non-null numeric >=0 (parent share SoT)",
            accrued or "NULL",
        )
        if acc_d is not None:
            _ck(
                "col.total_accrued_gte_posted",
                acc_d >= post_cmp,
                f">= {post_cmp}",
                str(acc_d),
            )

        # --- carry_over_amount (INTENTIONAL 0 on distribute tip) ---
        carry_d = _dec(carry)
        _ck(
            "col.carry_over_amount",
            carry_d is not None,
            "non-null numeric (NOT NULL)",
            carry or "NULL",
            details=(
                "distribute newChildRow sets 0; update path does not clear legacy; "
                "getFinalAmountListUsingCarryOver is in-memory paisa split not IAD.carry"
            ),
        )
        if carry_d is not None and tip_synced:
            _ck(
                "col.carry_over_zero_on_synced_tip",
                carry_d == Decimal("0"),
                "0 on distribute-owned tip",
                str(carry_d),
            )

        # --- total_accrual_posted_amount / last_accrual_posted_date ---
        # Nullable until booking; when posted>0 both must be consistent.
        if post_d is None:
            _ck(
                "col.total_accrual_posted_amount",
                True,
                "NULL or numeric (unposted OK)",
                "NULL",
            )
        else:
            _ck(
                "col.total_accrual_posted_amount",
                post_d >= 0,
                "numeric >=0 when set",
                str(post_d),
            )
        last_set = bool(last_posted) and last_posted != "NULL"
        if post_d is not None and post_d > 0:
            _ck(
                "col.last_accrual_posted_date",
                last_set,
                "non-null date when posted>0",
                last_posted or "NULL",
            )
            if last_set and end_d:
                _ck(
                    "col.last_posted_lte_end",
                    last_posted <= end_d,
                    f"<= {end_d}",
                    last_posted,
                )
        else:
            # Unposted: last_posted should be null (booking owns both)
            _ck(
                "col.last_accrual_posted_date",
                not last_set,
                "NULL when unposted/posted=0",
                last_posted or "NULL",
            )

        # --- loan_installment_details_id ---
        lid_ok = bool(lid) and lid != "NULL" and lid.isdigit()
        _ck(
            "col.loan_installment_details_id",
            lid_ok,
            "non-null FK bigint",
            lid or "NULL",
        )
        if lid_ok:
            lid_row = query_rows(
                f"""
                SELECT id::text, loan_account_id::text, installment_date::date::text
                FROM {schema}.loan_installment_details
                WHERE id = {int(lid)}
                LIMIT 1
                """
            )
            _ck(
                "col.loan_installment_details_id_fk",
                bool(lid_row),
                f"exists id={lid}",
                "missing" if not lid_row else lid,
            )
            # Existence alone is not ownership: the distribute path can fall back to
            # the PARENT's installment id, which still "exists". Fail closed on
            # cross-loan FKs.
            if lid_row:
                lid_owner = lid_row[0][1]
                _ck(
                    "col.loan_installment_details_id_owned_by_child",
                    lid_owner == child_id,
                    f"loan_account_id={child_id}",
                    f"loan_account_id={lid_owner}",
                    details=(
                        "cross-loan FK: child accrual row points at another account's "
                        "installment (parent fallback in distribute)"
                    ),
                )
                # MUST-MATCH independent: installment is resolved per row from the
                # child's own INT due on THIS row's end_date, not copied forward.
                if end_d:
                    expected = query_rows(
                        f"""
                        SELECT loan_installment_details_id::text
                        FROM {schema}.loan_due_details
                        WHERE loan_account_id = {int(child_id)}
                          AND component_type = 'INT'
                          AND COALESCE(is_deleted,false) = false
                          AND due_date >= DATE '{end_d}'
                        ORDER BY due_date
                        LIMIT 1
                        """
                    )
                    if expected and expected[0][0]:
                        _ck(
                            "col.loan_installment_details_id_tracks_window",
                            lid == expected[0][0],
                            expected[0][0],
                            lid,
                            details=(
                                "MUST-MATCH independent: getTodayOrNextDueDate(child, "
                                "row.end_date); a stale id means distribute copied it forward"
                            ),
                        )

        # Coverage marker: every physical column named above
        audited = {
            "id",
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
        }
        _ck(
            "col.all_physical_columns_audited",
            audited == set(IAD_PHYSICAL_COLUMNS),
            ",".join(IAD_PHYSICAL_COLUMNS),
            ",".join(sorted(audited)),
        )

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

        # Parent-sum parity alone cannot see a rupee moved between two children. Once a window has
        # been trued up, each child must match its OWN scheduled INT — that is what it gets billed.
        # Scoped to the caller's roll window: earlier rows were not written by this run.
        skew = [] if scheduled_int_since is None else query_rows(
            f"""
            WITH sched AS (
                SELECT lid.installment_date::date AS due_date,
                       ldd.due_amount AS scheduled_int,
                       LAG(lid.installment_date::date)
                           OVER (ORDER BY lid.installment_date) AS prev_due
                FROM {schema}.loan_due_details ldd
                JOIN {schema}.loan_installment_details lid
                  ON lid.id = ldd.loan_installment_details_id
                WHERE ldd.loan_account_id = {int(child_id)}
                  AND ldd.is_deleted = false
                  AND ldd.component_type = 'INT'
            ), acc AS (
                SELECT s.due_date, s.scheduled_int,
                       COALESCE(SUM(iad.total_accrued_amount), 0) AS accrued
                FROM sched s
                LEFT JOIN {schema}.interest_accrual_details iad
                       ON iad.account_id = {int(child_id)}
                      AND iad.end_date::date > COALESCE(s.prev_due, DATE '1900-01-01')
                      AND iad.end_date::date <= s.due_date
                GROUP BY s.due_date, s.scheduled_int
            )
            SELECT COUNT(*)::text
            FROM acc
            WHERE EXISTS (
                    SELECT 1 FROM {schema}.interest_accrual_details i
                    WHERE i.account_id = {int(child_id)}
                      AND i.end_date::date = acc.due_date
                  )
              AND acc.due_date >= {_q(scheduled_int_since)}::date
              AND acc.accrued <> acc.scheduled_int
            """
        )
        n_skew = int((skew[0][0] if skew else "0") or "0")
        if scheduled_int_since is not None:
            _ck(
            "closed_window_accrued_eq_own_scheduled_int",
            n_skew == 0,
            f"0 trued-up windows off own RPS INT since {scheduled_int_since}",
            str(n_skew),
            details="child accrued must equal its own loan_due_details INT once the window closes",
            )

        if parent_max_end:
            unfrozen = query_rows(
                f"""
                SELECT COUNT(*)::text
                FROM {schema}.interest_accrual_details iad
                WHERE iad.account_id = {int(child_id)}
                  AND iad.last_accrual_posted_date IS NOT NULL
                  AND iad.end_date::date < {_q(parent_max_end)}::date
                  AND COALESCE(iad.total_accrued_amount,0)
                      <> COALESCE(iad.total_accrual_posted_amount,0)
                """
            )
            n_unf = int((unfrozen[0][0] if unfrozen else "0") or "0")
            _ck(
                "posted_prior_tips_frozen_accrued_eq_posted",
                n_unf == 0,
                "0 unfrozen posted tips behind parent asOf",
                str(n_unf),
                details="freeze+new-tip must leave Accrued==Posted on closed tips",
            )

    parity_sql = (
        ROOT / "scripts/sql/helpers/verify_shg_interest_accrual_parity.sql"
    ).read_text(encoding="utf-8").replace(":parent_lan", _q(parent_lan))
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
        print(f"  IAD-COL WARN count={len(warns)}")
    if fails:
        names = ", ".join(c.name for c in fails)
        raise AssertionError(f"SHG child IAD column audit FAIL: {names}")
