# 11 · `mfi_integration_v3.3.1.0.1` — what's different from `3.2.8.4.1`

> Audit ran 2026-05-08. Read this when investigating any production issue on 3.3.1.0.1 — many fixes here changed contract behaviour materially (state machine, error codes, placeholder semantics, batch boundary).
>
> **HEADs at audit time:** accounting-v2 `149009993b`, batch `mfi_integration_v3.3.1.0.0`, platform-lib upstream `mfi_integration_v3.3.1.0.1`.
>
> Predecessor doc: this file replaces "what changed since 3.2.8.4.1" notes scattered across [`engines/disbursement-engine.md`](../engines/disbursement-engine.md) §11, [`engines/posting-engine.md`](../engines/posting-engine.md) header, [`engines/repayment-engine.md`](../engines/repayment-engine.md) header, and the changelog.

---

## 1. The big themes

| Theme | Severity | Where |
|---|---|---|
| **NEFT v2 enabled + concurrency-race series closed** (15 commits) | High | engines/disbursement-engine.md §4.8, §4.9 |
| **Death-foreclosure STAGE_6 partial-cycle billing** (SDCP-9301, 3 commits) | High | flows/loan-servicing/death-foreclosure.md (STAGE_6 section) |
| **`runEODJobs` orchestration scope clarified** (no code change; doc-only) | Medium | system/07-batch-atlas.md, accounting/03-batch-dependency.md |
| **Dup-CRN error code: `134067` → `134497`** | Medium | engines/posting-engine.md, engines/repayment-engine.md |
| **Task-id-orphan fix backport** | Low | runbooks/task-id-orphan-data-patch.md |
| **Platform-lib: `setIfAbsent` cache primitive + Kafka master-data routing** | Low | platform/redis-key-registry.md, platform/event-registry.md |

---

## 2. NEFT v2 series (accounting-v2)

NEFT v2 was disabled by config on 3.2.8.4.1. **3.3.1.0.1 enabled it (`340aff84b`) and shipped 14 follow-up fixes** to close the concurrency races that surfaced under real bank-callback timing.

### 2.1 Atomic CAS redesign for CLMT + parent loan state (PR #260, `e3d84a53b … f6e83c9fe`, 2026-04-28 → 05-04)

**Before:** `dao.save(entity)` after a state computation. Multiple writers (sync NEI inquiry response handler, async NEI callback handler, MFT callback handler, child queue replayer) could all `setDisbursementStatus` + save on the same `loan_account_events_queue` row in close succession. With no `@Version` on `LoanAccountEventsQueueEntity`, JPA save = blind UPDATE → last-writer-wins → stuck rows.

**Now:**
- New service `ChildClmtStateMachineService.transition()` — `@Transactional(REQUIRES_NEW)` + atomic CAS via `@Modifying` UPDATE … WHERE … RETURNING. Caller gets `APPLIED` (1 row) or `REJECTED` (0 rows, race lost).
- New service `LoanAccountStateMachineService.transition()` — same shape, on `loan_account.disbursement_status` (parent JLG/INDL flow).
- Helper `ChildClmtTerminalStateGuard.rankBackwardSafeFromStates(toState)` — derives the `fromStates` CSV from a rank table `DTFC_SUCCESS(1) < NEFT_STAGE_1_PENDING(2) < NEFT_STAGE_1_SUCCESS(3) < NEFT_STAGE_2_PENDING(4) < COMPLETED(5)`.

### 2.2 Hibernate auto-flush race close (`4c339282f` + `09295c377`, 2026-05-07)

**Survived the CAS redesign:** the `applyClmtAndSave` OK branch and the in-progress callback advisory branch both **mutated the in-memory `LoanAccountEventsQueueEntity`** after CAS. That entity loaded by `PerformChildLoanBankDisbursementProcessor:74` stays in the outer `disburseLoan` Hibernate persistence context; `AbstractBaseEntity` has **no `@PreUpdate`**, so the in-memory `updated_on` keeps its load-time value forever. When the outer transaction commits, Hibernate emits a plain UPDATE that rewrites the row with the in-memory state including the stale `updated_on` — undoing any later async-callback CAS to `COMPLETED`.

**Fix:** removed every post-CAS in-memory mutation block. CAS is now the sole writer. Failure / advisory / parse-error writes go through a new state-agnostic `ChildClmtStateMachineService.patchJsonFields` that does a `@Modifying` JSON-merge UPDATE and rejects any patch containing `disbursement_status`. Same fix applied to inquiry-failure write path in `ChildDisbursementLoanEventsQueueSync` (`09295c377`).

