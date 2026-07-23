# Job-owned tables (accounting) — never hand-mutate

**Standing rule (TDPQA-72 2026-07-24):** Tables whose rows are produced/advanced by **batch jobs** (or the same job services invoked via orchestration) must **not** be patched by ad-hoc writer code, ops SQL, or “summary fix” helpers that `set*` money fields and `save`.

Fix the **producer path** (force-bill via BILLING `postTransaction`, forceful accrual **booking** processor, correct settlement amounts). Do **not** zero/trim staging columns to make UI Accrued/Original line up.

## Allowed vs forbidden

| Allowed | Forbidden |
|---------|-----------|
| Job `*ItemWriter` / `*BatchService` that owns the table | `iad.setTotalAccruedAmount(ZERO)` + `dao.save` from DCF/FC writer |
| Orch calling the **same** job service (e.g. `checkLoanAccountInterestAccrualBookingProcessor` → forceful booking) | Raw SQL `UPDATE interest_accrual_details SET total_accrued_amount=…` |
| Money APIs that go through catalogue `postTransaction` (creates labd / GL the normal way) | Inventing Accrued≤Original by editing IAD outside booking/calc |
| Soft-delete / ops archive only when an approved ops pack says so | “Reconcile” helpers that rewrite job staging to pass asserts |

## Job-owned map (accounting)

| Table | Owning job(s) / Request | What job owns | Legitimate non-job path (if any) |
|-------|-------------------------|---------------|----------------------------------|
| `interest_accrual_details` | `interestAccrualCalculation` (UPSERT periods); `interestAccrualPosting` / LMS-IAP (posted amounts + dates) | `total_accrued_amount`, period windows, `total_accrual_posted_amount`, posting dates | **Forceful booking** via `CheckLoanAccountInterestAccrualBookingProcessor` → same booking service. **Not** arbitrary Accrued trim. |
| `penal_interest_accrual_details` | `penalInterestAccrualCalculation`; `penalInterestAccrualBooking` | Penal period Accrued + booking markers | `bookingNonPostedPenalProcessor` on FC/DFC (same booking semantics) |
| `dpi_accrual_details` | DPI accrual calc/booking (3.7.1 DPI train) | DPI Accrued / posted / bill markers | DPI orch siblings only — not hand SQL |
| `loan_account_billing_details` | `loanAccountBillingJob` | EMI / cycle billing rows + BILLING GL | **Force-bill** = `postTransaction` BILLING/NORMAL_BILLING then persist interest-only labd (`ForceBillBillingSupport`). Do **not** UPDATE `interest_amount` on an existing EMI labd to fake force-bill. |
| `loan_account` DPD / delinq fields (`past_due_days`, `delinq_string`, …) | `loanAccountDpdCalcJob` | Delinquency markers | No hand patch for “looks better on summary” |
| `loan_account` NPA / asset fields (`asset_criteria_slabs_id`, `npa_*`, suspense, …) | `loanAccountAssetCriteriaJob` (+ classification) | Asset / NPA state | Movement GL via job/orch only |
| `loan_account_derived_fields` | `updateLoanAccountDerivedFieldsJob` (+ monthly) | Denorm / classification display fields | Refresh via job, not one-off UPDATE |
| `trial_balance` (+ zeroisation outputs) | `trialBalanceCalculation` / `trialBalanceZeroisationJob` | Daily TB snapshot | Never patch to force TB balance |

## Not job-exclusive (do not over-ban)

These are written by APIs/orch as well as jobs — still prefer contract paths, but they are **not** “job-only staging”:

- `loan_due_details`, `loan_installment_details` — repayment / FC / DCF / waiver / billing booking
- `transaction_master` / partitions / details — any `postTransaction`
- `loan_account_payments_details` — prepayment / DCF settlement persist
- `account` / `loan_account` status & balances — lifecycle APIs (still no inventing money)

## Anti-pattern (do not reintroduce)

`DeathForeclosureInsuranceWriter.reconcileAccruedInterestToBilledOriginal` (removed on tip `5f4661b03`, briefly restored then reverted 2026-07-24): zeroed/trimmed `interest_accrual_details.total_accrued_amount` so summary Accrued ≤ Original. **Rejected** — IAD is job-owned; Accrued must move via accrual booking + BILLING, not writer mutate.

## Related

- `batchnew-jobs.md` — per-job behaviour
- `booking-billing-posting-accrual.md` — lifecycle stages
- `critical-lessons.md` — incident lessons (includes this rule)
- Brain: `cursor-bundle/brain/system/07-batch-atlas.md`, `accounting/db-code-map/by-flow/eod-bod.md`
