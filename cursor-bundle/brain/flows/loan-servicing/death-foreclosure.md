# Loan servicing — Death Foreclosure

> Customer dies → loan is foreclosed via insurance claim. **6-stage workflow** (`STAGE_1` … `STAGE_6`) over days/weeks. Coordinated with insurance partner (HDFC Life / HDFC Ergo / Bajaj Ergo). Generates a Death Claim Form (PDF), submits to insurer, processes return. **FTR/FTNR** outcomes.

## Variants

| Request | XML | Use |
|---|---|---|
| `loanDeathForeclosure` | `loans_orc.xml` | Main entry — staged workflow |
| `getDeathForeclosureDetails` | `loans_orc.xml` | Read state |
| `outboundDeathForeclosureInsuranceJob` | `loans_insurance_orc.xml` | Build outbound file for insurer |
| `inboundDeathForeclosureInsuranceJob` | `loans_insurance_orc.xml` | Process insurer's response file |
| `runInboundDeathForeclosureInsuranceJob` | `loans_insurance_orc.xml` | Trigger inbound processing |
| `deathForeclosureInsuranceJob` | `loans_insurance_orc.xml` | Final accounting after insurer pays |

## Function code = STAGE_*

`loanDeathForeclosure.function_code` is one of:

| Stage | What it does |
|---|---|
| `STAGE_1` | Maker initiates: capture nominee + supporting docs, create death-claim record, generate Death Claim Form PDF, create approval task |
| `STAGE_2` | Verifier reviews docs and approves/rejects |
| `STAGE_3` | Approval team approves the claim for insurance submission |
| `STAGE_4` | Outbound file sent to insurer; awaiting response |
| `STAGE_5` | Insurer response received (FTR=Free To Recover or FTNR=Free To Not Recover); processing |
| `STAGE_6` | Final close: post foreclosure transaction, mark loan FORECLOSED → CLOSED |
| `REJECT` | Cancel at any stage |
| `RE_UPLOAD_DOCUMENT` | Re-upload missing/rejected docs at any stage |

`function_sub_code` = `DEFAULT` (initial) or `UPDATE` (re-edit).

## Required input

(from `<Validators>`)

- `account_number` (loan to foreclose)
- `nominee_document_details` — required if `function_code != REJECT`
- `supporting_document_details` — required if `function_code != REJECT`
- `appointee_document_details` — required if `is_nominee_under_age=true`

## STAGE_1 processor chain (the heaviest stage)

1. `populateUserDetails`, `setCommonAttributesProcessor`
2. `valdiateLoanAccountNumberAndStatusForTransactionProcessor` — guard (loan must be active)
3. `validateDeathForeclosureDocumentsProcessor` — input doc validations
4. `validateTransactionForLoanAccountProcessor` (current_transaction_name=`DEATH_FORECLOSURE`)
5. `deathForeclosureDedupCheckProcessor` — refuse if death-fc already in progress
6. `syncDetailsForDeathForeclosureProcessor` — copy live loan/customer info into death-fc record
7. `createOrUpdateDeathForeclosureDetailsProcessor` — INSERT into `death_foreclosure_details` (status=PENDING)
8. `deathForeClosureSMSNotification` — notify family + branch
9. `excessAmountDeathForeclosureDetailsProcessor` — compute excess amount in `loan_account` (refundable to nominee)
10. `createOrUpdateDeathForeclosurePaymentModeDetailsProcessor` — capture how the family is contributing (cash, transfer)
11. **Document creation chain (×3)** — for nominee, supporting, optionally appointee:
    - `putDocumentDetailsProcessor` (load doc bytes from request)
    - `createDocumentProcessor` — INSERT into `document` + `document_file`
    - `createDeathForeclosureDocumentDetailsProcessor` (role_type=NOMINEE/SUPPORTING/APPOINTEE) — INSERT into `death_foreclosure_details__document`
12. `verifyDocumentProcessor` — DMS verification of nominee/supporting/appointee docs
13. `createTaskApprovalDataForDeathForeclosurePreProcessor` — assemble approval payload
14. `constructRequestForApprovalUsingApprovalTemplate` — wrap in approval template; emit AuditData
15. `createTaskWorkFlowHelpingProcessor` — INSERT into `mfi_task.task` (workflow_master_code=`DEATH_FORECLOSURE`, estimated_tat=10 days, scoped to `loan_office_id`)
16. **Death Claim Form PDF generation chain**:
    - `generateDeathClaimFormPreProcessor` — populate fields (policy number, holder name, member info, DOB, DOD, place + cause of death, nominee info)
    - `generateReportProcessor` (document_type=PDF, document_name=DeathClaimDocument) — calls reporting service
    - The PDF is uploaded to DMS and linked back

`loan_account.loan_status` → `DEATH_FORECLOSURE_FREEZE`.

## STAGE_2 — verifier review

Verifier reviews the nominee + supporting docs:
- Approve → STAGE_3 (or auto-progress depending on config)
- Reject (with `function_code=RE_UPLOAD_DOCUMENT` to maker) → cycle back to STAGE_1 doc updates

## STAGE_3 — approval