**Rule going forward:** any path that calls a CAS service on a CLMT entity MUST NOT subsequently set fields on that entity object. Same for parent `loan_account` after `LoanAccountStateMachineService.transition()`. See [`../platform/state-machine-safety.md`](../platform/state-machine-safety.md).

### 2.3 Async-NEI-callback vs sync-NEI-inquiry-post-handler race (`c704969ec`, 2026-05-06)

**Before:** at stage-2, two threads write the queue row in close succession — (a) reactor thread running `applyClmtAndSave` after sync ST_NEI inquiry response, (b) Tomcat HTTP worker running `processInProgressCallbackForChild` from the bank's async NEI callback. With sync still uncommitted, async reads stale `NEFT_STAGE_1_SUCCESS`, fails the curStatus check at `DoGenericSyncSTPBankNeftCallBackProcessor:502` (only accepted `NEFT_STAGE_2_PENDING`), falls to else branch, updates error fields without transitioning.

**Fix:** (i) async transition condition now accepts `NEFT_STAGE_1_SUCCESS` in addition to `NEFT_STAGE_2_PENDING` — state machine still monotonic-forward (bank's NEI callback proves inquiry was issued). (ii) sync handler `applyClmtAndSave` OK branch consults `ChildClmtTerminalStateGuard.isAtOrBeyondStage` before save (was previously only consulted in the OLE catch which never fires). Both writers respect monotonic forward.

### 2.4 CLMT prep-block split + populate-before-prepare (`a6fdc1c88` + `55e58d31d`, 2026-05-06 → 05-07)

**Before:** CLMT rows were created mid-orchestration after the child-bank-call block began. Async bank callbacks could arrive before CLMT rows were committed → callback bailed silently when lookup returned null.

**Fix:** new processor `PrepareClmtRowsForChildDisbursementProcessor` runs in its own `<Transaction>` block in `mfi_orc.xml` immediately before the child-bank-call block. Each `<Transaction>` is `REQUIRES_NEW` (per `ProcessorOrchestrator.java:111` in platform-lib) so rows commit before any bank call fires.

**Follow-up bug (same week):** the prep-block split moved CLMT row creation upstream of `populateAdditionalAmountDetailsForChildDisbursementProcessor`, the only place where per-member `net_disbursed_amount` is computed. Result on QA3 parent 11850460: 23 CLMT rows committed with `data.net_disbursed_amount=null`, then `CallBankAPIForIndividualChildLoanDisbursementProcessor` silently early-returned (empty `totalAmount` → `IS_BANK_CALL_FAILED=TRUE`, return — **with no log**) for every child leg. Fix: `PrepareClmtRowsForChildDisbursementProcessor.process()` now invokes `populateAdditionalAmountDetailsForChildDisbursementProcessor.execute(executionContext)` before `CreateClmtLoanAccountEventsProcessor`. Defense-in-depth: silent early-return now logs `LOGGER.error(...)`.

### 2.5 Bank parser NPE → CRR drop close (`7ad7a0adf`, 2026-05-07)

**Before:** bank's NEFT v2 inquiry returned `{"faxml":{"errorCode":"NDF","errorDesc":"Batch details not found..."}}` (no `paymentlist`). HDFC infra JAR's `NeftTransactionStatusInquiryV2.doServiceCall` NPE'd reading `paymentlist.get(...)`, exception unwound out of `performNeftV2InquiryWhenStage1Pending` before any CRR write. CRR not visible for the LAN; state stuck.

**Fix:** wrap `neftTransactionStatusInquiryV2`, `neftPaymentV2`, `neftPaymentV2Stage2` (parent + child inquiry) with `try { … } catch (RuntimeException) { … }` that persists CRR locally with the actual bank response, sets `IS_BANK_CALL_FAILED=TRUE`, and returns. Guarantees CRR is written and disbursement state stays put for any bank-side parser failure / malformed response.

### 2.6 Inquiry crash on pre-NEFT `disbursement_status` (`331cd8f98` / `aaecd4fb2`, 2026-05-07)

**Before:** `disburseLoan` re-trigger via `function_sub_code=DTFC_SUCCESS` after a NEFT URL failure crashed with `IllegalArgumentException: at least one fromState is required` in `saveBankErrorResponseCode`. `performNeftV2InquiryWhenNotStage1Pending` was setting `DO_TRANSACTION=FALSE` without `IS_BANK_CALL_FAILED=TRUE`, so the caller entered the NEFT-success CAS branch with `neftStageStatus=DTFC_SUCCESS`, which has no rank-1 predecessor → empty fromStates → throw.

**Fix:** mark bank-call failed in that else branch; add defensive empty-fromStates guard in both `CallBankAPIForDisbursementProcessor.saveBankErrorResponseCode` and `ChildDisbursementLoanEventsQueueSync.saveBankErrorResponseCode`.

### 2.7 NDF "batch not found" recovery (`1671a0fad`, 2026-05-07) — **state-machine rollback**

**Before:** retries from a failed bank attempt didn't reach COMPLETED. Two issues: (a) `performNeftV2InquiryWhenNotStage1Pending` else branch hard-set `DO_TRANSACTION=FALSE` for any pre-NEFT state — second `disburseLoan` from `disbursement_status=DTFC_SUCCESS` (with prior FAIL NEF CRR) silently skipped the NEFT call; (b) when bank inquiry returned `errorCode=NDF`, loan stayed pinned at `NEFT_STAGE_1_PENDING` because `rankBackwardSafeFromStates` is forward-only.

**Fix:**
- Parent inquiry router now allows `DO_TRANSACTION=TRUE` for `DTFC_SUCCESS` so retry fires fresh NEF.
- Parser-NPE catch (parent + child inquiry) sniffs raw bank response for NDF / "batch not found" via `isBankBatchNotFoundResponse` and signals rollback (`NEFT_STAGE_STATUS=DTFC_SUCCESS`, `IS_BANK_CALL_FAILED=FALSE`).
- `saveBankErrorResponseCode` (parent + child) now does **backward CAS** `fromStates=[NEFT_STAGE_1_PENDING] → DTFC_SUCCESS` when the empty-fromStates guard fires for `DTFC_SUCCESS`. Race-safe (REJECTED if a callback advanced state), then sets `IS_BANK_CALL_FAILED=TRUE` so child disbursement aborts and the next `disburseLoan` re-fires NEF cleanly.

**Implication:** the state machine is monotonic-forward EXCEPT for this one well-defined NDF rollback. If you see backward transitions in any other context, that's a bug. See [`../runbooks/disbursement-stuck.md`](../runbooks/disbursement-stuck.md) §B.1 for the runbook.

---

## 3. Death foreclosure STAGE_6 (SDCP-9301)

3 commits: `0ebb2fa4a` + `c71ea95c8` + `59e253c54` (2026-04-29 → 05-04).

**Pre-fix bug:** if a loan had pending accrual between `last_billed_date` and `death_date`, STAGE_6 would book it to `INT_ACC_NOT_DUE`, then DFC's loss leg would credit `LOSSES_INT_WAIVED_AIR` (waived-not-billed) for the same slice. Slice sat unbilled forever in `INT_ACC_NOT_DUE`; loss waiver mis-classified.

**Fix (in `DeathForeclosureInsuranceWriter.java`):**
1. Force-bill nested call: `postTransaction(BILLING-NORMAL_BILLING)` with PRIN=0, INT=slice — moves slice from `INT_ACC_NOT_DUE` → billed (`REG_EMI_BI`).
2. EC save/restore around the nested call so DFC's own posting sees its own globals, not BILLING's.
3. Clamp slice start: `effectiveAccrualStart = max(last_billed_date, death_date)`. Prevents pre-death BPI (already settled at disbursement) from being re-accrued.

**Result:** post-DFC ledger has `INT_ACC_NOT_DUE = 0`; trial balance net-zero; customer ledger correct. Full narrative in [`../flows/loan-servicing/death-foreclosure.md`](../flows/loan-servicing/death-foreclosure.md) STAGE_6 section.

---

## 4. Dup-CRN error code: `134067` → `134497`

Commit `d358a9034` (`SDCP | Return friendly error for duplicate client_reference_number on loanRepayment`).

**Before:** `clientReferenceNumberDedupProcessor.execute()` threw `NovopayFatalException("134067")` on dup-CRN. Generic error code, hard to interpret in operator UI.

**Now:** throws `134497`. Same logic, friendlier code. Mapping in front-end dictionaries and runbooks updated. **Brain doc `engines/posting-engine.md` says `134497 (3.3.1.0.1+) / 134067 (3.2.8.4.1)`** — both forms appear in code searches when looking across branch history.

---

## 5. `runEODJobs` orchestration scope (DOC FIX, no code change)

This was a long-running misunderstanding in the brain docs. Verified by reading [`MfiRunEODJobsProcessor.java:23–28`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/custom/mfi/jobs/processor/MfiRunEODJobsProcessor.java#L23):

`runEODJobs` invokes only **5 child Requests** sequentially:
1. `loanAccountDpdCalcJob`
2. `loanAccountAssetCriteriaJob`
3. `loanAccountAssetClassificationJob`
4. `penalInterestAccrualCalculation`
5. `penalInterestAccrualBooking`

Billing, interest accrual + posting, derived fields refresh, trial balance calc + zeroisation, post-EOD reports — all run on **independent `mfi_batch.batch_schedule` cron rows**. They do NOT cascade through `runEODJobs`.

**Implication for ops:** "EOD didn't run" is ambiguous. Diagnose per-job from `mfi_batch.batch_schedule`. See updated [`system/07-batch-atlas.md`](../system/07-batch-atlas.md) and [`accounting/03-batch-dependency.md`](03-batch-dependency.md).

---

## 6. SI Manual Presentation cosmetic fixes (no flow change)

Commits `3ce59eaf2`, `562957eb8`, `a59d96066` — customer-name rendering on the SI manual hold marking screen + read optimization. **No accounting flow impact.** Mention only because they appear in the 3.3.1.0.1 commit log.

---

## 7. Platform-lib deltas (`upstream/mfi_integration_v3.3.1.0.0` → `upstream/mfi_integration_v3.3.1.0.1`)

8 commits, ~190 lines changed across 11 files. Three substantive items for accounting:

1. **`4cb437b28` Atomic `setIfAbsent` on ICacheClient** — used by disbursement dedup key `dl<...>` to close the race between two pods trying to set the in-flight gate. Currently invoked from `LmsMessageBrokerConsumer:111` (which still passes no TTL — separate gap).
2. **Kafka config from master-data (`13c3cb1f7` + `b96de4874` + `08769aa2e`)** — Kafka topic routing now reads from master-data instead of local config. Infra-wide; no business-logic impact on accounting flows.
3. **Reporting RowMapper additions (`87353a235`, `e6fdc96f2`)** — Finnone previous-account columns. Not used by accounting flows.

---

## 8. Task-id-orphan fix (`b80a318f9`, backport from 3.2.8.4)

Original commit `154b500c0` on `SDCP-fix-task-id-orphan-3.2.8.4`. Backported to 3.3.1.0.1 in `b80a318f9`.

**Symptom:** loan stuck in `*_FREEZE` with `task_id=NULL` because flow updated `loan_status` BEFORE creating the task. If task service was unavailable, the loan got frozen with no task to approve.

**Fix:** task creation now happens BEFORE status update. If it fails, the loan stays in its pre-FREEZE state. Existing orphans need data patch — see [`../runbooks/task-id-orphan-data-patch.md`](../runbooks/task-id-orphan-data-patch.md).

---

## 9. What did NOT change

- `postTransaction` engine algorithm — Phase 1 + Phase 2 unchanged.
- Repayment appropriation algorithm — `RepaymentApproppriationProcessor` unchanged on this branch.
- `loan_account_events_queue` schema — unchanged; CAS / `patchJsonFields` operate on the same row shape.
- BOD orchestration — unchanged.
- SHG/JLG fan-out behaviour — replayer logic unchanged; CLB events still bulk-replayed once, others per-child.
- Auto-closure logic — unchanged.

---

## 10. Test artifacts on QA3 referenced in commit messages

| LAN | Issue | Fixed by |
|---|---|---|
| 6009683725 child 19 | Hibernate auto-flush race; row stuck NEFT_STAGE_2_PENDING with `updated_on` from outer-tx commit | `4c339282f` |
| 6009683325 child 2 | Async-NEI vs sync-NEI race; row stuck with `data.external_error_message="NEI Initiated…"` | `c704969ec` |
| 6009682925 (parent 11850460) | populate-before-prepare; 23 CLMT rows with `net_disbursed_amount=null` | `55e58d31d` |
| 6009685025 | Empty-fromStates crash on DTFC_SUCCESS retry | `331cd8f98` |
| 6009685525 | Bank parser NPE → CRR drop | `7ad7a0adf` |

Useful for `lan-360` regression checks if any of these reappear post-deploy.
