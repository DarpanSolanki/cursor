# State machine safety — CAS contract reference

> **Read this before** writing or reviewing any code that updates `loan_account.disbursement_status`, `loan_account.loan_status`, or `loan_account_events_queue.data->>'disbursement_status'`. The CLAUDE.md hard rule (§3) lives here in detail.

**Authoritative on:** `novopay-platform-accounting-v2 mfi_integration_v3.3.1.0.1`. Earlier versions had different patterns; rules below describe the post-`4c339282f` design (2026-05-07).

---

## 1. Two CAS services. Both `@Transactional(REQUIRES_NEW)`. Both atomic.

| Service | Owns | Method | Effect |
|---|---|---|---|
| [`ChildClmtStateMachineService`](../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/disbursement/service/ChildClmtStateMachineService.java) | `loan_account_events_queue.data->>'disbursement_status'` (CLMT rows for SHG/JLG child legs) | `transition(ChildClmtTransitionRequest)` | Atomic CAS via `@Modifying` UPDATE … WHERE `(data::jsonb)->>'disbursement_status' = ANY(string_to_array(:fromStatesCsv, ','))`. Returns `APPLIED` (1 row) or `REJECTED` (0 rows). |
| | (same row) | `patchJsonFields(rowId, patches, filler2, updatedBy)` | State-agnostic — for advisory/error/info writes. Throws `IllegalArgumentException` if `patches` contains `disbursement_status`. **Use this for everything that is not a state transition.** |
| [`LoanAccountStateMachineService`](../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/disbursement/service/LoanAccountStateMachineService.java) | `loan_account.disbursement_status` (parent JLG/INDL flow) | `transition(LoanAccountTransitionRequest)` | Atomic CAS on the parent column. Same APPLIED / REJECTED contract. |

Both rejects on race-loss. Caller must check the result.

---

## 2. The hard rule

**After a CAS returns APPLIED, do NOT call setters on the entity object you used to compute the request.**

That entity is loaded by `PerformChildLoanBankDisbursementProcessor:74` (or analog) at the start of `disburseLoan` and stays in the outer NP-Executor thread's persistence context. `AbstractBaseEntity` has **no `@PreUpdate` / no `@UpdateTimestamp`** ([file:line](../trustt-platform-accounting/src/main/java/in/novopay/accounting/common/entity/AbstractBaseEntity.java#L35-L44)) — so the in-memory `updated_on` keeps its load-time value forever.

When the outer `disburseLoan` transaction commits, Hibernate dirty-checks the entity, sees mutations on `data` / `event_status` / `filler_2`, and emits a plain `UPDATE` that **rewrites the row with the in-memory state including the stale `updated_on`** — undoing any later async-callback CAS to `COMPLETED`.

This is the bug closed by `4c339282f` (2026-05-07). The auto-flush wins because Hibernate runs at outer-tx commit time, well after any inner CAS already committed in its own `REQUIRES_NEW` transaction.

### How to obey

| What you want to do | How |
|---|---|
| Transition state | `service.transition(req)`. Check `result == APPLIED` before treating it as success. |
| Update advisory fields (filler_2, error message, etc.) without changing state | `service.patchJsonFields(rowId, patchesMap, filler2, updatedBy)` |
| Read the current persisted state | Re-fetch via DAO. Don't rely on the local entity. |
| Update entity fields needed by **later code in the same thread** (rare) | Re-fetch the entity from DAO after the CAS. The fresh fetch is fine to mutate (until the next CAS). |

### Anti-patterns that look correct but aren't

```java
// WRONG — auto-flush will revert the CAS
service.transition(req);
entity.setFiller3(utr);
entity.setExternalErrorMessage(msg);
dao.save(entity);

// WRONG — even if you don't call dao.save, dirty-checking still flushes at outer commit
service.transition(req);
entity.setFiller3(utr);
return; // <-- outer commit will UPDATE the row with stale updated_on

// CORRECT
ChildClmtTransitionRequest req = ChildClmtTransitionRequest.builder()
    .id(entity.getId())
    .fromStatesCsv(fromStates)
    .toState(toState)
    .filler3(utr)        // <-- pass to CAS
    .updatedBy(user)
    .build();
ChildClmtTransitionResult result = service.transition(req);
if (result == APPLIED) { /* proceed */ }
```

