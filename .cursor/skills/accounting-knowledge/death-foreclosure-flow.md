<!-- Relocated verbatim from .cursor/rules/accounting.mdc / accounting-module-knowledge.mdc. Edit these skill topic files; thin accounting.mdc only routes here. -->

## Death foreclosure flow (end-to-end)

1. Stage processors (STAGE_1→STAGE_6) → freeze loan, collect docs, compute outstanding
   - Claim-form calculation (e.g. `GenerateDeathClaimFormPreProcessor`) and insurance claim staging (stage-5 in `ProcessDeathForeclosureAsPerStageProcessor.populateDeathForeclosureInsuranceStagingDetails()`):
     - unconditionally call `loanAccountBillingJob` before `GetAmountDetailsForDeathForeclosureService.fetchOutStandingLoanBalanceAsPerDate(...)`
     - uses `function_sub_code=DEFAULT` and `job_time = date_of_death` (so billing paid/waived state is aligned with claim as-on date)
     - ensures `user_id` is set (defaults to `SYSTEM` if missing)
2. Outbound file to insurer (OutboundDeathForeclosureInsuranceJobProcessor)
3. Inbound approval (InboundDeathForeclosureInsuranceJobProcessor)
4. DeathForeclosureInsuranceWriter.calculateAmountsForTransaction():
   - syncs installment billing up to reporting date by calling `loanAccountBillingJob` for the same LAN (`function_sub_code=DEFAULT`, `job_time=dateOfReporting`) before DCF component calculations (ensures `user_id` is set; defaults to `SYSTEM` if missing)
   - GetAmountDetailsForDeathForeclosureService.fetchOutStandingLoanBalanceAsPerDate()
   - calculateLossInterestWaived() → LOSSES_INT_WAIVED, LOSSES_INT_WAIVED_AIR
   - populateAdditionalAmountDetails for all GL codes
   - calculateTotalTransactionAmount()
   - appropriateDeathForeclosure()
   - checkLoanAccountInterestAccrualBookingProcessor → separate INTEREST/NORMAL_ACCRUAL txn
   - postTransaction(DEATH_FORECLOSURE)
   - NPA calc, closure, child loan handling