Senior reviewer signs off the claim packet for insurer submission.

## STAGE_4 — outbound to insurer

Triggered by scheduled `outboundDeathForeclosureInsuranceJob`:

1. Reads `death_foreclosure_details` rows ready for insurer
2. Reads provider routing (per `loan_account_insurance_details` for the loan)
3. Builds outbound file (provider-specific format: HDFC Life, HDFC Ergo, Bajaj Ergo)
4. Stages in `death_foreclosure_insurance_staging_details`
5. Outbound file written to filesystem / SFTP'd

## STAGE_5 — insurer response (FTR / FTNR)

Triggered by `runInboundDeathForeclosureInsuranceJob` → `inboundDeathForeclosureInsuranceJob`:

1. Reads insurer response file
2. Stages rows in `death_foreclosure_insurance_staging_details`
3. Per row, two outcomes:

   **FTR** (Free To Recover): insurer covers principal + interest. The cleanest case.
   **FTNR** (Free To Not Recover): insurer denies. Nominee/family must pay (or write-off).

4. `loan_account_insurance_details` updated with claim status
5. Notification to maker/branch with outcome

## STAGE_6 — final close

For FTR (revised on 3.3.1.0.1 by SDCP-9301 — see below):

1. **Pre-close — book pending interest accrual** via `checkLoanAccountInterestAccrualBookingProcessor` (slice runs from last-billed date to death date).

2. **Force-bill the partial-cycle slice** (NEW on 3.3.1.0.1, commits `0ebb2fa4a` + `c71ea95c8`):
   ```
   nested postTransaction(BILLING-NORMAL_BILLING):
     DR  REG_EMI_BI                ₹interest_slice    (just-accrued portion)
     CR  INT_ACC_NOT_DUE           ₹interest_slice
   ```
   Moves the slice from `INT_ACC_NOT_DUE` → billed (`REG_EMI_BI`). Then EC swaps placeholder code from `LOSSES_INT_WAIVED_AIR` (waived-not-billed) → `LOSSES_INT_WAIVED` (waived-billed) so the DFC loss leg credits the now-billed bucket.

   **EC save/restore:** before nested `postTransaction(BILLING)`, the writer saves DFC's globals (`additional_amount_details`, placeholder list); after, restores them — so DFC's own posting (step 3) sees its own context, not BILLING's. This was the SDCP-9301 root-cause fix.

3. **DFC main posting:**
   ```
   DR  INSURANCE_RECEIVABLE_AC    ₹insurance_settlement_amount
   CR  LOAN_PRIN_AC               ₹principal due
   CR  INT_RECEIVABLE_AC          ₹interest due (incl. just-billed slice)
   CR  PINT_INC_AC                ₹penal due (if any)
   ```

4. **Insurer-paid leg** (when insurer pays, not always synchronous):
   ```
   DR  BANK_AC                    ₹insurance_paid
   CR  INSURANCE_RECEIVABLE_AC    ₹insurance_paid
   ```

5. Excess amount (if any in `loan_account.excess_amount`) → refunded to nominee via `loan_account_excess_amount_refund_details`.

6. `loan_account.loan_status` → `FORECLOSED` → `CLOSED` (auto-closure).