---

## 3. Forward-only state machine — with one exception

The rank table (in `ChildClmtTerminalStateGuard.DISBURSEMENT_STATUS_RANK`):

```
DTFC_SUCCESS(1) < NEFT_STAGE_1_PENDING(2) < NEFT_STAGE_1_SUCCESS(3) < NEFT_STAGE_2_PENDING(4) < COMPLETED(5)
```

`rankBackwardSafeFromStates(toState)` returns all states strictly lower in rank than `toState` — used to derive the `fromStates` CSV for forward CAS. COMPLETED has a carve-out (returns all states for idempotent terminal).

**The one allowed backward transition:** NDF / "batch not found" recovery (`1671a0fad`, 2026-05-07). When a NEFT inquiry returns NDF, parent `saveBankErrorResponseCode` and child `ChildDisbursementLoanEventsQueueSync.saveBankErrorResponseCode` perform a **backward CAS** `fromStates=[NEFT_STAGE_1_PENDING] → DTFC_SUCCESS`. Race-safe (REJECTED if a callback advanced state in parallel), then sets `IS_BANK_CALL_FAILED=TRUE` so child disbursement aborts and the next `disburseLoan` retry fires fresh NEF.

**If you see a backward transition anywhere else, that's a bug.**

---

## 4. UTR persistence

Canonical column is `loan_account_events_queue.filler_3` (commit `7ab965fe3`).

- **Sync writer:** [`ChildNeftClmtPostBankService.applyClmtAndSave:104`](../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/disbursement/service/ChildNeftClmtPostBankService.java#L104) — passes `.filler3(utrNumber)` in the CAS request builder. **Never** does `entity.setFiller3(utr)` directly (would auto-flush-revert).
- **Async writer:** [`DoGenericSyncSTPBankNeftCallBackProcessor.processLoanAccountForChildLoans:262`](../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/disbursement/processor/DoGenericSyncSTPBankNeftCallBackProcessor.java#L262) — same.
- **Reader:** `BookChildLoanProcessor.java:412` copies `event.getFiller3()` to `loan_disbursement_mode_details.utr_number`.

---

## 5. Outstanding gaps

- **Child MFT FAIL writer not migrated** — `PostMFTChildLoanBankDisbursementProcessor` FAIL branch still does `dao.save(row)` (legacy pre-CAS pattern). Auto-flush race remains for MFT-only flows. Migration deferred pending regression testing — track in [`../gaps-and-risks.md`](../gaps-and-risks.md).
- **No `@Version` on `LoanAccountEventsQueueEntity`** — by design (CAS is the locking mechanism). If you ever add `@Version`, the SQL CAS will fight the JPA optimistic lock — both must be re-evaluated together.
- **Other event queue types (PRTPRE, RSTCRE, REOPN, etc.)** — `childLoanEventProcessingBatchJob` updates `event_status` with a plain UPDATE (not CAS). Multi-writer scenarios for non-CLMT events are not yet protected.
- **`loan_account.loan_status` updates outside `LoanAccountStateMachineService`** — many flows (foreclosure, write-off, restructure, rebooking) still call `dao.save(loanAccount)` after `setLoanStatus(...)`. These flows are **maker-checker gated** and run inside their own approval-bound transaction, so the multi-writer race is not currently observed. But the same auto-flush trap applies if any of these ever interact with a CAS service.

---

## 6. Cross-references

- [`../engines/disbursement-engine.md`](../engines/disbursement-engine.md) §4.8 — full call-site map for both state-machine services.
- [`../engines/disbursement-engine.md`](../engines/disbursement-engine.md) §4.9 — async callback handler details + race fixes.
- [`../accounting/11-deltas-3.3.1.0.1.md`](../accounting/11-deltas-3.3.1.0.1.md) §2 — full timeline of the NEFT v2 race series.
- [`../runbooks/disbursement-stuck.md`](../runbooks/disbursement-stuck.md) §B — symptom-to-cause map.
- Memory: `feedback_no_inmem_mutation_after_cas` — the user's preference / hard rule.
