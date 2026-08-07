# Flow — Loan application + underwriting

## Mental model

Once the customer (or group) is in actor, a loan application becomes the central entity. It progresses through **stages** owned by LOS, each adding data and gating on eligibility/bureau/operator decisions. The final stage triggers disbursement (next flow).

Stage progression (per `StageConstants.java` + the operational sequence in LOS .cursorrules line 114):

```
QDE → ES → HHIE → AD → DDE → GFM (SHG/JLG only) → BET → CUWRTR → Document Mgmt → CPDC → triggerDisburseLoan
```

Per-stage operator tasks live in the **task service**. Maker-checker on Credit Underwriting + Disbursement-trigger lives in **approval**.

## Services involved

| Service | What it does |
|---|---|
| LOS | The application state machine; every stage is one or more `createOrUpdate*` Requests |
| actor | Look up customer / employee / group / hierarchy on every stage |
| masterdata | Code masters per stage (loan purpose, product, eligibility constants) |
| dms | Application docs (KYC, agreement drafts) |
| approval | Maker-checker on CU + disbursement-trigger |
| task | Operator tasks per stage (BET schedule, document dispatch, CU review) |
| notifications | Status updates to customer (SMS) and operator (push/email) |
| BPMN (Camunda) | Process orchestration for some stage flows |

## Stages — what each does

| Stage | Key Requests | What's captured |
|---|---|---|
| QDE — Quick Data Entry | `createOrUpdateLoanApp`, `createOrUpdateLoanAppPersonalDetails`, `createOrUpdateBorrowerCoborrowerDetails` | Mobile, name, basic identity, requested amount, product |
| ES — Eligibility Summary | `processEligibilityRules`, `processEligibilitySummaryRules`, `getDeviatedRules` | Rule outcomes (BRE / bureau-merged) + deviations |
| HHIE — Household Income & Expense | `createOrUpdateFamilyMemberDetails`, `addOrUpdateBorrowerIncomeDetails`, `addUpdateExpenseDetails`, `createOrUpdateHouseholdProfile` | Family composition, per-member income, household expense pattern |
| AD — Address verification | `createOrUpdateLoanAppPersonalDetails` (residential / office / co-borrower addresses) | Confirmed addresses with masterdata-validated VTC |
| DDE — Detailed Data Entry | `createOrUpdateBorrowerDDE`, `createOrUpdateFinancialDetails`, `createOrUpdateTaxDetails`, `createOrUpdateCreditBureauReport` | Detailed financial profile, tax, bureau snapshot |
| GFM — Group Formation (SHG/JLG only) | `createOrUpdateGroup`, `updateGroupSignatories`, `getGroupFlccDetails`, `createOrUpdateGroupFlcc`, `processGroupFormationEligibilityRules` | Group membership + eligibility |
| BET — Borrower Engagement Tool | `getBETDetails`, `submitScheduleBet`, `submitAcceptBetTask`, `rejectBetTask`, `submitGroupConductBet`, `submitGroupConductPdc` | Field-officer questionnaire on borrower behaviour, group conduct PDC |
| CUWRTR — Credit Underwriting | `submitCreditUnderwriting`, `processBetEligibilityRules` | Underwriter decision (with maker-checker) |
| Document Management | `uploadLoanOriginationDocument`, `generateLoanDocuments`, `generateSpecificLoanDocuments`, `eSignInitiateRequest`, `updateEsignStatus`, `savePhysicalSignDocument`, `documentVerification` | Loan agreement, eSign, physical sign |
| eStamp | `createEStamp`, `getEStampStatus`, `getEStampPaper` | Digital stamp paper |
| CPDC — Credit Policy Document Check | `processLoanAppIdForDisbursementAfterPDC`, `submitTaDashboardTask` | Pre-disbursement document/policy gate |
| Disbursement-trigger | `triggerDisburseLoan` | Publishes Kafka → accounting (see [`disbursement-end-to-end.md`](disbursement-end-to-end.md)) |

## Bureau / dedup pipeline (async)

Runs alongside QDE / DDE / CM stages:

```
LOS produces                                         LOS consumer processes
─────────────────────                                ──────────────────────
indl_qde_borrower_*_internal_dedupe_*  ─────▶       internalDedupeConsumer
indl_qde_borrower_*_factiva_*          ─────▶       factivaConsumer
indl_qde_borrower_*_posidex_*          ─────▶       posidexConsumer
indl_qde_borrower_*_posidex_*_2nd_call ─────▶       posidexSecondCallConsumer
indl_qde_borrower_*_multi_bureau_*     ─────▶       multiBureauConsumer
+ jlgdl_* variants for group loans
+ _retry_ variants for failures
```

Each consumer enriches the loan application with bureau data (writes to `posidex_status_log`, `multi_bureau_*` tables) and updates the eligibility decision. Failures retry via the `_retry_` topics; eventually surface as a deviation requiring operator decision.

## Operator task creation (per stage)

LOS calls `createOrUpdateTask` (or `createOrUpdateMfiTaskByCode`) on the task service whenever a stage requires operator action:

| Stage | Task type |
|---|---|
| BET schedule | Field officer task to schedule the BET visit |
| BET conduct | Field officer task to conduct the BET |
| CU review | Underwriter review task |
| CPDC | Operations review task (`createUpdateOpsTask`) |
| Document dispatch | Dispatch operator task (`createOrUpdateDocDispatchTask`) |
| Disbursement | Disbursement operator task |

Tasks have TAT; `notifyUsersForPendingTasksJob` reminds; `tat_escalation_matrix` escalates.

## Maker-checker on CU + Disbursement

Both `submitCreditUnderwriting` and `triggerDisburseLoan` go through `submitApplication` on the approval service. The CU/disbursement state advances only on `approveApplication`. See [`maker-checker.md`](maker-checker.md).

## DB writes summary

LOS tables touched (heaviest): `loan_app`, `loan_app_process`, `loan_app__customer_details`, `loan_app__bet_details`, `loan_app__flcc_group(_member)`, `posidex_status_log`, `multi_bureau_*`, `doc_generation_status`, `document_dispatch`, `estamp_details`, `entity__step_sub_step_status(_history)`, `ops_rejected_reason_history`, `disburse_loan_process`.

## Failure modes

| Symptom | First check |
|---|---|
| Stage stuck mid-progress | `entity__step_sub_step_status` for the loan_app_id; look for missing transition |
| Bureau result not arriving | LOS `_retry_` topics; check consumer last-poll |
| Task not appearing for operator | task service log; verify `createOrUpdateTask` call succeeded; verify hierarchy resolution against actor |
| Eligibility rules wrong | BRE service stored procedures (lives outside this workspace); verify `processEligibilityRules` call returned expected codes |
| eSign callback missing | Document service eSign callback handler at gateway; check `Esign*Controller` |
| `triggerDisburseLoan` doesn't publish | Verify approval row APPROVED; verify CPDC complete (`disburse_loan_process` row); verify Kafka producer health |

## Where to dig deeper

- LOS brain: [`../services/novopay-mfi-los.md`](../services/novopay-mfi-los.md)
- Disbursement (next stage): [`disbursement-end-to-end.md`](disbursement-end-to-end.md)
- Maker-checker: [`maker-checker.md`](maker-checker.md)
