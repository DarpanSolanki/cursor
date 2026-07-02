# Child Loan Foreclosure with Principal Waiver — Flow Map and Failure Modes

> SHG/JLG child loan foreclosure (group loan, product `LOAN_SHG`) when the customer pays only part of the outstanding in cash and the remainder is waived. The flow runs an **inline** posting on the child PLUS a follow-up **inline** call to the parent's part-prepayment reschedule. Both legs go through the same `loanPrepayment` Request with `function_code=APPROVE` / `do_prepayment=true`. The two postings share the same `ExecutionContext`, which is the root of several of the bugs documented below.
>
> First written from the SDCP-10080 RCA (LAN 7000035818 / 7000042524 on QA2 `mfi_integration_v3.3.3`).

---

## 1. End-to-end flow

```
Operator submits Foreclosure Final Submission task
  ▼ (task service → accounting)
Request "loanPrepayment" with do_prepayment=true, is_child_loan=true
  ─ child_account_number = 7000042524
  ─ parent_account_number = 7000035818
  ─ total_foreclosure_amount  = 8     (cash to be paid)
  ─ balance_principal_due_amount = 761 (full child outstanding to settle)
  ─ paid_foreclosure_fee = 0
  ─ payment_mode = CASH
  ─ receipt_number = 614200000023264
  ▼
[loans_orc.xml :: <Request name="loanPrepayment"> :: <Control do_prepayment=true>]
deploy/application/orchestration/loans_orc.xml:2004
  │
  ├─ checkLoanAccountInterestAccrualBookingProcessor
  ├─ bookingNonPostedPenalProcessor (job_time=foreclosure_date)
  ├─ updateDueDetailsForPrepaymentProcessor       ◄── (1) creates child FEE ldd row,
  │                                                    writes child waiver rows + waiver_details
  ├─ populateAdditionalAmountAndAccountDetailsForForeclosureProcessor
  ├─ getPrepaymentDetailsProcessor (task_status=APPROVED)
  ├─ populateAmountComponentsForAppropriationProcessor
  │     sets principal_amount = PRIN_OVERDUE + balance_principal_amount_to_be_paid (=8)
  ├─ prepaymentApproppriationProcessor              ◄── (2) sets EC principal/interest/fee/penal
  │                                                    from cash-only appropriation; mutates
  │                                                    LoanDueDetailsEntity in-memory ONLY
  │
  ├─ <Control is_child_loan=true>
  │    ├─ getPrepaymentChargeDetailsObjectProcessor   (populates charges_details list)
  │    └─ dummyProcessor force_gst_posting=true
  │
  ├─ <API postTransaction>                        ◄── (3) TM 2002 on child (catalogue 117 = LOAN_PREPAYMENT)
  │     transaction_type = LOAN_PREPAYMENT
  │     transaction_sub_type = CASH
  │     amount = total_foreclosure_amount (=8)
  │     client_reference_number = receipt_number (=614200000023264)
  │     ┌── 17-rule expansion (see §3) using the EC reference codes:
  │     │   POS=8, LOSSES_PRN_WAIVED_UB=753, BPI_AMT=0, LOSSES_INT_WAIVED_AIR=2, TRMN_AMT=8
  │     └── produces 5 transaction_details legs (cash DR 8, waiver DR 753, …, child LOAN_ACCOUNT CR 761)
  │
  ├─ prePaymentGLCBSIntegrationProcessor          (HDFC CBS GL push; off-platform)
  ├─ updateLoanDueDetailsProcessor                ◄── (4) marks child ldd rows paid_amount from appropriation
  ├─ updateLoanInstallmentDetailsProcessor (mode=prepayment)
  ├─ createLoanAccountPaymentsDetailsProcessor    ◄── (5) child row 801: amount=8, principal=8
  │     repayment_amount = total_foreclosure_amount (=8)
  │     principal_amount = "principal_amount" from EC (=8, cash-only after appropriation)
  ├─ loanAccountDpdCalcProcessor / loanAccountAssetCriteria / classification
  ├─ updateLoanAccountStatusProcessor loan_status=CLOSED
  ├─ updateLoanStatusForSHGProcessor (closes the child in actor side)
  ├─ pushLoanAccountClosureDetailsProcessor
  ├─ updateExcessAmountForPrepaymentProcessor
  ├─ updatePrepaymentTaskDetailsProcessor task_status=APPROVED prepayment_status=APPROVED
  ├─ deleteDraftProcessor
  ├─ updateCollectionForClosureProcessor
  ├─ createLoanDueDetailsLoanAccountPaymentsDetailsProcessor
  ├─ createLoanAccountClosureDetailsProcessor
  │
  ├─ <Control is_child_loan=true>
  │    └─ callInternalOrchestrationProcessor (api_name=parentLoanAccountPartPrepayment)
  │         IParams:
  │           loan_account_number      = parent_account_number (=7000035818)
  │           parent_loan_account_entity → loan_account_entity (re-bind)
  │           gross_amount   = total_foreclosure_amount       (=8)   ◄── cash from customer
  │           net_amount     = balance_principal_due_amount   (=761) ◄── parent share to settle
  │           charges        = paid_foreclosure_fee           (=0)
  │           bpi_amount     = bpi_amount_paid_amount         (=0)
  │           excess_amount  = paid_excess_amount             (=0)
  │           receipt_number = ${unique_reference_no}_${account_number} (=614200000023264_7000042524)
  │           rescheduling_effective_date = foreclosure_date
  │           part_prepayment_impact = REDUCE_EMI
  │           broken_period_interest_handling = UPFRONT
  │           instrument_type = payment_mode (=CASH)
  │           paid_by, depositor_name, notes pass through
  │
  │     ▼  CallInternalOrchestrationProcessor.process() copies the ENTIRE parent EC
  │        (shared + local maps) into a fresh ExecutionContext for the callee. That includes:
  │        additional_amount_details, POS, LOSSES_PRN_WAIVED_UB, LOSSES_INT_WAIVED_AIR,
  │        TRMN_AMT, account_details, prepayment_details, loan_due_details_list,
  │        and the child LoanAccountEntity (until rebound).
  │
  │     [group_mfi_orc.xml :: <Request name="parentLoanAccountPartPrepayment">]
  │     deploy/application/orchestration/group_mfi_orc.xml:435
  │       ├─ populateUserDetails / setCommonAttributesProcessor / fetchBulkUniqueMasterData
  │       ├─ fetchSuperDataForForeclosureProcessor
  │       ├─ createOrUpdateLoanAccountPartPrepaymentProcessor    ◄── (6) parent part_prepayment_details
  │       │       (gross=8, net=761, charges=0, bpi=0; status PENDING)
  │       ├─ getOfficeIdFromAccountNumberProcessor (transaction_type=RSCH_LOAN_PREPAYMENT)
  │       ├─ populateLoanAccountPartPrepaymentDetailsProcessor   ◄── (7) reloads parent
  │       │       part_prepayment row → puts gross_amount, net_amount, charges, bpi_amount
  │       │       back into EC (these are the durable values for the rest of the flow).
  │       ├─ populateAdditionalTaxAmountAndAccountDetailsFromChargeDetails
  │       ├─ bookingNonPostedPenalProcessor (job_time=rescheduling_effective_date)
  │       ├─ registerLoanAccountRescheduleEventProcessor          (creates loan_account_reschedule_details row)
  │       ├─ loanAccountRescheduleBatchProcessor
  │       │     └─ PartPrepaymentLoanAccountRescheduleService.execute (qualifier "partprepayment_loan_account_rescheduler")
  │       │           └─ saveEntities → realModePostTransaction=true →
  │       │              PostPartPrepaymentTransactionProcessor.postPartPrepaymentTransaction
  │       │                ├─ populateAdditionalAmountForPartPrepaymentProcessor
  │       │                │     ├─ populateTransactionTypeSubtype (transaction_type stays as RSCH_LOAN_PREPAYMENT)
  │       │                │     ├─ checkEligibleForRepaymentAppropriationProcessor
  │       │                │     ├─ if (do_repayment_appropriation == "true") repaymentApproppriationProcessor
  │       │                │     │      (runs PARENT appropriation; for a current/not-overdue parent
  │       │                │     │       this is a no-op or 0)
  │       │                │     ├─ processExcessAmount (parent has 0 excess)
  │       │                │     ├─ papulatePartPrepaymentAdditionalAmountFields (PRIN_AMT=761, INT_AMT=0,
  │               │                │     │      PART_PREPAYMENT=0)  ← INTENDED parent legs.
  │               │                │     │      BUT: child's POS, LOSSES_PRN_WAIVED_UB, LOSSES_INT_WAIVED_AIR,
  │               │                │     │      TRMN_AMT, additional_amount_details are STILL in EC.
  │               │                │     ├─ papulateTransactionAccountDetails (LOAN_ACCOUNT → parent 7000035818)
  │               │                │     └─ amount = grossAmount (=8) put into EC
  │               │                ├─ <postTransaction internal call>           ◄── (8) TM 2003 on parent
  │               │                │     catalogue 209 = "Child Loan Foreclosure Parent Reschedule"
  │               │                │     transaction_type = RSCH_LOAN_PREPAYMENT
  │               │                │     amount = 8 (grossAmount, customer cash)
  │               │                │     Posting expansion uses the INHERITED reference codes plus
  │               │                │     the freshly added PRIN_AMT=761.
  │               │                │     Result: 5 transaction_details legs IDENTICAL to TM 2002 but
  │               │                │     with the parent's LOAN_ACCOUNT GL (is_child_gl_code=False).
  │               │                ├─ saveAndUpdateLoanEntities
  │               │                │     ├─ generateRepaymentScheduleProcessor.createPartPrepaymentDueDetailsEntities
  │               │                │     │     ▶ inserts parent installment row (lid=schedule 2,
  │               │                │     │       installment_date=foreclosure_date, is_settled=true,
  │               │                │     │       is_part_prepayment_entry=true) and one PRIN ldd
  │               │                │     │       (id=1703) due=761, paid=761 (then later mutated to
  │               │                │     │       paid=8, waived=753 by the appropriation/waiver
  │               │                │     │       merge — see §4 BUG #3).
  │               │                │     ├─ createAndLogicalDeletionOfLatestInstallmentAndDueDetailsEntities
  │               │                │     │     ▶ logically deletes (is_deleted=True) the parent's old
  │               │                │     │       schedule-1 future installments AND their ldd rows,
  │               │                │     │       creates new schedule-2 installments + ldd rows with
  │               │                │     │       the principal reduced by the foreclosed share.
  │               │                │     └─ saveLoanRepaymentScheduleAndInstallmentANDLoanDueDetailsEntities
  │               │                │           creates the rest of the new schedule.
  │               │                ├─ updateLoanDueDetailsProcessor (if totalDues>0; not in this case)
  │               │                ├─ interestAccrualBookingProcessor (if bpi>0; not in this case)
  │               │                └─ saveLoanAccountPaymentsDetails  ◄── (9) parent row 802
  │               │                    repayment_amount = grossAmount (=8) BUT (see §4 BUG #2)
  │               │                    DB shows amount=761, principal_amount=761 — driven by the
  │               │                    overrides from the PRIN_AMT=761 / NET_AMOUNT=761 that
  │               │                    `papulatePartPrepaymentAdditionalAmountFields` set.
  │               └─ updateLoanAccountPartPrepaymentTaskProcessor (prepayment_status=DEPOSITED)
  │
  ├─ childLoanForeclosureEventGenerationProcessor   (writes a CLF event to loan_account_events_queue)
  └─ prepaymentSMSNotification
```

