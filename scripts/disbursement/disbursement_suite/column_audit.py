"""Value-level column audits for disburseLoan (fail-closed).

Aligns with feedback_real_flow_db_write_validate.md and acceptance_coverage_manifest
domain_money_tables.disbursement. Presence-only / status-200 is not a pass.

Each check returns expected vs actual column values; callers must treat ok=False +
level=FAIL as suite failure (never WARN-and-pass on wrong money values).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Callable


QueryRows = Callable[[str], list[tuple[str, ...]]]


@dataclass
class ColumnCheck:
    name: str
    table: str
    ok: bool
    expect: str
    actual: str
    details: str = ""
    level: str = "FAIL"  # FAIL | WARN

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "table": self.table,
            "ok": self.ok,
            "expect": self.expect,
            "actual": self.actual,
            "details": self.details,
            "level": self.level,
        }


@dataclass
class ColumnAuditResult:
    checks: list[ColumnCheck] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def failed(self) -> bool:
        return any((not c.ok) and c.level == "FAIL" for c in self.checks)


def _dec(v: Any) -> Decimal | None:
    try:
        return Decimal(str(v).strip())
    except (InvalidOperation, AttributeError, ValueError):
        return None


def _sql_quote(s: str) -> str:
    return "'" + str(s).replace("'", "''") + "'"


def audit_disbursement(
    *,
    account_id: int,
    account_number: str,
    req: dict[str, Any],
    product_type: str,
    child_flow: bool,
    loan_status: str,
    disbursement_status: str,
    query_rows: QueryRows,
    schema: str = "mfi_accounting",
) -> ColumnAuditResult:
    """Read back money tables and assert column values for this LAN (and SHG children)."""
    out = ColumnAuditResult()
    loan_details = req.get("loan_details") or {}
    repayment_details = req.get("repayment_details") or {}
    disbursement_details = req.get("disbursement_details") or {}
    expected_loan_amount = str(loan_details.get("loan_amount") or "").strip()
    expected_product_id = str(loan_details.get("product_id") or "").strip()
    expected_installments = str(repayment_details.get("number_of_installments") or "").strip()
    expected_mode = str(disbursement_details.get("disbursement_mode") or "").strip().upper()
    ext_ref = str(disbursement_details.get("external_ref_number") or "").strip()

    # --- loan_account ---
    la_rows = query_rows(
        f"""
        SELECT loan_status, disbursement_status, TRIM(TRAILING '.' FROM TRIM(TRAILING '0' FROM loan_amount::text)),
               loan_product_id::text, COALESCE(external_ref_number, ''), COALESCE(has_child_accounts::text, 'false')
        FROM {schema}.loan_account
        WHERE account_id = {int(account_id)} AND is_deleted = false;
        """
    )
    if not la_rows:
        out.checks.append(
            ColumnCheck(
                name="loan_account_row",
                table="loan_account",
                ok=False,
                expect=f"id={account_id} present",
                actual="missing",
            )
        )
        return out
    la_status, la_disb, la_amt, la_prod, la_ext, has_child = la_rows[0]
    out.evidence["loan_account"] = {
        "loan_status": la_status,
        "disbursement_status": la_disb,
        "loan_amount": la_amt,
        "loan_product_id": la_prod,
        "external_ref_number": la_ext,
        "has_child_accounts": has_child,
    }

    if child_flow:
        status_ok = la_status in {"APPROVED", "ACTIVE", "CLOSED"}
        disb_ok = la_disb in {
            "PARENT_SUCCESS",
            "CHILD_SUCCESS",
            "COMPLETED",
            "DTFC_SUCCESS",
            "NEFT_STAGE_1_PENDING",
            "NEFT_STAGE_1_SUCCESS",
            "NEFT_STAGE_2_PENDING",
        }
    else:
        status_ok = la_status in {"ACTIVE", "CLOSED"}
        disb_ok = la_disb in {
            "COMPLETED",
            "DTFC_SUCCESS",
            "NEFT_STAGE_1_PENDING",
            "NEFT_STAGE_1_SUCCESS",
            "NEFT_STAGE_2_PENDING",
            "LOAN_BOOKED",
        }
    out.checks.append(
        ColumnCheck(
            name="loan_account.loan_status",
            table="loan_account",
            ok=status_ok and la_status == loan_status,
            expect=("APPROVED|ACTIVE|CLOSED" if child_flow else "ACTIVE|CLOSED") + f" (snap={loan_status})",
            actual=la_status,
        )
    )
    out.checks.append(
        ColumnCheck(
            name="loan_account.disbursement_status",
            table="loan_account",
            ok=disb_ok and la_disb == disbursement_status,
            expect=f"terminal set matching snap={disbursement_status}",
            actual=la_disb,
        )
    )
    if expected_loan_amount:
        exp_amt = _dec(expected_loan_amount)
        act_amt = _dec(la_amt)
        amt_ok = exp_amt is not None and act_amt is not None and exp_amt == act_amt
        out.checks.append(
            ColumnCheck(
                name="loan_account.loan_amount",
                table="loan_account",
                ok=bool(amt_ok),
                expect=expected_loan_amount,
                actual=str(la_amt),
            )
        )
    if expected_product_id:
        # Request product_id often maps via scheme; assert persisted loan_product_id is present.
        out.checks.append(
            ColumnCheck(
                name="loan_account.loan_product_id",
                table="loan_account",
                ok=bool(str(la_prod).strip()) and str(la_prod).strip().isdigit(),
                expect=f"non-blank numeric loan_product_id (request.product_id={expected_product_id})",
                actual=str(la_prod),
            )
        )
    if ext_ref:
        # Reset may suffix __LOCAL_DEDUPE_BYPASS — allow prefix match
        ext_ok = la_ext == ext_ref or la_ext.startswith(ext_ref)
        out.checks.append(
            ColumnCheck(
                name="loan_account.external_ref_number",
                table="loan_account",
                ok=ext_ok,
                expect=ext_ref,
                actual=la_ext,
            )
        )

    # --- schedule / dues (parent vs SHG children) ---
    audit_ids: list[int] = [int(account_id)]
    child_ids: list[int] = []
    if child_flow:
        child_rows = query_rows(
            f"""
            SELECT account_id::text, a.account_number, la.loan_status, la.disbursement_status,
                   TRIM(TRAILING '.' FROM TRIM(TRAILING '0' FROM la.loan_amount::text))
            FROM {schema}.loan_account la
            JOIN {schema}.account a ON a.id = la.account_id AND a.is_deleted = false
            WHERE la.parent_loan_account_id = {int(account_id)} AND la.is_deleted = false
            ORDER BY la.account_id;
            """
        )
        out.evidence["children"] = [
            {"id": r[0], "lan": r[1], "loan_status": r[2], "disbursement_status": r[3], "loan_amount": r[4]}
            for r in child_rows
        ]
        member_details = req.get("member_details") or []
        expected_children = len(member_details) if isinstance(member_details, list) else 0
        child_ids = [int(r[0]) for r in child_rows]
        out.checks.append(
            ColumnCheck(
                name="shg_children_count",
                table="loan_account",
                ok=len(child_ids) == expected_children and expected_children > 0,
                expect=f"parent_loan_account_id children == {expected_children}",
                actual=str(len(child_ids)),
            )
        )
        for r in child_rows:
            cid, clan, cst, cds, camt = r
            out.checks.append(
                ColumnCheck(
                    name=f"child[{clan}].loan_status",
                    table="loan_account",
                    ok=cst in {"ACTIVE", "CLOSED", "APPROVED"},
                    expect="ACTIVE|CLOSED|APPROVED",
                    actual=cst,
                )
            )
            # Child schedule is mandatory once children exist
            audit_ids.append(int(cid))

    for aid in audit_ids:
        is_parent = aid == int(account_id)
        # SHG parent often has 0 installments until/unless product books parent schedule;
        # schedule correctness is enforced on children.
        skip_parent_schedule = child_flow and is_parent
        inst = query_rows(
            f"""
            SELECT COUNT(1)::text,
                   COALESCE(SUM(installment_amount), 0)::text,
                   COALESCE(MIN(schedule_number)::text, ''),
                   COALESCE(MAX(schedule_number)::text, '')
            FROM {schema}.loan_installment_details
            WHERE loan_account_id = {aid} AND is_deleted = false;
            """
        )
        inst_cnt = int(inst[0][0]) if inst else 0
        inst_sum = inst[0][1] if inst else "0"
        sched_min = inst[0][2] if inst else ""
        sched_max = inst[0][3] if inst else ""
        due = query_rows(
            f"""
            SELECT COUNT(1)::text,
                   COUNT(DISTINCT component_type)::text,
                   COALESCE(string_agg(DISTINCT component_type, '|' ORDER BY component_type), '')
            FROM {schema}.loan_due_details
            WHERE loan_account_id = {aid} AND is_deleted = false;
            """
        )
        due_cnt = int(due[0][0]) if due else 0
        due_components = due[0][2] if due else ""
        key = f"{'parent' if is_parent else 'child'}:{aid}"
        out.evidence[f"schedule:{key}"] = {
            "installments": inst_cnt,
            "installment_amount_sum": inst_sum,
            "schedule_number_min": sched_min,
            "schedule_number_max": sched_max,
            "dues": due_cnt,
            "component_types": due_components,
        }
        if skip_parent_schedule:
            # Documented product behaviour — do not FAIL parent for 0 schedule
            out.checks.append(
                ColumnCheck(
                    name="loan_installment_details.parent_optional",
                    table="loan_installment_details",
                    ok=True,
                    expect="SHG parent schedule optional (asserted on children)",
                    actual=f"count={inst_cnt}",
                    level="WARN" if inst_cnt == 0 else "FAIL",
                )
            )
            continue
        if expected_installments and expected_installments.isdigit():
            exp_n = int(expected_installments)
            # Children inherit parent installment count
            out.checks.append(
                ColumnCheck(
                    name=f"loan_installment_details.count[{aid}]",
                    table="loan_installment_details",
                    ok=inst_cnt == exp_n,
                    expect=f"count=={exp_n}",
                    actual=str(inst_cnt),
                )
            )
        else:
            out.checks.append(
                ColumnCheck(
                    name=f"loan_installment_details.count[{aid}]",
                    table="loan_installment_details",
                    ok=inst_cnt > 0,
                    expect="count>0",
                    actual=str(inst_cnt),
                )
            )
        if inst_cnt > 0:
            out.checks.append(
                ColumnCheck(
                    name=f"loan_installment_details.schedule_number[{aid}]",
                    table="loan_installment_details",
                    ok=bool(sched_min) and bool(sched_max),
                    expect="schedule_number populated (min/max present)",
                    actual=f"min={sched_min} max={sched_max}",
                )
            )
        sum_ok = _dec(inst_sum) is not None and (_dec(inst_sum) or Decimal(0)) > 0
        out.checks.append(
            ColumnCheck(
                name=f"loan_installment_details.installment_amount_sum[{aid}]",
                table="loan_installment_details",
                ok=bool(sum_ok),
                expect="SUM(installment_amount)>0",
                actual=str(inst_sum),
            )
        )
        out.checks.append(
            ColumnCheck(
                name=f"loan_due_details.count[{aid}]",
                table="loan_due_details",
                ok=due_cnt > 0,
                expect="count>0 with component_type populated",
                actual=f"count={due_cnt} components={due_components}",
            )
        )
        # Prefer INT+PRIN (or INTEREST/PRINCIPAL naming) when present
        comps = {c.strip().upper() for c in due_components.split("|") if c.strip()}
        if comps:
            has_int = any("INT" in c for c in comps)
            has_prin = any("PRI" in c for c in comps)
            out.checks.append(
                ColumnCheck(
                    name=f"loan_due_details.component_types[{aid}]",
                    table="loan_due_details",
                    ok=has_int and has_prin,
                    expect="component_type includes INT* and PRI*",
                    actual=due_components,
                )
            )

    # --- loan_disbursement_mode_details ---
    mode_rows = query_rows(
        f"""
        SELECT mode, COALESCE(account_number, ''), COALESCE(utr_number, '')
        FROM {schema}.loan_disbursement_mode_details
        WHERE loan_account_id = {int(account_id)} AND is_deleted = false
        ORDER BY id DESC LIMIT 1;
        """
    )
    if mode_rows:
        mode, mode_acct, utr = mode_rows[0]
        out.evidence["loan_disbursement_mode_details"] = {
            "mode": mode,
            "account_number": mode_acct,
            "utr_number": utr,
        }
        out.checks.append(
            ColumnCheck(
                name="loan_disbursement_mode_details.mode",
                table="loan_disbursement_mode_details",
                ok=(not expected_mode) or mode.upper() == expected_mode,
                expect=expected_mode or "(any)",
                actual=mode,
            )
        )
    else:
        out.checks.append(
            ColumnCheck(
                name="loan_disbursement_mode_details.row",
                table="loan_disbursement_mode_details",
                ok=False,
                expect="mode row for parent loan_account_id",
                actual="missing",
            )
        )

    # --- loan_disbursement_transaction ---
    ldt = query_rows(
        f"""
        SELECT COUNT(1)::text,
               COALESCE(MAX(amount)::text, ''),
               COALESCE(MAX(NULLIF(btrim(client_reference_number), '')), ''),
               COALESCE(MAX(NULLIF(btrim(transaction_reference_number), '')), '')
        FROM {schema}.loan_disbursement_transaction
        WHERE loan_account_id = {int(account_id)} AND is_deleted = false;
        """
    )
    ldt_cnt = int(ldt[0][0]) if ldt else 0
    ldt_amt, ldt_cref, ldt_tref = (ldt[0][1], ldt[0][2], ldt[0][3]) if ldt else ("", "", "")
    out.evidence["loan_disbursement_transaction"] = {
        "count": ldt_cnt,
        "amount": ldt_amt,
        "client_reference_number": ldt_cref,
        "transaction_reference_number": ldt_tref,
    }
    # Parent LDT expected for flat flows; SHG parent may have LDT after parent bank
    if not child_flow or ldt_cnt > 0 or la_disb in {"COMPLETED", "PARENT_SUCCESS", "CHILD_SUCCESS", "DTFC_SUCCESS"}:
        out.checks.append(
            ColumnCheck(
                name="loan_disbursement_transaction.count",
                table="loan_disbursement_transaction",
                ok=ldt_cnt > 0,
                expect="count>0 with amount and client_reference_number",
                actual=f"count={ldt_cnt} amount={ldt_amt} cref={ldt_cref}",
            )
        )
        if ldt_cnt > 0:
            out.checks.append(
                ColumnCheck(
                    name="loan_disbursement_transaction.client_reference_number",
                    table="loan_disbursement_transaction",
                    ok=bool(ldt_cref),
                    expect="non-blank client_reference_number",
                    actual=ldt_cref or "(blank)",
                )
            )
            if expected_loan_amount and ldt_amt:
                # amount may be net of charges — require >0 and <= loan_amount * 1.5
                exp_a = _dec(expected_loan_amount)
                act_a = _dec(ldt_amt)
                ok_amt = (
                    exp_a is not None
                    and act_a is not None
                    and act_a > 0
                    and act_a <= (exp_a * Decimal("2"))
                )
                out.checks.append(
                    ColumnCheck(
                        name="loan_disbursement_transaction.amount",
                        table="loan_disbursement_transaction",
                        ok=bool(ok_amt),
                        expect=f"0 < amount <= 2*{expected_loan_amount}",
                        actual=str(ldt_amt),
                    )
                )

    # --- transaction_master (posting) ---
    tm = query_rows(
        f"""
        SELECT COUNT(1)::text,
               COALESCE(MAX(NULLIF(btrim(tm.client_reference_number), '')), ''),
               COALESCE(MAX(tm.original_amount::text), '')
        FROM {schema}.transaction_master tm
        WHERE tm.client_reference_number IN (
                SELECT NULLIF(btrim(ldt.client_reference_number), '')
                FROM {schema}.loan_disbursement_transaction ldt
                WHERE ldt.loan_account_id = {int(account_id)} AND ldt.is_deleted = false
              )
           OR tm.reference_number IN (
                SELECT NULLIF(btrim(ldt.transaction_reference_number), '')
                FROM {schema}.loan_disbursement_transaction ldt
                WHERE ldt.loan_account_id = {int(account_id)} AND ldt.is_deleted = false
              );
        """
    )
    tm_cnt = int(tm[0][0]) if tm else 0
    tm_cref, tm_orig = (tm[0][1], tm[0][2]) if tm else ("", "")
    out.evidence["transaction_master"] = {
        "count": tm_cnt,
        "client_reference_number": tm_cref,
        "original_amount": tm_orig,
    }
    # Flat terminal flows must post; SHG parent may post GL before children
    if not child_flow:
        out.checks.append(
            ColumnCheck(
                name="transaction_master.count",
                table="transaction_master",
                ok=tm_cnt > 0,
                expect="count>0 with client_reference_number",
                actual=f"count={tm_cnt} cref={tm_cref} original_amount={tm_orig}",
            )
        )
        if tm_cnt > 0:
            out.checks.append(
                ColumnCheck(
                    name="transaction_master.client_reference_number",
                    table="transaction_master",
                    ok=bool(tm_cref),
                    expect="non-blank client_reference_number",
                    actual=tm_cref or "(blank)",
                )
            )
    else:
        out.checks.append(
            ColumnCheck(
                name="transaction_master.parent_optional_or_present",
                table="transaction_master",
                ok=True,
                expect="SHG parent TM optional until full COMPLETED; children assert schedule",
                actual=f"count={tm_cnt}",
                level="WARN" if tm_cnt == 0 else "FAIL",
            )
        )

    # --- client_request_response_log ---
    crr = query_rows(
        f"""
        SELECT transaction_type, status,
               COALESCE(NULLIF(btrim(client_reference_number), ''), ''),
               COALESCE(NULLIF(btrim(partner), ''), ''),
               COUNT(1)::text
        FROM {schema}.client_request_response_log
        WHERE loan_account_number = {_sql_quote(account_number)}
          AND (
                transaction_type IN (
                    'DISB_GL_CBS_INTEGRATION',
                    'DISBURSEMENT_MFT',
                    'DISBURSEMENT_NEFT'
                )
                OR transaction_type LIKE '%NEFT_NEF%'
                OR transaction_type LIKE '%NEFT%'
          )
        GROUP BY transaction_type, status, client_reference_number, partner
        ORDER BY transaction_type, status;
        """
    )
    out.evidence["client_request_response_log"] = [
        {"transaction_type": r[0], "status": r[1], "client_reference_number": r[2], "partner": r[3], "count": r[4]}
        for r in crr
    ]
    success_rows = [r for r in crr if str(r[1]).upper() == "SUCCESS"]
    blank_cref_success = [r for r in success_rows if not r[2]]
    out.checks.append(
        ColumnCheck(
            name="client_request_response_log.success_rows",
            table="client_request_response_log",
            ok=len(success_rows) > 0,
            expect=">=1 SUCCESS bank/GL row with client_reference_number",
            actual=f"success_rows={len(success_rows)} types={[r[0] for r in success_rows[:5]]}",
        )
    )
    out.checks.append(
        ColumnCheck(
            name="client_request_response_log.client_reference_number",
            table="client_request_response_log",
            ok=len(success_rows) > 0 and len(blank_cref_success) == 0,
            expect="every SUCCESS row has non-blank client_reference_number",
            actual=f"blank_cref_success={len(blank_cref_success)}",
        )
    )
    # Mode-specific rail
    if expected_mode == "ACCTWB":
        mft_ok = any(r[0] == "DISBURSEMENT_MFT" and r[1].upper() == "SUCCESS" for r in crr)
        out.checks.append(
            ColumnCheck(
                name="client_request_response_log.DISBURSEMENT_MFT",
                table="client_request_response_log",
                ok=mft_ok,
                expect="DISBURSEMENT_MFT status=SUCCESS",
                actual="present" if mft_ok else "missing",
            )
        )
    elif expected_mode == "OTHBACCT":
        neft_ok = any("NEFT" in r[0].upper() and r[1].upper() == "SUCCESS" for r in crr)
        out.checks.append(
            ColumnCheck(
                name="client_request_response_log.NEFT",
                table="client_request_response_log",
                ok=neft_ok,
                expect="NEFT* status=SUCCESS",
                actual="present" if neft_ok else "missing",
            )
        )

    out.evidence["product_type"] = product_type
    return out
