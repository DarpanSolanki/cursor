---
name: feedback_fresh_loan_first_cycle_coverage
description: >-
  Aged-fixture money suites cannot see first-cycle defects. Interest/billing
  coverage needs at least one case that walks a freshly disbursed loan from
  0 IAD / 0 LABD across its first month-end and first due date. 2026-08-03.
---

# Fresh-loan first-cycle coverage (STANDING)

## Incident

Two mature interest suites existed — `flowtest.shg_int_accrual_stitch` and
`flowtest.accrual_billing`. Both **reuse aged fixtures** and derive their roll
window *from existing IAD rows* (`_resolve_roll_window` prefers the next due
after `MAX(end_date)`, and reopens the last installment when accrual has run
past the schedule). Neither had ever walked a loan from zero accrual state.

A fresh JLG disbursement (LAN 6004162725, 2026-08-03, acc `mfi_integration_v3.4.2.4`)
exposed two things on the very first cycle:

1. **`loanAccountBillingJob` FAILED 134207** on the first due date — product 2
   had no `product__transaction_catalogue` row for BILLING/NORMAL_BILLING.
   `interestAccrualCalculation` and `interestAccrualPosting` had passed cleanly
   for the 30 days before it, so any suite asserting only "accrual moved"
   reports green while billing is structurally impossible.
2. **SHG distribute rounding** — per-segment children sum ≠ parent (±₹1) and
   child accrued ≠ child scheduled INT (±₹1). The errors cancel over the
   installment window and across the group, so the existing
   `verify_shg_interest_accrual_parity.sql` returns **PASS (diff 0.000000)**.
   See GAP-082.

## Rule

- Money-flow coverage needs at least one **first-cycle** case per flow family.
  A suite built only on aged fixtures cannot see setup gaps (missing product
  config), first-segment math, or first-boundary behaviour.
- **Reseed, don't drift.** A repeatable first-cycle case must wipe its own
  artefacts (parent **and** children) back to zero before each run, or it
  silently becomes another aged-fixture case after run 1.
- **Net-zero is not parity.** When a check aggregates (window total, group
  total), also assert at the *granularity the ledger is cut at* — per segment,
  per child, per posting day. Opposite-signed rounding errors cancel in the
  aggregate and produce a confident PASS over a real break.

## Where

- Case: `flowtest.fresh_loan_int_accrual_e2e`
  (`scripts/testing/flowtest/scenarios/fresh_loan_int_accrual_e2e.py`) —
  sections A (134207 preflight), K2 (per-segment parity), K3 (child vs own schedule).
- Local product fix: `scripts/sql/setup/local_setup_jlg_billing_catalogue_placeholder_iad.sql`
- Gaps: GAP-082. Related: [[feedback_money_behavior_parity_no_amount_only_ship]].

## Firing cadence is part of the contract — but daily is not required

A money harness that fires batches **sparsely** is not equivalent to one that fires
them repeatedly. But "repeatedly" is far cheaper than "every calendar day".

Measured on SHG parent 6004162825 (verified-current bytecode, incl. `ad399c5f2`):

| mode | fires | wall | per-segment parity (K2) |
|------|------:|-----:|-------------------------|
| posting_days (month-end + due only) | 2 | 23s | **PASSES — defect hidden** |
| hop (posting days + 1 intermediate per gap) | 4 | 32s | FAILS 307/306, 701/702 |
| daily (full EOD walk) | 34 | ~6min | FAILS 307/306, 701/702 |

The SHG per-segment break accrues from **repeated re-distribution of the open
segment**, so one intermediate calc per gap is sufficient; the other 30 days add
nothing. `hop` is the default for group loans — same fidelity, ~11x less wall.
Standalone loans have no distribute step and are byte-identical under posting_days.

Rule: don't equate "faithful" with "daily". Identify the *mechanism* the defect
needs (here: >1 distribute per segment) and fire the minimum that exercises it —
then prove equivalence against the full walk before making it the default.

## Also learned

- The due-date segment is **trued-up to the scheduled installment INT**
  (`InterestAccrualCalculationBatchService.getAccruedInterestOnDueDate`), not
  day-count × rate. Assert `Σ accrued per installment == loan_due_details INT`
  for due segments; keep the day-count formula assert for non-due segments only.
- Yugabyte evaluates FK checks against the transaction snapshot: batching a
  child-then-parent delete in one `psql -c` still fails the FK. Issue one
  statement per call, and enumerate FK children from `pg_constraint`
  (`transaction_master` has three: partition details, details, metadata).
