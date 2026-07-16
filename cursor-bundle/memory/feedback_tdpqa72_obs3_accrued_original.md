---
name: feedback_tdpqa72_obs3_accrued_original
description: Parent Accrued>Original after last-child DFC — IAD past last billed INT due; write-path reconcileAccruedInterestToBilledOriginal
---

# TDPQA-72 Obs3 — Accrued > Original after group last-child DFC

## Fail mode (QA + local)

Summary screen: **Accrued > Original** on **parent** after sibling FC/RSCH + last-child death FC.

- **Original** = `getBilledInterestAmount` = SUM(INT `due_amount`) WHERE installment has non-reversed labd
- **Accrued** = SUM(`interest_accrual_details.total_accrued_amount`)
- Webapp: `getLoanAccountSummaryDetails` → `interest_details.accrued_amount` / `original_amount`

Local proof: Accrued through last billed INT due ≈ Original; Accrued after that date is the gap.
Children Accrued==Original after force-bill labd.

Root: after sibling FC → parent RSCH, **new schedule INT dues lack labd** while IAD for those
calendar periods remains. Child-only force-bill does not close parent gap.

## Permanent write-path

`DeathForeclosureInsuranceWriter.reconcileAccruedInterestToBilledOriginal`:
- After child force-bill and after parent `waiveFutureInterestPastReporting` on last-child
- Max billed INT due_date via `getDueDetails` + `findByLoanInstallmentDetailsId` (reuse + Java)
- Zero `total_accrued_amount` on IAD with `end_date` after cutoff; batch save

Do **not** invent parent `DFC_PRTL_BILL` (Obs1b Out-of-scope).

## Asserts

- SQL: `assert_accrued_le_original`
- Webapp: `assert_webapp_bound_apis` → summary nested interest fields

## Fixture

QA LANs 6011375325 / 5655 / 5656 — full QA→local multi-table clone not available; **equivalent
local product-70 SHG** via e2e auto-discover + `DCF_SEED_EMI_LABD=1` + EXTRA. Non-last child DFC
triggers parent RSCH (same Accrued orphan class as Vikram regular-FC-then-DFC).
