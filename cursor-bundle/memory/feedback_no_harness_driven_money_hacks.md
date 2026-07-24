---
name: feedback_no_harness_driven_money_hacks
description: Never change money code to green e2e/adversarial harness; understand product path first; QA/fixture data can be wrong
---

# No harness-driven money hacks (Darpan 2026-07-24)

## Correction

Agent added `absorbForceBillIntoIntDueWhenAccruedInstallmentDiffers` in `ForceBillBillingSupport`
so Obs3 Accrued≤Original would pass when Accrued stub was on installment A and force-bill labd
on B. **Reverted.** That was a test-suite / assert patch, not a product fix.

## Standing rule

1. **Understand the real FC/DFC/billing code path first** — amount source, installment attach, GL, dues.
2. **Do not** mutate `due_amount` / IAD / labd solely so `assert_accrued_le_original` or adversarial
   `SEED_EXTRA` / `DCF_SEED_EMI_LABD` fixtures go green.
3. **QA or harness data can be wrong** — prove the fail mode on a normal product path before coding.
4. Prefer **simple** alignment (same installment for Accrued amount and labd, or existing job/booking
   semantics) over compensating writes that paper over A≠B.

## Related

- `feedback_job_owned_tables_no_hand_mutate.md` — no IAD trim hacks either
- `feedback_tdpqa72_obs3_accrued_original.md` — Obs3; reconciler also rejected