Key timestamp evidence on QA2 (LAN 7000042524 / 7000035818):

| When | Where | What |
|---|---|---|
| 2026-05-22 12:16:00.064 | `value_date` stamp on parent rows | parent ldd 1703, 1704..1747; parent payment_details id=802; parent installment_details rows 1301..1323 |
| 2026-05-22 12:39:29.45-.62 | child waiver writes | 23 `waiver_details` rows + 22 `waiver__loan_due_details` rows + child ldd `processForeclosureFee` writes row 1702 |
| 2026-05-22 12:39:30.468 | TM 2002 (child) | catalogue 117 LOAN_PREPAYMENT, amount=8 |
| 2026-05-22 12:39:31.828 | child payment row 801 | amount=8 |
| 2026-05-22 12:39:34.309 | TM 2003 (parent) | catalogue 209 RSCH_LOAN_PREPAYMENT, amount=8 — **5 customer-side legs duplicated** |

The 12:16 stamp on parent rows is `value_date` / `rescheduling_effective_date` (foreclosure_date midnight + processing-second offset), *not* the wall-clock insertion time — it sorts BEFORE child rows in the DB but the actual write order is exactly as listed.

---

## 2. Tables touched

| Table | Owner write site | What gets written for child foreclosure-with-waiver |
|---|---|---|
| `loan_due_details` (child) | `UpdateDueDetailsForPrepaymentProcessor` (lines 56-85), `processPendingInstallmentObject`, `processBalancePrincipalObject`, `processBPI`, `processForeclosureFee` | (a) future PRIN ldd rows get `waived_amount=due_amount` (rows 1345..1681 in the LAN 7000042524 trace); (b) `processForeclosureFee` always inserts a new FEE ldd row even when chargeAmount=0 (row 1702 in trace, base_amount=761, due=paid=waived=0) — see §4 BUG #4. |
| `loan_due_details` (parent) | `GenerateRepaymentScheduleProcessor.createPartPrepaymentDueDetailsEntities` (line 193) + `createAndLogicalDeletionOfLatestInstallmentAndDueDetailsEntities` (line 211) | New "today" PRIN row id=1703 with due_amount=761 (later mutated to paid=8, waived=753); old future ldd `is_deleted=True`; new future ldd inserted under schedule_number=N+1. |
| `loan_installment_details` (parent) | same | New foreclosure-date "settled" row (`is_part_prepayment_entry=True`, `is_settled=True`, schedule_number=N+1); old future installments `is_deleted=True`; new future installments inserted. |
| `waiver_details` | `UpdateDueDetailsForPrepaymentProcessor.saveWaiverDetails` (line 258) | 23 rows for CHILD only. **0 rows for parent** (gap — see §4 BUG #5). |
| `waiver__loan_due_details` | `UpdateDueDetailsForPrepaymentProcessor.saveWaiverLoanDueDetails` (line 281) | 22 rows for child (one per waived future installment). **1 row for parent ldd 1703** — origin unclear in code; the most likely path is the same `updateLoanDueDetailsProcessor` running again in the parent reschedule with the inherited EC, but `waiver_details` is NOT updated in parallel → inconsistency. |
| `loan_account_payments_details` (child) | `CreateLoanAccountPaymentsDetailsProcessor` (loans_orc.xml:2057) | `amount = total_foreclosure_amount` (cash only), `principal_amount = "principal_amount"` from EC (cash-only appropriation result). Child row 801: amount=8, principal=8. |
| `loan_account_payments_details` (parent) | `PostPartPrepaymentTransactionProcessor.saveLoanAccountPaymentsDetails` (line 290) | `repayment_amount = grossAmount` (=8) per code, but DB shows amount=761 because the EC `principal_amount` (line 308: `netAmount.add(overDuePrincipal)`) is what ends up driving the row; the principal_amount override in EC by `papulatePartPrepaymentAdditionalAmountFields(line 151)` is also a factor. |
| `loan_account_part_prepayment_details` (parent) | `CreateOrUpdateLoanAccountPartPrepaymentProcessor` (line 99) | One row per parent reschedule. For LAN 7000035818: gross=8, net=761, charges=0, bpi=0, status=DEPOSITED. |
| `loan_account_reschedule_details` (parent) | `RegisterLoanAccountRescheduleEventProcessor` | One row per reschedule, identifier_type=PARTPREPAYMENT, batch_status=PENDING→SUCCESS. |
| `loan_account_closure_details` (child) | `createLoanAccountClosureDetailsProcessor` (loans_orc.xml:2098) | One row identifier=FORECLOSURE, identifier_value=prepayment_details_id. |
| `transaction_master`, `transaction_details` (child) | `postTransaction` API call (loans_orc.xml:2026) | One TM with catalogue 117 + 5 legs (see §3). |
| `transaction_master`, `transaction_details` (parent) | `postTransaction` API call via `PostPartPrepaymentTransactionProcessor.postPartPrepaymentTransaction:123` | One TM with catalogue 209 + 5 legs (see §3) — currently **identical legs** as the child posting (BUG #1). |
| `loan_account_events_queue` | `childLoanForeclosureEventGenerationProcessor` (loans_orc.xml:2137) | One CLF event for the foreclosed child — picked up by the child-event-batch downstream. |

---

## 3. Accounting rules — catalogue 117 (`LOAN_PREPAYMENT`) vs catalogue 209 (`RSCH_LOAN_PREPAYMENT`)

Verified from `mfi_accounting.transaction_accounting_rule` on QA2:

```
ref_code                       debit_placeholder    credit_placeholder    source_amount
ADV_BPI_AMT                    EXCESS_ACCT          INT_ACC_NOT_DUE       ADV_BPI_AMT
ADV_POS                        EXCESS_ACCT          LOAN_ACCOUNT          ADV_POS
ADV_FORECLOSURE_AMT            EXCESS_ACCT          FRCLSR_CHRG           ADV_FORECLOSURE_AMT
TRMN_AMT                       DUE_TO_FC_B          TRMN_SUSP             amount
INT_AMT                        TRMN_SUSP            BILLED_INTEREST       INT_AMT
PRIN_AMT                       TRMN_SUSP            BILLED_PRINCIPAL      PRIN_AMT
BPI_AMT                        TRMN_SUSP            INT_ACC_NOT_DUE       BPI_AMT
POS                            TRMN_SUSP            LOAN_ACCOUNT          POS
FORCLSR_CHRG / FORECLOSURE_FEE TRMN_SUSP            FRCLSR_CHRG           FORECLOSURE_FEE_SRC_AMT
ROUND_UP_AMT                   DUE_TO_FC_B          ROUND_OFF             ROUND_UP_AMT
ROUND_DOWN_AMT                 ROUND_OFF            INT_ACC_NOT_DUE       ROUND_DOWN_AMT
LOSSES_INT_WAIVED_AIR          BILLED_INT_WAIVE     INT_ACC_NOT_DUE       LOSSES_INT_WAIVED_AIR
LOSSES_PRN_WAIVED_UB           PRIN_WAIVE_NPA       LOAN_ACCOUNT          LOSSES_PRN_WAIVED_UB
LOSSES_BILLED_INT_WAIVED       BILLED_INT_WAIVE     BILLED_INTEREST       LOSSES_BILLED_INT_WAIVED
LOSSES_BILLED_PRN_WAIVED_STD   PRIN_WAIVE_STD       BILLED_PRINCIPAL      LOSSES_BILLED_PRN_WAIVED_STD
LOSSES_BILLED_PRN_WAIVED_UB    PRIN_WAIVE_NPA       BILLED_PRINCIPAL      LOSSES_BILLED_PRN_WAIVED_UB
LOSSES_PRN_WAIVED_STD          PRIN_WAIVE_STD       LOAN_ACCOUNT          LOSSES_PRN_WAIVED_STD
```

Catalogue 209 has the **same 17 rules with the same reference codes, same debit/credit placeholders, and same source-amount mappings as catalogue 117**. The only structural difference is the `description` string (`"Child Loan Foreclosure Parent Reschedule"` vs `"LOAN PREPAYMENT"`).

Consequence: when the same `additional_amount_details` survive between the child and parent postings, both transactions produce the same set of legs — see BUG #1.

---

## 4. Bug inventory (SDCP-10080 + corollaries)

### BUG #1 — Duplicate customer-side GL legs on parent reschedule (TM 2003)

**Symptom.** For LAN 7000042524: TM 2002 (child, catalogue 117) and TM 2003 (parent, catalogue 209) each post the same 5 legs:

```
CR  INT_ACC_NOT_DUE  2          (BPI / waived AIR)
CR  LOAN_ACCOUNT     761        (POS 8 + LOSSES_PRN_WAIVED_UB 753 netted on child / parent GL)
DR  DUE_TO_FC_B      8          (cash account — TRMN_AMT)
DR  ROUND_OFF        2
DR  PRIN_WAIVE_NPA   753        (LOSSES_PRN_WAIVED_UB)
```

`DUE_TO_FC_B` is debited 8 twice (cash GL over-debited by 8). `PRIN_WAIVE_NPA` is debited 753 twice (waiver expense GL over-debited by 753). Each TM balances individually, so trial balance per-TM is clean — but per-GL across the two TMs, the system records the customer's 8 cash + 753 waiver TWICE.

**Why (proof-backed).**
1. `infra-navigation/src/main/java/in/novopay/infra/navigation/processor/CallInternalOrchestrationProcessor.java:46-58` builds the callee EC by `requestMap.putAll(executionContext.getSharedMap())` + `requestMap.putAll(executionContext.getLocalMap())`. Every reference-code key already set by the child posting (`POS`, `LOSSES_PRN_WAIVED_UB`, `LOSSES_INT_WAIVED_AIR`, `TRMN_AMT`, and the `additional_amount_details` list itself) is carried into the parent run.
2. `PostPartPrepaymentTransactionProcessor.populateAdditionalAmountForPartPrepaymentProcessor.process()` (PopulateAdditionalAmountForPartPrepaymentProcessor.java:97-130) ADDS to `additional_amount_details` (via `createAdditionalAmountFieldDetails:219`) but does NOT clear what was already there.
3. The catalogue-209 accounting rules are byte-identical to catalogue-117 (verified on QA2 — see §3). So the same reference codes resolve to the same legs.
4. The only differentiator is the `LOAN_ACCOUNT` placeholder, which resolves to the parent account number via `papulateTransactionAccountDetails(PopulateAdditionalAmountForPartPrepaymentProcessor.java:205)`. Hence the parent's LOAN_ACCOUNT leg is parent-side, but every other leg duplicates the child posting.

**Net GL impact for LAN 7000042524 across TM 2002 + TM 2003 (incorrect):**

| GL | DR | CR | Net |
|---|---:|---:|---:|
| `DUE_TO_FC_B` (cash) | 16 | 0 | DR 16 |
| `PRIN_WAIVE_NPA` (waiver expense) | 1 506 | 0 | DR 1 506 |
| `INT_ACC_NOT_DUE` (accrued int liability) | 0 | 4 | CR 4 |
| `ROUND_OFF` | 4 | 0 | DR 4 |
| `LOAN_ACCOUNT` (child 7000042524) | 0 | 761 | CR 761 |
| `LOAN_ACCOUNT` (parent 7000035818) | 0 | 761 | CR 761 |

The customer's true economic event is 8 rs cash + 753 rs waiver against the child's 761 outstanding. The system has recorded that twice over the customer-side legs. Both child and parent loans see a 761 reduction in their LOAN_ACCOUNT GL, but the parent leg should have been an intercompany settlement (DR Parent's LOAN_ACCOUNT / CR Child Loan Suspense or similar), not a duplicate of the customer-side legs.

### BUG #2 — Parent `loan_account_payments_details.amount` = 761 instead of 8

**Symptom.** DB row id=802 for parent has `amount=761, principal_amount=761`. The reporter's expected value was 8 (the cash component) or alternatively 761 if the convention is to record total settlement.

**Why.** `PostPartPrepaymentTransactionProcessor.saveLoanAccountPaymentsDetails:307` writes `repayment_amount = grossAmount` where `grossAmount = gross_amount` from the part_prepayment_details row (=8). But just before this, `papulatePartPrepaymentAdditionalAmountFields(PopulateAdditionalAmountForPartPrepaymentProcessor.java:148-161)` sets `PRIN_AMT = netAmount (=761)` in EC. The `CreateLoanAccountPaymentsDetailsProcessor.process:67-68` reads `principal_amount` from EC and writes it into the row. The `amount` field on the row is set from `repayment_amount`, which `papulatePartPrepaymentAdditionalAmountFields` overwrites at line 151 via `createAdditionalAmountFieldDetails` (puts `PRIN_AMT` value as local "PRIN_AMT" not "principal_amount") — but `saveLoanAccountPaymentsDetails:308` then writes `principal_amount = netAmount + overDuePrincipal = 761 + 0 = 761`, and the row's `amount` column is fed from a similar override at line 307 effectively coming out as 761 because of EC reuse from the child appropriation. This inconsistency between the operator-visible "deposit amount" and the row's `amount` is what the reporter flagged.

Today there is no single source-of-truth for which value `loan_account_payments_details.amount` should hold on the parent for a child-foreclosure-with-waiver:
- `gross_amount` (8) — customer cash → semantically matches the customer's deposit.
- `net_amount` (761) — parent's share of the closed child principal → semantically matches the GL leg posted on the parent.

Per the ticket, the expected value on the **child** row is 761 (total settlement). The child row 801 currently holds 8. This is the symmetric inconsistency.

### BUG #3 — Parent ldd 1703 mutation chain

**Symptom.** Parent ldd id=1703 ends up with `due_amount=761, paid_amount=8, waived_amount=753`.

**Why.** `GenerateRepaymentScheduleProcessor.createPartPrepaymentDueDetailsEntities:193-209` creates the row with `paid_amount = due_amount = 761` (via `updateSettledAmount:231-235`). Later in the parent reschedule flow, the EC's `LOSSES_PRN_WAIVED_UB=753` (inherited from the child) causes a waiver row to be created against this ldd (the `waiver__loan_due_details` id=101 entry) AND `paid_amount` to be reduced by the same 753 to keep `paid+waived = due` invariant.

If/when BUG #1 is fixed by clearing inherited reference codes (the cleanest fix), `waived_amount` will silently become 0 on parent ldd 1703 too — and the parent's outstanding will be "paid" with 761 rs of imaginary cash. So fix #1 cannot ship in isolation; the parent waiver propagation must be redesigned at the same time (see §5 fix plan).

### BUG #4 — Child FEE ldd row with all-zero amounts

**Symptom.** Child ldd 1702: `component_type=FEE, charge_code='' (empty), base_amount=761, due_amount=0, paid_amount=0, waived_amount=0`.

**Why.** `UpdateDueDetailsForPrepaymentProcessor.processForeclosureFee:233-256` builds and saves a new ldd row UNCONDITIONALLY whenever a `prepayment_charge_details` entry exists for `foreclosure_fee`. The trace shows `prepayment_charge_details` id=2 with `charge_amount=0, waived_amount=0, base_amount=761, charge_code=''`. No guard checks "skip if charge_amount=0 AND waived_amount=0".

`base_amount=761` is the prepayment principal-outstanding used to compute the (zero) fee, kept for audit. This row never participates in postings or settlement — it is essentially dead metadata, but it shows up in operator-side ldd queries as "an extra row".

### BUG #5 — `waiver_details` not written for the parent loan_account

**Symptom.** `waiver_details` has 23 rows for child 38807, 0 rows for parent 32601. But `waiver__loan_due_details` has 1 row for parent (id=101 → parent ldd 1703).

**Why.** `UpdateDueDetailsForPrepaymentProcessor.saveWaiverDetails:258-279` is only invoked from the child's `do_prepayment` branch (loans_orc.xml:2013 `updateDueDetailsForPrepaymentProcessor`). It writes both `waiver_details` AND `waiver__loan_due_details`. The parent's `waiver__loan_due_details` id=101 came in through a different path (likely the `updateLoanDueDetailsProcessor` running again under the parent reschedule with the inherited `LOSSES_PRN_WAIVED_UB=753` in EC). That path doesn't go through `saveWaiverDetails`, so the parent has a waiver-DTL row but no waiver header row.

This is invisible to GL but visible to any reporting / audit query that joins `waiver_details` to `loan_account` for "all waivers per LAN".

### BUG #6 — Parent's future ldd reduction is silent (no waiver record per installment)

**Symptom.** Parent's new schedule ldd rows 1704..1747 (active, `is_deleted=False`) have principal/interest values that are smaller than the old ldd rows by exactly the foreclosed child's share. No `waived_amount` on any of these rows. No `waiver_details` or `waiver__loan_due_details` row per future installment.

**Why.** This is by design of the part-prepayment reschedule (the foreclosed child's principal is treated as a prepayment that REDUCES the parent's outstanding, redrawing the schedule). However, 753 of that 761 reduction came from a waiver, not from cash — and that economic distinction is lost in the parent's per-installment schedule. The reporter's items 3 and 4 are about this: the parent should somehow record that 753 of the principal reduction came from a waiver, not a payment. Today the parent's ledger view will show "principal outstanding reduced by 761" with no link back to the child's waiver.

---

## 5. Fix plan

The five bugs fall in three layers. Fixing them independently breaks the others, so they must be planned together.

### 5a. Stop the EC leak (the structural fix)

Drop everything the child posting added to EC *before* calling `parentLoanAccountPartPrepayment`, so the parent posting computes its own reference codes from its own data.

- Add an explicit cleanup processor right before the `callInternalOrchestrationProcessor` for `is_child_loan=true` (loans_orc.xml:2111). It should remove from EC: `additional_amount_details` (list), `account_details` (list), and the reference-code keys: `POS`, `PRIN_AMT`, `INT_AMT`, `BPI_AMT`, `TRMN_AMT`, `FORCLSR_CHRG`, `CBC_AMT`, `ROUND_UP_AMT`, `ROUND_DOWN_AMT`, `LOSSES_PRN_WAIVED_UB`, `LOSSES_PRN_WAIVED_STD`, `LOSSES_BILLED_PRN_WAIVED_UB`, `LOSSES_BILLED_PRN_WAIVED_STD`, `LOSSES_BILLED_INT_WAIVED`, `LOSSES_INT_WAIVED_AIR`, `ADV_POS`, `ADV_BPI_AMT`, `ADV_INT_AMT`, `ADV_PRIN_AMT`, `ADV_FORECLOSURE_AMT`, `ADV_PART_PREPAYMENT`, plus `loan_due_details_payment_dto_map`, `loan_due_details_list`, `prepayment_details_id`, `prepayment_details`, `loan_account_entity`, `transaction_reference_number`, `overall_transaction_details`, `account_level_transaction_details`.
- Sibling option: change `CallInternalOrchestrationProcessor.process` (infra-lib) to NOT inherit shared+local maps by default and instead require the caller to whitelist what crosses the boundary. This is a broader infra change with cross-flow impact.

### 5b. Define the parent leg's intended postings

Catalogue 209 is named "Child Loan Foreclosure Parent Reschedule" but its rules are a copy of LOAN_PREPAYMENT. That's the underlying schema problem.

- Decide the correct accounting model for the parent leg. For a child-foreclosure-with-waiver where the customer pays 8 cash + 753 waiver and the child's principal of 761 is closed, the parent's GL should typically have:
  - DR Parent `LOAN_ACCOUNT` for the parent's share of the closed principal (offsetting the parent's outstanding).
  - CR a Child Loan Suspense / Intercompany account by the same amount.
  - No second customer-side cash leg, no second waiver expense leg.
- Replace the catalogue-209 rules with this intercompany set (config-only change in `transaction_accounting_rule` for `transaction_catalogue_id=209`).
- Verify by re-running the same scenario and checking that the cash GL net (across TM 2002 + TM 2003) is 8, the waiver expense GL net is 753, and the parent's LOAN_ACCOUNT net is 761 (settlement-side).

This is a config change, deploy-together with 5a.

### 5c. Decide the parent loan_account_payments_details semantics

Pick one of:
- **(A)** Parent row.amount = 8 (cash, matches GL cash leg). Useful for reconciling with the bank file.
- **(B)** Parent row.amount = 761 (total settlement, matches the parent's outstanding reduction). Useful for the customer ledger.

Both are defensible. Today the field is being set to one OR the other depending on which EC value last wrote `repayment_amount`, which is non-deterministic. Pick one and make the code unambiguous. The child row should follow the same convention (today child=8, parent=761 — clearly inconsistent).

### 5d. Add the parent waiver record explicitly

After the parent's reschedule posts, if `LOSSES_PRN_WAIVED_UB > 0` was sourced from a child foreclosure, write the matching:
- One `waiver_details` row per affected parent ldd (currently 1, the foreclosure-date PRIN row).
- The `waiver__loan_due_details` row already gets written (verified) — just make sure the `identifier_value` correctly points back to the child's prepayment.

Optional (depends on product call): for the parent's future installments that were silently reduced, decide whether to record per-installment waiver entries on the parent OR to surface this on the closure summary only.

### 5e. Skip zero-fee ldd rows

`UpdateDueDetailsForPrepaymentProcessor.processForeclosureFee:233` should early-return if `chargeAmount.signum() == 0 && waivedAmount.signum() == 0`. The base_amount-only row provides no operational value and confuses downstream queries.

### 5f. Data fix for LAN 7000042524 / 7000035818

DB writes are out of scope for this workspace (boundary rule). Once a fix lands and is deployed to QA2, propose to the QA-DBA the following corrective actions:

```sql
-- Reverse the parent's TM 2003 (catalogue 209) — keep the child's TM 2002 intact.
-- Reverse via the standard reverseTransaction API rather than direct DELETE,
-- so transaction_details, GL balances and audit log stay consistent.

-- After reversal, write the correct parent posting via a new TM with the corrected rules
-- (intercompany-only, no duplicate customer-side legs).

-- For the parent waiver gap (BUG #5), insert the missing waiver_details row:
-- INSERT INTO mfi_accounting.waiver_details (loan_account_id, loan_due_details_id, is_fully_waived,
--   waiver_amount, waiver_status, created_by, created_on, updated_by, updated_on)
-- VALUES (32601, 1703, false, 753.000000, 'APPROVED', '<svc-user>', NOW(), '<svc-user>', NOW());
```

Do NOT directly UPDATE `transaction_details` net_amount or DELETE rows — those leave the GL out of balance with no audit trail.

---

## 6. First-SQL diagnostic — has this child foreclosure-with-waiver bug hit a LAN?

For any closed child loan with `parent_loan_account_id IS NOT NULL` and a `LOSSES_PRN_WAIVED_UB > 0` prepayment, check whether the cash GL and waiver expense GL were over-debited.

```sql
WITH affected AS (
  SELECT la_child.account_id   AS child_id,
         la_child.la_account_number AS child_lan,
         la_par.account_id     AS parent_id,
         la_par.la_account_number   AS parent_lan,
         pd.id                  AS prepayment_details_id,
         pd.balance_principal_waived_amount AS principal_waived,
         pd.balance_principal_amount_to_be_paid AS cash_paid
  FROM mfi_accounting.loan_account la_child
  JOIN mfi_accounting.loan_account la_par ON la_par.account_id = la_child.parent_loan_account_id
  JOIN mfi_accounting.prepayment_details pd ON pd.loan_account_id = la_child.account_id
  WHERE la_child.loan_status = 'CLOSED'
    AND pd.prepayment_status = 'APPROVED'
    AND pd.balance_principal_waived_amount > 0
    AND pd.is_child_loan_prepayment = true
)
SELECT a.child_lan, a.parent_lan, a.cash_paid, a.principal_waived,
       (SELECT COUNT(*) FROM mfi_accounting.transaction_master tm
          JOIN mfi_accounting.transaction_details td ON td.transaction_id = tm.id
          WHERE tm.transaction_catalogue_id = 209
            AND td.account_number IN (a.child_lan, a.parent_lan)) AS rsch_legs_on_loans,
       (SELECT COUNT(*) FROM mfi_accounting.waiver_details wd
          WHERE wd.loan_account_id = a.parent_id) AS parent_waiver_rows,
       (SELECT COUNT(*) FROM mfi_accounting.waiver__loan_due_details w
          JOIN mfi_accounting.loan_due_details ldd ON ldd.id = w.loan_due_details_id
          WHERE ldd.loan_account_id = a.parent_id) AS parent_waiver_ldd_rows
FROM affected a
ORDER BY a.child_lan;
```

Any row where `parent_waiver_rows = 0 AND parent_waiver_ldd_rows > 0` is hit by BUG #5; any row where `rsch_legs_on_loans > 0` and `principal_waived > 0` is potentially hit by BUG #1 (verify by inspecting the 5 legs of the catalogue-209 TM).

---

## 7. Cross-references

- Orchestration: `deploy/application/orchestration/loans_orc.xml:1675` (`loanPrepayment`), `:2004` (`do_prepayment=true`), `:2111` (parent call); `deploy/application/orchestration/group_mfi_orc.xml:435` (`parentLoanAccountPartPrepayment`), `:262` (`individualChildLoanForeclosure` — the alternative, queued path).
- Code: `src/main/java/in/novopay/accounting/loan/prepayment/processor/PrepaymentApproppriationProcessor.java`, `UpdateDueDetailsForPrepaymentProcessor.java`, `PopulateAdditionalAmountAndAccountDetailsForForeclosureProcessor.java`; `src/main/java/in/novopay/accounting/loan/partprepayment/processor/PostPartPrepaymentTransactionProcessor.java`, `PopulateAdditionalAmountForPartPrepaymentProcessor.java`, `CreateOrUpdateLoanAccountPartPrepaymentProcessor.java`, `PopulateLoanAccountPartPrepaymentDetailsProcessor.java`; `src/main/java/in/novopay/accounting/loan/rescheduling/processor/LoanAccountRescheduleBatchProcessor.java`; `src/main/java/in/novopay/accounting/loan/lrs/rescheduling/partprepayment/PartPrepaymentLoanAccountRescheduleService.java`; `src/main/java/in/novopay/accounting/loan/lrs/processor/GenerateRepaymentScheduleProcessor.java`.
- Lib: `novopay-platform-lib/infra-navigation/src/main/java/in/novopay/infra/navigation/processor/CallInternalOrchestrationProcessor.java`.
- Related brain docs: [`../accounting/06-shg-jlg-group-loans.md`](../accounting/06-shg-jlg-group-loans.md) (group-loan accounting), [`../accounting/05-flows.md`](../accounting/05-flows.md) (foreclosure section), [`../engines/posting-engine.md`](../engines/posting-engine.md) (GL posting / placeholder resolution).
- Ticket: SDCP-10080. QA2 LAN 7000035818 (parent) / 7000042524 (child), accounting branch `mfi_integration_v3.3.3 @ 15dccca569` at time of analysis.
