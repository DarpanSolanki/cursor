# 04 · The journey of a rupee

> Track ₹1 from disbursement-bank → customer's loan → repayment → bank settlement → GL closure. Every GL hit, every Kafka event, every table touch, in order.

This page is the cross-service "money flow" — assumes you've read [`../accounting/08-gl-posting-engine.md`](../accounting/08-gl-posting-engine.md) for the GL engine internals.

---

## Stage 1 — Loan booked, money goes out

**Trigger:** LOS publishes `disburseLoan|<json>|disburseLoan{productId}_{externalRefNumber}` to Kafka topic `disburse_loan_api_<tenant>`.

```
LOS                                   Accounting (LMS)                            Bank
─────────────────────────────────     ────────────────────────────────────────    ────────────
PrepareDisburseLoanAPIRequestService
DisburseLoanAPIUtil.publish ─Kafka──▶ LmsMessageBrokerConsumer.processConsumerRecord
                                       getDisburseSkipReason → NONE
                                       NovopayCacheClient.set("dl"+key, "true")  ← Redis ACCOUNTING (DB 5)
                                       executeServiceOrchestration("disburseLoan")
                                          │
                                          ├─ Stage DEFAULT  → loan_account row INSERT (status=APPROVED)
                                          ├─ Stage LAN_CREATED → generateRepaymentSchedule, populate due
                                          ├─ Stage LOAN_BOOKED → bank NEFT call ────────────────────────▶ NEFT request
                                          │                                                            ◄ NEFT response
                                          ├─ Stage NEFT_STAGE_1_PENDING (waiting)
                                          ├─ Stage NEFT_STAGE_1_SUCCESS (callback received)
                                          ├─ Stage NEFT_STAGE_2_PENDING / NEFT_STAGE_2_SUCCESS
                                          ├─ Stage PARENT_SUCCESS:
                                          │     postTransaction (txn_catalogue=LOAN_DISB_PRIN)
                                          │     ┌───────────────────────────────────────────┐
                                          │     │  DR  internal_account(BANK_DISB_AC)  ₹X   │  GL e.g. 110102
                                          │     │  CR  internal_account(LOAN_PRIN_AC)  ₹X   │  GL e.g. 230101
                                          │     └───────────────────────────────────────────┘
                                          │     loan_status = ACTIVE
                                          │     CreateClmtLoanAccountEventsProcessor enqueues
                                          │           CLB row in loan_account_events_queue
                                          │
                                          └─ sendResultMessageToKafka (success) ─Kafka─────────────────▶  los_lms_disbursement_sync
                                              → cleanupCacheKeys (delete dl+key)                          (LOS receives)
```

For SHG/JLG, the `loan_account_events_queue` row holds the per-child JSON. Next run of `childLoanEventProcessingBatchJob`:

```
batch service ─HTTP────────────────▶ accounting:childLoanEventProcessingBatchJob
                                       ChildLoanEventsProcessingProcessor
                                         ├ pulls event_status='P' rows
                                         ├ for CLB: invokes childLoanDisbursement once with full event_array
                                         │   bookChildLoanProcessor → INSERT each child loan_account
                                         │   GroupLoanUtility.getFinalAmountListUsingCarryOver splits parent EMI
                                         │   per-child GL postings via postTransaction (gl_code = "CG"+code)
                                         └ marks CLB row event_status='C'
```

GL summary so far:

| Side | Account | GL code | Notes |
|---|---|---|---|
| DR | BANK_DISB_AC | 110102 | parent only |
| CR | LOAN_PRIN_AC | 230101 | parent only |
| (children) | "CG" prefix on both legs | CG110102 / CG230101 | per child fraction |

Per-customer side: `transaction_details` rows for the loan; `loan_due_details` for each future installment.

---

## Stage 2 — Time passes, interest accrues

**Trigger:** `runEODJobs` schedule fires (typically 21:00 IST) via batch service.

