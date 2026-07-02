# Repayment engine — parent / child / NPA / auto-closure

**Branch verified:** `mfi_integration_v3.3.1.0.1` (head `149009993`, audited 2026-05-08).
**3.3.1.0.1 deltas:** (i) dup-CRN error code returned by `clientReferenceNumberDedupProcessor` is now `134497` (was `134067`) — friendly error per `d358a9034`; (ii) SI Manual Presentation customer-name fix + optimization (`3ce59eaf2`, `562957eb8`, `a59d96066`) — purely cosmetic on the SI presentation screen, no flow change.
**Authoritative paths:**
- [loans_orc.xml](../novopay-platform-accounting-v2/deploy/application/orchestration/loans_orc.xml) `<Request name="loanRepayment">` at L958.
- [mfi_orc.xml](../novopay-platform-accounting-v2/deploy/application/orchestration/mfi_orc.xml) `<Request name="loanRepayment">` at L2661 (DDP / `novosli` channel).
- [group_mfi_orc.xml](../novopay-platform-accounting-v2/deploy/application/orchestration/group_mfi_orc.xml) `<Request name="childLoanRepayment">` at L33.
- Java: [src/main/java/in/novopay/accounting/loan/repayment/](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/repayment/) (parent), [loan/grouploan/repayment/](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/repayment/) (child enqueue).

---

## 1. Three repayment Requests — same name, different orchestrations

| Request | File:Line | Channel | Txn model |
|---------|-----------|---------|-----------|
| `loanRepayment` | `loans_orc.xml`:958 | Generic / web | Implicit |
| `loanRepayment` | `mfi_orc.xml`:2661 | DDP — `novosli` channel; sets `user_id=2` before `populateUserDetails`; `client_reference_number` minLength=10 | **`explicitTxnMgmt="true"`** |
| `childLoanRepayment` | `group_mfi_orc.xml`:33 | Async, queue-driven (per-member SHG/JLG) | Implicit (called from batch worker) |

**Tenant precedence (`application.properties`):** `mfi,product` — so `mfi_orc.xml` overrides `loans_orc.xml` for tenants that load mfi templates.

---

## 2. Parent leg shape (loans_orc.xml L958+ — full chain summary)

Validators: `mandatoryFieldValidator` (`account_number, repayment_amount, value_date, repayment_mode, client_reference_number`), `masterDataValidator`, `amountValidator`, `patternFieldValidator`, `stringLengthValidator`.

Processor flow:

1. `populateUserDetails` → `setCommonAttributesProcessor`.
2. Nested API: `getNotificationMessageByNotificationCode` (resolves narration template).
3. **`validateLoanAccountNumberAndStatusForRepayProcessor`** — gates on `loan_status` (must allow repayment).
4. `validateLoanRepaymentData` — request-shape validation.
5. **`autoPopulateChildLoansForRepaymentProcessor`** — for SHG/JLG, expands `child_loans[]` from current member roster if not provided.
6. `validateChildLoansRepaymentDataProcessor` — per-child validation.
7. `receiptNumberDedupProcessor` — separate dedupe before `postTransaction`'s own CREF dedupe.
8. **Mode router** — conditional `dummyProcessor`s set `transaction_type` / `transaction_sub_type` based on `repayment_mode` (CASH, ACH, NEFT, UPI, NET_BANKING, EXCESS_AMT, DIRDR, etc.).
9. **`function_code` router**:
   - `DEFAULT` → `getMakerCheckerEnabledForUseCaseProcessor` (use case `LOAN-RPYMT-UC001`).
   - `APPROVE` / `RESUBMIT` flows for maker-checker.
10. **`run_mode` router**:
    - `TRIAL` → nested `<API name="postTransaction">` with `run_mode=TRIAL` (no DB writes).
    - `REAL` → update loan rows + nested `postTransaction` (REAL) + child enqueue + GL/CBS push.
11. **NPA reverse leg** (verbatim block in §4 below).
12. **Auto-closure block** — eligibility check → DPD recalc → asset criteria → asset classification → auto-closure → closure detail persistence + Kafka publish.

---

## 3. Child leg (group_mfi_orc.xml L33–L177)