7. NOC record created in `loan_account_noc_details` (issued in nominee's name).

8. `death_foreclosure_details.status` → `CLOSED`.

9. Task closed.

### SDCP-9301 — partial-cycle billing fix (3.3.1.0.1)

**Pre-fix bug:** if a loan had pending accrual between `last_billed_date` and `death_date`, STAGE_6 would book it to `INT_ACC_NOT_DUE`, then DFC's loss leg would credit `LOSSES_INT_WAIVED_AIR` (interest waived, NOT billed) for the same slice. Result: the slice sat unbilled forever in `INT_ACC_NOT_DUE`, and the loss waiver was for waived-not-billed when it should have been waived-billed. Trial balance showed asymmetry; customer ledger was wrong.

**Fix (3 commits, 2026-04-29 → 05-04):**
- `0ebb2fa4a` — force-bill nested call introduced.
- `c71ea95c8` — EC save/restore so the nested `postTransaction(BILLING)` doesn't pick up DFC's outer placeholder list.
- `59e253c54` — clamp slice start: `effectiveAccrualStart = max(last_billed_date, death_date)`. Prevents pre-death BPI (already settled at disbursement) from being re-accrued into the slice.

**Code:** `DeathForeclosureInsuranceWriter.java` (Spring Batch ItemWriter for STAGE_6). Cross-link: `engines/posting-engine.md` placeholder section (LOSSES_INT_WAIVED_AIR vs LOSSES_INT_WAIVED).

**Result:** post-DFC ledger has `INT_ACC_NOT_DUE = 0`; trial balance net-zero; customer ledger reflects either paid, waived-billed, or settled-by-insurance for every interest paisa accrued up to death date.

For FTNR:
- Either family pays manually (regular `loanRepayment`) → close
- Or `loanWriteoff` is initiated → see [write-off.md](write-off.md)

## DB tables touched (cumulative across stages)

| Table | Action | Stage |
|---|---|---|
| `death_foreclosure_details` | INSERT/UPDATE | 1, all |
| `death_foreclosure_appointee_details` | INSERT (if minor nominee) | 1 |
| `death_foreclosure_nominee_details` | INSERT | 1 |
| `death_foreclosure_payment_mode_details` | INSERT | 1 |
| `death_foreclosure_details__document` | INSERT (×N docs) | 1, RE_UPLOAD |
| `document`, `document_file` | INSERT (per doc upload) | 1 |
| `death_foreclosure_insurance_staging_details` | INSERT (outbound) / UPDATE (inbound) | 4, 5 |
| `loan_account.loan_status` | UPDATE → `DEATH_FORECLOSURE_FREEZE` → `FORECLOSED` → `CLOSED` | 1 → 6 |
| `loan_account_insurance_details` | UPDATE (claim status) | 5 |
| `loan_account_excess_amount_refund_details` | INSERT (refund) | 6 |
| `loan_account_noc_details` | INSERT | 6 |
| `loan_account_closure_details` | INSERT | 6 |
| `transaction_master`, `transaction_partition_details`, etc. | INSERT (final foreclosure posting) | 6 |
| `mfi_approval.application` | INSERT/UPDATE | 1, 2, 3 |
| `mfi_task.task` | INSERT/UPDATE | 1, 2, 3 |
| `mfi_dms.document` (DMS) | INSERT (Death Claim Form PDF) | 1 |

## SHG/JLG fan-out

If the deceased customer is a member of a SHG/JLG group, the death-fc on their child loan triggers parent-side reschedule. The parent transitions to `DEATH_FORECLOSURE_FREEZE_RSCH` until parent's schedule is recomputed (similar to disbursement-cancellation parent-rescheduling pattern).

## Insurance partner integration

Per-provider triplets (`outbound*Job`, `inbound*Job`, `runInbound*Job`) for:
- HDFC Life (life insurance)
- HDFC Ergo (health)
- Bajaj Ergo (health)

Each partner has slightly different file format + return codes; abstracted by per-provider tasklet implementations.

## Common queries

```sql
-- Death FC in progress
SELECT a.account_number, dfd.status, dfd.created_on, dfd.cause_of_death,
       la.loan_status
  FROM mfi_accounting.death_foreclosure_details dfd
  JOIN mfi_accounting.loan_account la ON la.account_id = dfd.loan_account_id
  JOIN mfi_accounting.account a ON a.id = la.account_id
 WHERE dfd.status NOT IN ('CLOSED','REJECTED')
 ORDER BY dfd.created_on;

-- Insurance staging — what's pending insurer response
SELECT loan_account_no, status, provider, sent_on
  FROM mfi_accounting.death_foreclosure_insurance_staging_details
 WHERE status IN ('SENT','PENDING')
 ORDER BY sent_on LIMIT 50;
```

## Failure modes

| Symptom | Cause | Triage |
|---|---|---|
| Stuck in STAGE_1 / DEATH_FORECLOSURE_FREEZE | Verifier (STAGE_2) not actioned | Push operator |
| Insurer file not generated | `outboundDeathForeclosureInsuranceJob` schedule missed or row stuck PENDING | Check `mfi_batch.batch_schedule` last_run; check staging table |
| FTR posted but loan still not CLOSED | STAGE_6 auto-closure failed mid-chain | Check app log around STAGE_6 timestamp; `loanAccountClosure` batch may pick up later |
| Wrong nominee in PDF | `syncDetailsForDeathForeclosureProcessor` pulled stale data | Re-edit via STAGE_1 with `function_sub_code=UPDATE` |
| FTNR but nominee not informed | Notification lookup missing | Check notification template `DEATH_FC_FTNR_*` |

## Code anchors

- **Orchestration**: `loans_orc.xml::loanDeathForeclosure`, `loans_insurance_orc.xml` (insurance partner Requests)
- **Death-foreclosure code root**: [`loan/deathforeclosure/`](../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/deathforeclosure/)
- **Insurance integration**: [`loan/deathforeclosure/insurance/`](../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/deathforeclosure/insurance/)
- **Reader/writer for staging**: [`loan/deathforeclosure/reader/`](../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/deathforeclosure/reader/), [`loan/deathforeclosure/writer/`](../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/deathforeclosure/writer/)
- **Tables (Tier 2 — not yet curated)**: `death_foreclosure_details` (31 cols), `death_foreclosure_insurance_staging_details` (67 cols), `death_foreclosure_appointee_details` (17 cols), `death_foreclosure_nominee_details` (19 cols), `death_foreclosure_payment_mode_details` (8 cols), `death_foreclosure_details__document` (5 cols)

## Cross-references

- [Foreclosure (regular)](../foreclosure-and-closure.md)
- [Excess amount refund](excess-amount-refund.md)
- [Write-off](write-off.md) (for FTNR fallback)
- Lifecycle: `DEATH_FORECLOSURE_FREEZE`, `DEATH_FORECLOSURE_FREEZE_RSCH` in [`../../accounting/07-loan-account-lifecycle.md`](../../accounting/07-loan-account-lifecycle.md)