```
batch service ─HTTP─▶ accounting:runEODJobs (orchestration aggregator)
                       fans out (sequential per-step Requests):
                       ├─ loanAccountBillingJob          (today's due records → loan_account_billing_details)
                       ├─ interestAccrualCalculation     (computes today's accrual per loan)
                       │   batchnew/interest/interestaccrualcalculation/* — partitioned 10-thread Spring Batch
                       │   InterestAccrualCalService picks calculator: flat or reducing-balance
                       │   UPSERT interest_accrual_details (loan_account_id, accrual_date)
                       ├─ interestAccrualPosting         (post to GL)
                       │   For each accrued row, postTransaction (txn_catalogue=INT_ACCRUAL_BOOK)
                       │     DR  INT_RECEIVABLE_AC  ₹daily-interest
                       │     CR  INT_INCOME_AC      ₹daily-interest
                       ├─ penalInterestAccrualCalculation / penalInterestAccrualBooking (DPD-based)
                       ├─ loanAccountDpdCalcJob          (refreshes loan_account.past_due_days)
                       ├─ loanAccountAssetCriteriaJob    (asset_criteria_slabs_id by DPD bucket)
                       ├─ loanAccountAssetClassificationJob (final NPA tag)
                       ├─ updateLoanAccountDerivedFieldsJob (denorm for reporting)
                       ├─ trialBalanceCalculation        (trial_balance daily snapshot)
                       ├─ trialBalanceZeroisationJob     (closing → next-day open)
                       ├─ generateTBZeroisationReport
                       ├─ extractCasaBalanceFor180/182ProductCode
                       └─ generatePostEODReports         (kicks reporting service)
                                                          │
                                       trustt-platform-reporting:generateReport ─DMS upload─▶ S3/FS
                                                                                  ─ES audit─▶ Elasticsearch
```

Per day, the GL gains hundreds/thousands of small interest receivable / income pairs.

---

## Stage 3 — Customer pays an EMI

**Trigger:** webapp → gateway → accounting `loanRepayment` (sync), or payments service `collectionLoanRepayment` (sync HTTP from LCS), or NACH presentation success.

```
webapp / payments / NACH callback ─HTTP─▶ accounting:loanRepayment (mfi_orc.xml)
                                            ├ accounting_getUserDetails / getUseCaseDetails
                                            ├ loanRepayment_getLoanAccountDetails (self)
                                            ├ checkEligibleForRepaymentAppropriationProcessor
                                            ├ if maker_checker_enabled=1: loanRepayment_submitApplication ─▶ approval
                                            ├ RepaymentApproppriationProcessor:
                                            │    look up loan_product_asset_criteria (4 component slots + liquidationOrder)
                                            │    sort loan_due_details (by date, by component, or hybrid)
                                            │    walk + deduct → fills principal_amount, interest_amount,
                                            │       penalty_amount, fee_amount, excess_amount, suspense_amount
                                            ├ updateLoanDueDetailsProcessor   (paid_amount += current)
                                            ├ updateLoanInstallmentDetailsProcessor
                                            ├ updateLoanAccountForExcessAmountProcessor
                                            └ <API id="postTransaction"> (txn_catalogue=LOAN_REPAYMENT)
                                                  Multiple legs (one per component, depending on rules):
                                                  DR  CUSTOMER_AC / BANK_RECV_AC   ₹total
                                                  CR  LOAN_PRIN_AC   ₹principal
                                                  CR  INT_INCOME_AC  ₹interest
                                                  CR  PENAL_INC_AC   ₹penalty
                                                  CR  FEE_INCOME_AC  ₹fee
                                            ├ createLoanAccountPaymentsDetailsProcessor (audit + excess pool)
                                            ├ checkNPAReverseMovementRequiredProcessor   (clear NPA if eligible)
                                            └ checkAccountAutoClosureEligibilityProcessor (CLOSE if loan paid up)
                                                  if eligible:
                                                    populateLoanAutoClosureReqProcessor
                                                    loanAccountDpdCalcProcessor (recompute final DPD)
                                                    loanAccountAssetCriteriaProcessor + loanAccountAssetClassificationProcessor
                                                    loanAccountAutoClosureProcessor → loan_status = CLOSED
                                                    createLoanAccountClosureDetailsProcessor
```