```xml
<Request name="childLoanRepayment">
  <!-- mode-conditional: CASH/DIRDR/ACH/UPI/NET_BANKING/EXCESS_AMT
       set transaction_type/transaction_sub_type via dummyProcessor -->
  <Processor bean="getOfficeIdFromAccountNumberProcessor"/>
  <Processor bean="checkEligibleForRepaymentAppropriationProcessor"/>
  <Processor bean="repaymentApproppriationProcessor"/>
  <Processor bean="populateAmountForExcessRepaymentModeProcessor"/>
  <Processor bean="populateAdditionalAmountDetailsProcessor"> <!-- 6× : PRIN_AMT, INT_AMT, PENALTY_AMT, EXCESS_AMT, SUSP_AMT, FEE_AMT --> </Processor>
  <Processor bean="populateTransactionAccountDetailsProcessor"/>
  <Processor bean="updateLoanDueDetailsProcessor"/>
  <Processor bean="updateLoanInstallmentDetailsProcessor"/>
  <Processor bean="updateLoanAccountForExcessAmountProcessor"/>
  <API id="postTransaction" name="postTransaction" version="v1"> <!-- L110-L122 --> </API>
  <Processor bean="createLoanAccountPaymentsDetailsProcessor"/>
  <Processor bean="checkNPAReverseMovementRequiredProcessor"/>     <!-- L124 -->
  <Control method="if" pattern="${do_npa_reverse_movement}" condition="=" value="true">
    <Processor bean="populateAdditionalAmountDetailsProcessor"> <!-- INT_SUS_AMT --> </Processor>
    <Processor bean="populateTransactionAccountDetailsProcessor"/>
    <API id="postTransaction" name="postTransaction" version="v1">
      <IParam fieldName="transaction_sub_type" value="NPA"/>
      <IParam fieldName="amount" value="${interest_amount}"/>
      <IParam fieldName="client_reference_number" value="${npa_client_reference_number}"/>
    </API>
  </Control>
  <Processor bean="checkAccountAutoClosureEligibilityProcessor"/>  <!-- L150 -->
  <Control method="if" pattern="${eligible_for_auto_closure}" condition="=" value="true">
    <Processor bean="populateLoanAutoClosureReqProcessor"/>
    <Processor bean="loanAccountDpdCalcProcessor"/>
    <Processor bean="loanAccountAssetCriteriaProcessor"/>
    <Processor bean="loanAccountAssetClassificationProcessor"/>
    <Processor bean="loanAccountAutoClosureProcessor"/>
    <Processor bean="createLoanAccountClosureDetailsProcessor"/>
  </Control>
</Request>
```

---

## 4. NPA reverse leg — verbatim (group_mfi_orc.xml L124–L149)

```xml
<Processor bean="checkNPAReverseMovementRequiredProcessor"/>
<Control method="if" pattern="${do_npa_reverse_movement}" condition="=" value="true">
  <Processor bean="populateAdditionalAmountDetailsProcessor">
    <IParam fieldName="reference_code" value="INT_SUS_AMT" scope="local"/>
    <IParam fieldName="amount" value="${interest_amount}" scope="local"/>
  </Processor>
  <Processor bean="populateTransactionAccountDetailsProcessor">
    <IParam fieldName="placeholder" value="LOAN_ACCOUNT" scope="local"/>
    <IParam fieldName="narration" value="Loan Repayment" scope="local"/>
    <IParam fieldName="account_number" value="${account_number}" scope="local"/>
  </Processor>
  <API id="postTransaction" name="postTransaction" version="v1">
    <IParam fieldName="transaction_sub_type" value="NPA" scope="local"/>
    <IParam fieldName="amount" scope="local" value="${interest_amount}"/>
    <IParam fieldName="client_reference_number" scope="local" value="${npa_client_reference_number}"/>
  </API>
</Control>
```

Identical pattern in `loans_orc.xml` L1228–L1254 and `mfi_orc.xml` L2793–L2815.

**Semantics:** when a previously-accrued NPA suspended-interest balance exists, a secondary `postTransaction` with `transaction_sub_type=NPA` posts the suspended-interest amount. Uses a **separate** `client_reference_number` (`npa_client_reference_number`) — so dedupe is independent of the primary repayment.

---

## 5. Parent → Child enqueue

Java: [`ChildLoanRepaymentEventGenerationProcessor.java`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/repayment/processor/ChildLoanRepaymentEventGenerationProcessor.java) (L20–L53).

Invoked at:
- `loans_orc.xml` L1224
- `mfi_orc.xml` L2781

Behaviour:
1. Builds a `LoanAccountEventsQueueEntity` per child loan: `parentAccountId = loanAccountEntity.getId()`, `eventType = "REP"`, `eventStatus = "P"`.
2. Populates `data` JSON via `repEventsQueueDataPopulator`.
3. Saves via `LoanAccountEventsQueueDAOService.save`.

