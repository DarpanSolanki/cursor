## Batch posting uses time-based `client_reference_number` → replay / partial-progress can double-post

### Symptom class
- A batch step is retried/replayed (manual rerun, scheduler retry, partition retry).
- The step posts financial transactions via `postTransaction` (or equivalent) but uses a **time-based** `client_reference_number` (e.g., `System.currentTimeMillis()` / `new Date().getTime()`).
- On replay, the dedupe guard (`ClientReferenceNumberDedupProcessor` in `postTransaction`) does **not** fire because the client ref changed, so the same business action can be posted again if upstream state is not strictly idempotent.

### Why this happens
The platform dedupes real-time posting primarily by `client_reference_number`. If a batch generates that value from the clock instead of a deterministic business key (account + business_date + stage), then:
- partial progress (some DB state committed) + rerun can create a *new* client ref
- the system treats it as a new transaction

### Where this exists (examples; verify per flow before changing)
- `novopay-platform-accounting-v2/.../InterestAccrualBookingBatchService.java` (time-based client ref; already captured as a High risk gap)
- `novopay-platform-accounting-v2/.../LoanAccountBillingBatchService.java` (client ref includes `new Date().getTime()`)
- `novopay-platform-accounting-v2/.../LoanAccountAssetCriteriaBatchProcessor.java` (client ref includes `new Date().getTime()`)
- `novopay-platform-accounting-v2/.../loan/deathforeclosure/writer/DeathForeclosureInsuranceWriter.java` uses `System.currentTimeMillis()` before calling `postTransaction` in the DCF posting flow

### How to prove risk (DB + logs)
- Identify two `transaction_master` rows with the same business meaning but different `client_reference_number` created by reruns.
- Correlate by account / transaction_type / value_date / job_time and timestamps.

### Mitigation direction
- Prefer deterministic client ref seeds: `${accountId|LAN}_${businessDate}_${batchName}_${stage}` (+ counter only on definitive FAIL).
- If deterministic ref cannot be adopted immediately, enforce stronger idempotency using a business-keyed “already-posted” marker (table row / status) that is checked before posting.

