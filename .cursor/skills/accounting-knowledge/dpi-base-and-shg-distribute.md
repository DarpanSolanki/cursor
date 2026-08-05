# DPI base_amount and the SHG parent→child distribute (3.7.1 DPI train)

Read before touching `DpiAccrualCalculationBatchService`, `DpiGroupLoanAccrualDistributionService`,
or anything that writes `mfi_accounting.dpi_accrual_details`.

## What `base_amount` means

`dpi_accrual_details.base_amount` is the **overdue principal + interest that DPI is charging on**
for that segment — not the outstanding principal, and not the EMI.

It is **cumulative from the DPI cut-off**, not per-installment. As each admitted installment falls
overdue it is added:

| segment | admitted installments | base |
|---------|----------------------|------|
| May     | May                  | 14,528 |
| Jun     | May + Jun            | 29,056 |
| Jul     | May + Jun + Jul      | 43,584 |

Two gates decide which installments count, and **both** must be applied:

1. **Go-live cut-off** — only installments whose admission date is on/after the product's
   configured DPI go-live date. Pre-cut-off arrears are never charged DPI.
2. **Admission date** — `DPICalculationService.resolveAdmissionOverdueDate`, which is the stored
   `loan_due_details.overdue_date` **only**. The `graceDays` argument is currently ignored; grace
   is already baked into `overdue_date` at schedule creation. Do not re-add grace arithmetic.

Rows with `due_amount - paid_amount - waived_amount <= 0` are excluded per row.

Parent-side implementation: `precomputeDaySnapshots` walks day by day, admitting into a running
base — so the base is a snapshot **at the segment's start date**, not at its end.

## SHG: children mirror the parent, but carry their OWN base

`DpiGroupLoanAccrualDistributionService` splits the parent's accrued amount across ACTIVE children
and writes one child row per parent segment.

| column | child value |
|--------|-------------|
| `base_amount` | the **child's own** overdue PRIN+INT under the same two gates — never the parent's |
| `total_accrued_amount` | the child's share of the **parent's** accrued (parent is the SoT) |
| `start_date` / `end_date` / `dpi_annual_rate` / `days_in_year` | copied from the mirrored parent segment |
| `carry_over_amount` | 0 on distribute-owned rows |
| `installment_id` | the **child's own** installment (a parent FK here is a cross-loan defect) |

**Invariants**

- `sum(children.base_amount) == parent.base_amount` per segment — **exact**. The group's arrears
  are the sum of its members' arrears.
- `sum(children.total_accrued_amount) == parent.total_accrued_amount` — **exact over the window**,
  but a single segment may drift by up to the child count. Accrued is split at scale 0 because
  booking rejects a fractional accrual, so `23/3` becomes `8+8+8=24` and the next segment gives the
  rupee back. Asserting exact per-segment equality on *accrued* is a false failure; asserting it on
  *base* is mandatory.

The go-live date and grace are resolved once by the calc batch and passed to the distribute service
on `DpiAccrualCalculationVo`. Do **not** re-resolve them there, and do **not** infer the cut-off
from existing accrual rows — accruals get purged and rebuilt, which silently moves an inferred floor.

## TDPQA-234 (2026-08-04) — how this went wrong

Child rows were stamped from `getTotalOverdueAmountByAccountIdsAndDate`, which applies neither gate:
no go-live filter, no per-row outstanding guard, and `due_date <` instead of the admission date. On
QA1 the parent held 14,528 / 29,056 / 43,584 while children held 27,346 / 34,193 / 41,040 —
four pre-cut-off installments the parent never charged on. Children summed to 58,134 against a
parent base of 14,528.

It survived review because the column audit checked `base_amount >= 0` on the **tip row only**.
Presence-only asserts pass every wrong value. See `.cursor/rules/40-knowledge-upkeep.mdc`.

**Blast radius is display/audit, not money:** nothing reads `dpi_accrual_details.base_amount` back
to compute a charge — child accrued comes from the parent's accrued, not from the child's base. A
wrong base is a wrong audit trail and a QA reject, not a mischarge. Confirm this still holds before
assuming it.

## Verify

```bash
bash scripts/dpic/run_dpi_shg_parent_child_parity.sh    # calc → booking → billing, audit after each
ntest run dpic.shg_parent_child_parity
```

`flowtest.dad_column_audit.audit_shg_child_dad_all_rows` re-derives every expected value in SQL and
walks **every** row, not the tip.