**Drain job:** `childLoanEventProcessingBatchJob` ([batchnew/childloaneventprocessingbatchjob/](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/batchnew/childloaneventprocessingbatchjob/)). `GRID_SIZE=30, CHUNK_SIZE=50`, cron `0 0 0/2 * * ?` (every 2 hours). Reader queries `WHERE event_status='P' AND is_deleted=false`. Writer dispatches per `event_type`:
- `REP` → `childLoanRepayment`
- `FCL` → `childLoanForeclosure`
- `WAIVER` → `childWaiveLoanAccountCharges`
- `RSTCRE` → `childLoanRestructuring`
- `REOPN` → `childLoanReopening`
- `TXNREV` → `childLoanTransactionReversal`
- `PRTPRE` → `childLoanPartPrepayment`
- `REBK` → `childLoanRebooking` / `childLoanRebookingAdjustmentTransaction`
- `CANCL` → `childLoanDisbursementCancellation` (and `*ParentRescheduling`)
- `CLB` → `childLoanBooking`
- `CLMT` → CLMT queue sync (parent NEFT v2 / SHG bank progression)
- `LEAR` → ledger event after refund

---

## 6. Auto-closure block (parent + child paths)

Eligibility decision: `checkAccountAutoClosureEligibilityProcessor` (sets `eligible_for_auto_closure`).

When eligible:
1. `populateLoanAutoClosureReqProcessor` — builds closure request shape.
2. `loanAccountDpdCalcProcessor` — recomputes DPD (days past due).
3. `loanAccountAssetCriteriaProcessor` — re-applies asset criteria slabs.
4. `loanAccountAssetClassificationProcessor` — re-classifies (NPA bucket).
5. `loanAccountAutoClosureProcessor` — flips `loan_status=CLOSED`.
6. `createLoanAccountClosureDetailsProcessor` — persists `loan_account_closure_details` row.
7. (Parent only) `pushLoanAccountClosureDetailsProcessor` — publishes Kafka `los_lms_data_sync_` with `entity_type, event_type=CLOSURE`.

**Note:** child auto-closure does NOT push to LOS — parent rolls up via `parentGroupDisbursementStatusSyncService`.

---

## 7. Cross-leg release rules (mandatory)

Any change to repayment behaviour must be **mirrored across all 3** Request definitions:

| Change | Edit | Verify |
|--------|------|--------|
| New repayment mode (e.g. `DIGITAL`) | mode router in `loans_orc.xml` + `mfi_orc.xml` + `group_mfi_orc.xml` | child `postTransaction` logs concrete `transaction_type/sub_type` (no `${...}` placeholder leakage) |
| New txn sub-type | new row in `transaction_catalogue` + `transaction_accounting_rule` | catalogue/rule lookup succeeds in both legs |
| New EC field consumed by child | populate it in parent **before** queue write | child API does not see null |
| Queue-shape change | `LoanAccountEventsQueueEntity` data JSON contract | drain batch parses it; `event_status` reaches `C` without retry loop |
| Child → parent rollup | `parentGroupDisbursementStatusSyncService.syncParentAfterChildQueueProgress` | parent + every child both reach terminal state in one E2E run |

Failure mode if not mirrored: parent `postTransaction` succeeds → parent leg appears settled → child leg fails with `Invalid transaction_type and/or transaction_sub_type` → SHG group state diverges silently. Documented as a **High** cross-service-transaction risk in `cross-service-transactions.md`.

---

## 8. Receipt-number / client-reference dedupe layering

| Layer | Where | Key | Failure mode |
|-------|-------|-----|--------------|
| Receipt-level | `receiptNumberDedupProcessor` (parent only) | `receipt_number` | Whole repayment rejected |
| Primary post | `clientReferenceNumberDedupProcessor` inside nested `postTransaction` | `client_reference_number` | Single-leg dedupe (134067) |
| NPA reverse post | same processor inside the secondary `postTransaction` | `npa_client_reference_number` (distinct EC key) | Independent — primary success + NPA-leg replay safe |
| Payments-side push | `MfiCollectionsDAOService.callPushLMSUpdateAPI` retry loop | accounting CRR | Payments retries on transport failure; relies on accounting dedupe |

**Risk window (GAP-068):** payments retries the whole nested `loanRepayment` if accounting transport fails after partial commit; accounting dedupe protects, but receipt-semantics drift could open a double-post hole.

---

## 9. Tests / coverage

Verified test inventory on this branch:
- `loan/repayment/` test package present.
- `loanRepayment` E2E suites in `disburse_loan_sanity.py` cover JLG/INDL/SHG.
- **Gap:** no automated test for `childLoanRepayment` queue-drain failure modes (poison message, partial child failure with parent-success).
- **Gap:** no automated test for NPA reverse leg dedupe semantics.

---

## 9.5. NPA suspense — **set during appropriation, not as post-step**