**For child-loan repayment** (SHG/JLG), the parent flow may queue a `REP` event for siblings, replayed by `childLoanEventProcessingBatchJob` → `childLoanRepayment` Request per child.

---

## Stage 4 — Foreclosure / closure

`loanForeclosure` (or `childLoanForeclosure` → `individualChildLoanForeclosure` per child) does:

```
1. validate eligibility (no inactive status)
2. createPrepaymentDetails + createPrepaymentChargeDetails (foreclosure charge + tax)
3. checkLoanAccountInterestAccrualBookingProcessor (book any pending accrual)
4. bookingNonPostedPenalProcessor
5. updateDueDetailsForPrepayment + populateAdditional* (build the DR/CR amounts)
6. prepaymentApproppriationProcessor (allocates the prepayment amount)
7. <API id="postTransaction"> (txn_catalogue=LOAN_PREPAYMENT or FORECLOSE)
       DR  CUSTOMER_AC                ₹full outstanding
       CR  LOAN_PRIN_AC               ₹principal due
       CR  INT_RECEIVABLE_AC          ₹interest due
       CR  FORECLOSURE_CHRG_INCOME_AC ₹fc charge
8. updateLoanAccountStatusProcessor → loan_status = FORECLOSED
9. loanAccountAutoClosureProcessor → loan_status = CLOSED
10. createLoanAccountClosureDetailsProcessor
11. notification + delete maker-checker draft
```

If auto-closure fails, `loanAccountClosure` batch job picks it up later (from `FORECLOSED` → `CLOSED`).

---

## Stage 5 — Trial balance, zero out

End of day:

- `trialBalanceCalculation` snapshots GL balances for the day → `trial_balance` (one row per GL, per business_date).
- `trialBalanceZeroisationJob` carries closing → next-day opening balance.
- `generateTBZeroisationReport` produces the human-readable summary.

A non-zero net on any GL after zeroisation = a hard accounting bug. See [`../runbooks/trial-balance-imbalance.md`](../runbooks/trial-balance-imbalance.md).

---

## Where each "rupee state" lives

| State | Table |
|---|---|
| Loan principal outstanding | `loan_account` (denormalised on `loan_account_derived_fields.outstanding`) |
| Per-component pending | `loan_due_details` (`due_amount`, `paid_amount`, `waived_amount`) |
| Per-installment | `loan_installment_details` |
| Daily accrued interest | `interest_accrual_details` |
| Daily accrued penal | `penal_interest_accrual_details` |
| Each GL transaction | `transaction_master` + `transaction_partition_details` (DR/CR) |
| Per-account ledger | `transaction_details` + `account_balance` |
| GL daily totals | `trial_balance` |
| Historic snapshots | `loan_account_derived_fields` (daily) + `_monthly` |
| Provisioning | `loan_provisioning_details` |
| Closure record | `loan_account_closure_details` |
| Repayment audit | `loan_account_payments_details` |

---

## Cross-references

- GL engine internals: [`../accounting/08-gl-posting-engine.md`](../accounting/08-gl-posting-engine.md)
- Lifecycle states: [`../accounting/07-loan-account-lifecycle.md`](../accounting/07-loan-account-lifecycle.md)
- SHG/JLG fan-out: [`../accounting/06-shg-jlg-group-loans.md`](../accounting/06-shg-jlg-group-loans.md)
- Repayment appropriation algorithm: [`../accounting/08-gl-posting-engine.md`](../accounting/08-gl-posting-engine.md) §7
- Older deep narrative: [`../engines/disbursement-engine.md`](../engines/disbursement-engine.md), [`../engines/repayment-engine.md`](../engines/repayment-engine.md), [`../engines/posting-engine.md`](../engines/posting-engine.md)
