# loanDeathForeclosure — DCF claim → settle / RSCH

## Symptom
Death foreclosure job fails, parent/child amounts disagree, force-bill missing/hijacked, CRN collision **134497**, or Accrued>Original on parent.

## Entry points
- **API/orch:** `loanDeathForeclosure` (initiation / stages)
- **Batch:** `deathForeclosureInsuranceJob` → `DeathForeclosureInsuranceWriter`
- **Cross-service:** `Pending for FR` → `updateTaskWorkflow` (task) then staging `REJECTED` (accounting) — partial-progress risk

## Money spine (recent train evidence — TDPQA-72 / GAP-078)
1. Inbound insurance staging (`death_foreclosure_insurance_staging_details`)
2. Force-bill path: dedicated `DFC_PRTL_BILL` labd (not EMI hijack); CRN = accountId + valueDate + **deathForeclosureDetailsId** (`935c52743`)
3. Appropriation / RSCH_DEATH_FORECLOSURE; last-child vs non-last amount rules differ (Obs2 last-child amount==principal fail-closed; non-last product-open GAP-079)
4. Parent Accrued≤Original reconcile (Obs3); webapp summary/statement asserts when in scope

## Open / parked
- **GAP-074** INT-180 last-child parent INT/DPI under-settlement (parked branch)
- **GAP-079** non-last amount≠principal (product)
- **GAP-080** parent/member future INT ₹1 (product)

## Tables
`death_foreclosure_details`, `death_foreclosure_insurance_staging_details`, `loan_account`, `loan_due_details`, `loan_account_billing_details`, `loan_account_payments_details`, `transaction_master`

## See also
- `cursor-bundle/brain/runbooks/sdcp-10199-group-parent-last-child-dfc.md`
- `system_brain/edge_cases/death_foreclosure_insurance_pending_fr_partial_progress_blocks_batch.md`
- Registry: `dcf.group_parent_last_child_e2e`, `dcf.non_last_rsch_amount_eq_principal`
