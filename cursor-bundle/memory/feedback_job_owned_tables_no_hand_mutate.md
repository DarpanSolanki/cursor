---
name: feedback_job_owned_tables_no_hand_mutate
description: Accounting job staging (IAD etc.) never hand-updated — fix via job/booking/BILLING path only
---

# Job-owned tables — never hand-mutate (accounting)

Triggered TDPQA-72 (2026-07-24): restoring `reconcileAccruedInterestToBilledOriginal`
(zero/trim `interest_accrual_details.total_accrued_amount` in DCF writer) was rejected —
IAD is updated only via accrual **jobs** (and forceful booking processor), not summary hacks.

**Map:** `.cursor/skills/accounting-knowledge/job-owned-tables.md`

**Do:** force-bill via BILLING `postTransaction`; forceful accrual booking; correct settlement.
**Don't:** writer/SQL `UPDATE` Accrued columns to pass Accrued≤Original asserts.
