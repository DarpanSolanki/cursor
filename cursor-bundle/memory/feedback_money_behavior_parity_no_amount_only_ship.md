---
name: feedback_money_behavior_parity_no_amount_only_ship
description: >-
  Money ships that replace an existing write path must keep calendar/state/FK
  behavior parity — amount-only PASS is forbidden. Carry on SHG distribute is
  intentional 0. 2026-07-31.
---

# Money behavior parity (STANDING — production bar)

## Incident

SHG INT Accrued distribute shipped with **window sum parity PASS** while child IAD
`end_date` stayed mid-month (independent child calc would have advanced tip).
Column audit later caught it; WARN-as-pass was wrong.

## Rule

When a change **replaces or bypasses** an existing money write path (distribute vs
independent calc, batch vs online, parent vs child):

1. **Amount SoT** (sums / fractions) — required, not sufficient.
2. **Behavior parity** — calendar (`end_date`/`asOf`), booking gates, FKs,
   status columns the old path wrote must still match unless the ticket **explicitly**
   scopes a behavior change and registry asserts the new contract fail-closed.
3. **Column audit** — value-level on every touched money table column that matters
   for booking/UI (not presence-only, not sum-only).
4. **Never** ship with WARN-only on money calendar/state defects.

## SHG INT distribute vs independent child calc (parity matrix)

| Field / side-effect | Independent `createOrUpdateIADE` | Distribute | Class |
|---------------------|----------------------------------|------------|-------|
| `total_accrued_amount` | Child daily/RPS calc | Parent window share SET | **INTENTIONAL** (only amount SoT difference) |
| `carry_over_amount` | Rounding carry from child calc | New tip hard `0`; update does not clear legacy | **INTENTIONAL** — do not require independent carry. `getFinalAmountListUsingCarryOver` is in-memory paisa split across children, **not** IAD.carry |
| `end_date` / asOf tip advance | `updateExisting` / `createNew` to accrual end | tipBehind → extend or freeze+new to parent asOf | **MUST-MATCH** |
| create-new vs update when posted | `lastAccrualPostedDate != null` → createNew | tipBehind + posted → freeze Accrued=Posted + new tip | **MUST-MATCH** |
| tipBehind, unposted | `updateExisting` set Accrued + endDate | set Accrued + `setEndDate(asOf)` | **MUST-MATCH** |
| `account_id` | child | child | **MUST-MATCH** |
| `start_date` | prior tip end / disb | empty window: prevDue; freeze+new: prior tip end | **MUST-MATCH** |
| `base_amount` | from aide / outstanding | copy prior tip (or 0 if none) | **MUST-MATCH** when prior tip exists |
| `interest_rate` | `aide.effectiveRate` | copy prior tip | **MUST-MATCH** tip vs aide |
| `loan_installment_details_id` | current due LID | prior tip LID or parent installment id | **MUST-MATCH** non-null |
| `total_accrual_posted_amount` / `last_accrual_posted_date` | booking path owns | distribute does not invent; freeze uses posted | **MUST-MATCH** (booking) |
| Accrued ≥ Posted | invariant | invariant + freeze | **MUST-MATCH** |
| Reader SQL children | N/A (children calc) | `parent_loan_account_id IS NULL` — children via distribute only | **MUST-MATCH** (exclude) |
| Soft-delete | N/A on IAD entity | N/A on IAD entity | N/A |

## Machine

- `scripts/lib/money_behavior_parity_gate.py` (wired into `ship_discipline_gate`)
- `flowtest/iad_column_audit.py` — tip `end_date` == parent asOf **FAIL** closed; tip carry 0 on synced tip; rate vs aide; frozen posted tips
- `acceptance_coverage_manifest` — `interest_accrual` enforced + IAD required columns

## Agent checklist (every JIRA / enhancement / money fix)

Before claiming Pass: real flow → **all IAD physical columns** (schema SoT) →
adversarial/dirty → tip/calendar if IAD/group → impact matrix includes behavior
parity → no WARN-as-pass → no invented carry "fix" for distribute.

IAD physical columns (11): id, account_id, base_amount, start_date, end_date,
interest_rate, total_accrued_amount, carry_over_amount, total_accrual_posted_amount,
last_accrual_posted_date, loan_installment_details_id. No created_by/updated_on on table.

