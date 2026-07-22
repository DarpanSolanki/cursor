<!-- Relocated verbatim from .cursor/rules/accounting.mdc / accounting-module-knowledge.mdc. Edit these skill topic files; thin accounting.mdc only routes here. -->

## Transaction types and sub-types

| Type | Sub-type | Source | What it posts | When |
|------|----------|--------|---------------|------|
| LOAN_DISBURSEMENT | CASH, CASA, ACCOUNT_TRANSFER_NEFT | loans_orc.xml, BookChildLoanProcessor | Principal, upfront interest | Real-time disbursement |
| LOAN_REPAYMENT | CASH, UPI, NET_BANKING, EXCESS_AMT | loans_orc.xml, mfi_orc.xml | PRIN, INT, PINT, FEE, excess | Real-time repayment |
| LOAN_PREPAYMENT | CASH | loans_orc.xml | PRIN, INT, POS, BPI, CBC | Foreclosure |
| LOAN_PART-PREPAYMENT | CASH, instrumentType | PopulateAdditionalAmountForPartPrepaymentProcessor | PRIN, INT, charges | Part prepayment |
| BILLING | NORMAL_BILLING | LoanAccountBillingService | PRIN + INT per installment | EOD nightly |
| INTEREST | NORMAL_ACCRUAL | InterestAccrualBookingService | Interest accrual | EOD / forceful in DCF |
| INTEREST | NPA_ACCRUAL, NPA_ACCRUAL_BOOKING | InterestAccrualBookingService | NPA interest | EOD for NPA loans |
| DEATH_FORECLOSURE | DEFAULT | DeathForeclosureInsuranceWriter | PRIN, INT, BPI, POS, excess, losses | DCF batch |
| RSCH_DEATH_FORECLOSURE | DEFAULT | DeathForeclosureInsuranceWriter | Parent loan part-prepayment | DCF batch (parent) |
| AUTO_CLOSURE | LOAN_ACCOUNT | LoanAccountClosureService | Closure amounts | EOD auto-closure |
| REGULAR_TO_NPA / NPA_TO_REGULAR | INT_INCOME | AssetClassification processors | NPA movement | NPA batch |
| EXCESS_AMT_REFUND | LOAN_ACCOUNT, INCOME_GL | loans_orc.xml | Excess refund | Real-time |
| LOAN_DISB_CNCL | CASH | loans_orc.xml | Disbursement reversal | Cancellation |
| LOAN_WRITE_OFF | FINAL_WRITE_OFF | loans_orc.xml | Write-off | Real-time |
| LOAN_REBOOKING | INTEREST_ADJUSTMENT | ExecuteLoanAccountRebookingProcessor | Interest adjustment | Rebooking |
| ACCR_PROVISIONING | LOANS | LoanProvisioningPostingService | Provisioning | EOD |
| MANUAL_JOURNAL_POSTING | GL | product_transaction_orc.xml | Manual JE | Real-time |