**Critical insight (was undocumented):** `RepaymentApproppriationProcessor.process()` ([file](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/repayment/processor/RepaymentApproppriationProcessor.java)) populates `suspense_amount = interest_amount` inline at L113–L116 **only when** `loanAccountEntity.getNpaAgeingStartDate() != null`. The 1-st `postTransaction` then resolves the credit leg through the rule engine — credit goes to `INT_SUSPENSE` (not `INT_INCOME`) because the placeholder binding for NPA loans is configured that way in `transaction_accounting_rule`.

The 2-nd (NPA reverse) `postTransaction` (L2807–L2827 in mfi_orc.xml; L2228–L2254 in loans_orc.xml) only fires when `do_npa_reverse_movement=true` (set by `CheckNPAReverseMovementRequiredProcessor`). It uses a **separate `client_reference_number = "NPA_" + primary_cref`** (L31 of CheckNPAReverseMovementRequiredProcessor) — independent dedup keying so the primary repayment + NPA reverse can be replayed without collision.

**Implication for debugging:** if a repayment shows the wrong INT GL bucket on an NPA loan, check the appropriation step first — `suspense_amount` must be non-zero on the request to `postTransaction`. If `suspense_amount=0` but the loan is NPA, the bug is in `npa_ageing_start_date` not being set on the loan.

---

## 9.6. DDP-specific overrides (mfi_orc.xml L2661+)

The `mfi_orc.xml` variant — invoked when tenant resolves `mfi` template precedence — adds:

- **`explicitTxnMgmt="true"`** — wraps `postTransaction` + child event generation in an outer `<Transaction>` block. Each inner `<API name="postTransaction">` and the `childLoanRepaymentEventGenerationProcessor` commit independently (REQUIRES_NEW per `ProcessorOrchestrator`).
- **`user_id=2`** pre-populated before `populateUserDetails` (DDP system user).
- **Channel-aware `client_reference_number` minLength**: `minLength=10` for DDP (`channel_code,client_code="novosli,novosli"`), `minLength=1` for everything else. Validators at L2697–L2701.
- **DDP-only response fields**: `overall_transaction_details` + `account_level_transaction_details`, populated by `extractOverallTransactionDetailsAndNetAmountForAccountProcessor` at L2801. Non-DDP paths do not produce these — front-ends consuming `loanRepayment` over the generic gateway do not see them.

**Implication:** the 3-leg parity check in §7 holds for the *core* flow (validators → appropriation → postTransaction → audit). DDP path differs in (a) txn-isolation boundaries and (b) extra response fields. Behaviour is otherwise identical.

---

## 9.7. Missing processors flagged by audit

These processors are referenced by ORC but not currently locatable in the code scan — likely they exist under different package paths or are dynamically registered. Verify before relying on the contract:

- `populateAmountForExcessRepaymentModeProcessor` (loans_orc.xml L1132, mfi_orc.xml L2739, group_mfi_orc.xml L83) — populates `excess_amount` based on `repayment_mode`.
- `checkEligibleForRepaymentAppropriationProcessor` (same call sites) — gates whether the appropriation block runs at all. If it sets `do_repayment_appropriation=false`, the appropriation chain is skipped and `principal_amount` / `interest_amount` are **never populated** — subsequent `postTransaction` will fail validation.

**Action:** when debugging "appropriation skipped" symptoms, grep wider — `grep -rn "checkEligibleForRepaymentAppropriationProcessor\|populateAmountForExcessRepaymentModeProcessor" /home/darpan/darpan/`. If still missing, the processor name in ORC may be a Spring bean alias or tenant-overridden — consult `application.properties` and component-scan paths.

---

## 10. Quick verify commands

```bash
# All postTransaction call-sites in repayment ORC
grep -n 'name="postTransaction"' \
  novopay-platform-accounting-v2/deploy/application/orchestration/loans_orc.xml \
  novopay-platform-accounting-v2/deploy/application/orchestration/mfi_orc.xml \
  novopay-platform-accounting-v2/deploy/application/orchestration/group_mfi_orc.xml

# Confirm 3-way mode mapping parity for a specific mode
grep -n 'value="<MODE_NAME>"' \
  novopay-platform-accounting-v2/deploy/application/orchestration/{loans_orc,mfi_orc,group_mfi_orc}.xml

# Inspect queue drain job
ls novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/batchnew/childloaneventprocessingbatchjob/
```

---

*When editing any of: `loanRepayment` (any of the 3 ORCs), `childLoanRepayment`, `ChildLoanRepaymentEventGenerationProcessor`, `LoanAccountEventsQueueEntity`, `childLoanEventProcessingBatchJob`, repayment appropriation, NPA reverse logic, or auto-closure — update this file and the cross-leg checklist in §7.*
