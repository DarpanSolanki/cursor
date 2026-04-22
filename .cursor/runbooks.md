# Runbooks — High severity gaps (this codebase)

This file is intended to be **2am-usable**: concrete failure modes, what to look for, and what to do.  
Cross-reference: `.cursor/gaps-and-risks.md`. Related diagrams: `.cursor/architecture.mmd`, `.cursor/accounting-flow.mmd`.

---

## LOS disbursement sync no-ops if `entity_type` missing

- **What breaks (failure mode + file path)**  
  LOS consumes `los_lms_disbursement_sync`, but `DisbursementSyncService` short-circuits when `entity_type` is absent → LOS does not persist `failure_reason` / state update even though Accounting already published a terminal status.  
  - File: `novopay-mfi-los/src/main/java/in/novopay/los/service/disbursement/DisbursementSyncService.java`

- **Early warning signs (logs/metrics to watch)**  
  - Symptom: Accounting logs show SUCCESS/FAILED publish, but LOS row does not change.  
  - Watch: Kafka consumer lag on `los_lms_disbursement_sync` + LOS consumer logs around sync processing for the same `external_ref_number`.

- **Immediate mitigation (2am, step-by-step)**  
  - Step 1: Copy the `external_ref_number`, `tenant_code`, and `status` from the message (or from Accounting logs).  
  - Step 2: Confirm Accounting truth: check `mfi_accounting.loan_account` for `disbursement_status` and `loan_status`; check CRR for bank leg status.  
  - Step 3: Confirm LOS truth: find LOS disbursement record for the same `external_ref_number`; verify it did not persist failure/success.  
  - Step 4: If Accounting is terminal but LOS is stale: run the **LOS-side manual sync/patch** procedure (ops tool / SQL patch) to update LOS state from the message **without re-triggering bank leg**.  
  - Step 5: If LOS must be replayed: republish the sync message (same `external_ref_number`) **after** fixing payload contract (avoid infinite no-op replay).

- **Permanent fix (what to build + ETA)**  
  - Make sync contract robust: producer always sends `entity_type` (additive field) **and** LOS consumer tolerates missing field by falling back to a safe default branch.  
  - Add contract tests: “sample message fixture” checked into both repos.  
  - Effort: **2–3 days** + cross-module QA.

- **Files to check (exact paths)**  
  - `novopay-mfi-los/src/main/java/in/novopay/los/service/disbursement/DisbursementSyncService.java`  
  - `novopay-mfi-los/src/main/java/in/novopay/los/kafka/DisbursementSyncConsumer.java`  
  - `novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java`  
  - `system_brain/edge_cases/disbursement_sync_entity_type_missing.md`

- **Related accounting flows impacted**  
  - Disbursement async pipeline (`disburse_loan_api_` → `disburseLoan` → `los_lms_disbursement_sync`)

- **Business impact**  
  - **SLA breach + operational rework**: LOS shows wrong status; agents reinitiate; can cause duplicate manual interventions and customer impact.

---

## Accounting → LOS sync payload does not include `entity_type`

- **What breaks (failure mode + file path)**  
  Accounting publishes `los_lms_disbursement_sync` JSON without `entity_type`; LOS expects it for certain update branches → consumer can skip update → LOS and Accounting diverge.  
  - File: `novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java` (payload build in `sendResultMessageToKafka`)

- **Early warning signs (logs/metrics to watch)**  
  - Accounting log lines indicating publish success (and for failures: error_code / error_message) but LOS DB unchanged.  
  - LOS consumer logs show processing but no update (or repeated reprocessing with no state change).

- **Immediate mitigation (2am, step-by-step)**  
  - Step 1: Verify whether message contains `entity_type`. If not, do **not** keep replaying blindly.  
  - Step 2: If status is FAILED, capture `error_code` and map to which processor likely failed.  
  - Step 3: Patch producer to include `entity_type` (hotfix), deploy, then republish only affected `external_ref_number`s.  
  - Step 4: Until hotfix lands: do controlled LOS patch for those rows (update failure reason from Accounting payload) to unblock ops without re-triggering money movement.

- **Permanent fix (what to build + ETA)**  
  - Additive contract: include `entity_type`, and update `.cursor/event-registry.md` payload schema for this topic.  
  - Add LOS-side validation: if missing, route to “generic sync update” branch (still persist status/error).  
  - Effort: **1–2 days** engineering + **1 day** QA.

- **Files to check (exact paths)**  
  - `novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java`  
  - `novopay-mfi-los/src/main/java/in/novopay/los/service/disbursement/DisbursementSyncService.java`

- **Related accounting flows impacted**  
  - Disbursement async completion → LOS mirror sync

- **Business impact**  
  - **Data inconsistency** across systems used for customer servicing; can lead to wrong user actions and reconciliation load.

---

## Disbursement Redis in-flight key has no TTL (LOS producer)

- **What breaks (failure mode + file path)**  
  LOS sets an in-flight Redis key and relies on cleanup; if the JVM crashes between set/remove, the key persists forever → subsequent disburse requests are skipped.  
  - File: `novopay-mfi-los/src/main/java/in/novopay/los/util/DisburseLoanAPIUtil.java`

- **Early warning signs (logs/metrics to watch)**  
  - Disburse attempts that immediately “skip” / “already in progress” without producing new Kafka messages.  
  - Redis observation: key exists with **no TTL** for the affected `external_ref_number`.

- **Immediate mitigation (2am, step-by-step)**  
  - Step 1: Confirm there is **no active in-flight disburse** for that key (check running consumers, recent logs).  
  - Step 2: Confirm Accounting did not already complete the disbursement (avoid duplicate money movement).  
  - Step 3: Delete only the specific stale in-flight key (tenant-scoped DB index) and re-trigger the flow once.  
  - Step 4: If the loan is already ACTIVE/COMPLETED in Accounting, do not retrigger; instead run LOS sync remediation.

- **Permanent fix (what to build + ETA)**  
  - Add TTL (>\(max orchestration time + buffer\)) + refresh/heartbeat, or fencing token.  
  - Effort: **2 days** + chaos/replay test.

- **Files to check (exact paths)**  
  - `novopay-mfi-los/src/main/java/in/novopay/los/util/DisburseLoanAPIUtil.java`  
  - Redis config for LOS DB index

- **Related accounting flows impacted**  
  - Async disbursement producer side (no Kafka emission)

- **Business impact**  
  - **Funding blocked**: disburse never happens until manual Redis surgery; SLA breach.

---

## Disbursement Redis in-flight key has no TTL (Accounting consumer)

- **What breaks (failure mode + file path)**  
  Accounting consumer sets `dl...` key in Redis accounting DB index and uses it as in-flight lock; crash mid-orchestration leaves key without TTL → consumer skips forever.  
  - File: `novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java`

- **Early warning signs (logs/metrics to watch)**  
  - Exact log message: `Request is already in processing, skipping this record with cacheKey: {}`  
  - Also: `Skipping disbursement - loan already ACTIVE (disbursed) for external ref number: {}` (should be terminal-safe skip)  
  - Redis: `dl...` keys present with no TTL in `RedisDBConfig.ACCOUNTING` index

- **Immediate mitigation (2am, step-by-step)**  
  - Step 1: Check DB for loan terminal state first: if ACTIVE + disbursement_status=COMPLETED, **do not** replay bank leg.  
  - Step 2: If not terminal and key is stale: remove only the specific `dl...` key and the paired `originalCacheKey`.  
  - Step 3: Replay the Kafka message (or trigger LOS to republish) once, and monitor `sendResultMessageToKafka` result.  
  - Step 4: If consumer keeps re-locking: inspect exception in consumer logs; fix underlying fatal error before repeated retries.

- **Permanent fix (what to build + ETA)**  
  - Add TTL on the in-flight key; store completion marker in DB to gate replays; unify TTL behavior with LOS.  
  - Effort: **2 days**.

- **Files to check (exact paths)**  
  - `novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java`  
  - `novopay-platform-lib/infra-cache/.../NovopayCacheClient` implementations

- **Related accounting flows impacted**  
  - Async disbursement consumer path (`disburse_loan_api_`)

- **Business impact**  
  - **Funding delays** + customer dissatisfaction; potential duplicate attempts by ops if not handled carefully.

---

## Broad Redis `flushDb()` helper exists

- **What breaks (failure mode + file path)**  
  A call to `RedisCacheClient.flushDb()` can wipe an entire Redis DB index used for locks/dedupe/sessions → mass idempotency failures and inconsistent system behavior.  
  - File: `novopay-platform-lib/infra-cache/src/main/java/in/novopay/infra/cache/RedisCacheClient.java`

- **Early warning signs (logs/metrics to watch)**  
  - Sudden drop in Redis key count; sudden spike in duplicate processing / STAN dedupe failures.  
  - Multi-service blast radius within minutes after a deploy touching cache code.

- **Immediate mitigation (2am, step-by-step)**  
  - Step 1: Identify the deploy or job that invoked flush; stop/rollback it immediately.  
  - Step 2: Freeze consumers that rely on Redis dedupe to avoid duplicate postings.  
  - Step 3: Restore Redis from backup if available; otherwise warm-up minimal critical keys (sessions, STAN, locks) as per ops playbook.  
  - Step 4: Run reconciliation checks on disbursement/repayment postings for duplicate triggers in the window.

- **Permanent fix (what to build + ETA)**  
  - Remove or hard-gate `flushDb()` in production (break-glass only); implement safe delete-by-prefix with limits.  
  - Effort: **1–2 days** + repo-wide cleanup.

- **Files to check (exact paths)**  
  - `novopay-platform-lib/infra-cache/src/main/java/in/novopay/infra/cache/RedisCacheClient.java`  
  - All call sites of `flushDb(`

- **Related accounting flows impacted**  
  - Any Redis-backed idempotency: disbursement, consumer dedupe, gateway STAN, batch retries

- **Business impact**  
  - **Money at risk** via duplicate processing; platform outage; audit incident.

---

## Interest accrual posting uses time-based `client_reference_number`

- **What breaks (failure mode + file path)**  
  Interest accrual batch derives `client_reference_number` from time; on partial failure/retry it can generate a different CREF → dedupe may not fire → double-posting.  
  - File: `novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/batchnew/interest/interestaccrualbooking/InterestAccrualBookingBatchService.java`

- **Early warning signs (logs/metrics to watch)**  
  - Duplicate `transaction_master` for same loan/value_date/txn_type with different CREFs.  
  - Reconciliation mismatch between expected accrual totals and posted totals.

- **Immediate mitigation (2am, step-by-step)**  
  - Step 1: Stop the batch job.  
  - Step 2: Identify the run window and list affected loans.  
  - Step 3: Verify duplicates in DB and prepare reversal entries before restart.  
  - Step 4: Restart only after ensuring deterministic idempotency keys or after manually marking processed items.

- **Permanent fix (what to build + ETA)**  
  - Deterministic CREF derived from stable tuple `(account_id, value_date, txn_type, run_id)`; persist batch checkpoints.  
  - Effort: **3–5 days** including regression on large volumes.

- **Files to check (exact paths)**  
  - `.../InterestAccrualBookingBatchService.java`  
  - `novopay-platform-accounting-v2/deploy/application/orchestration/product_transaction_orc.xml` (`clientReferenceNumberDedupProcessor`)

- **Related accounting flows impacted**  
  - EOD interest accrual posting → `postTransaction`

- **Business impact**  
  - **Money/state correctness risk**: loan balances wrong; GL mismatch; audit exposure.

---

## Proactive excess refund writer swallows exceptions

- **What breaks (failure mode + file path)**  
  Writer catches and swallows exceptions → batch step can appear successful while data is partially updated; rerun can duplicate.  
  - File: `novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/batchnew/refund/proactiveexcessamountrefund/ProactiveExcessAmountRefundItemWriter.java`

- **Early warning signs (logs/metrics to watch)**  
  - Batch job status SUCCESS with suspiciously low processed counts; missing ERROR logs per failed item.  
  - Customer complaints for missing refunds.

- **Immediate mitigation (2am, step-by-step)**  
  - Step 1: Stop the job.  
  - Step 2: Identify impacted staging rows and compare against posted transactions (by CREF / reference numbers).  
  - Step 3: Re-run only after ensuring writer fails the chunk on error or after isolating bad rows.

- **Permanent fix (what to build + ETA)**  
  - Fail-fast chunk policy; DLQ for bad records; per-record metrics and alerts.  
  - Effort: **2–3 days**.

- **Files to check (exact paths)**  
  - `.../ProactiveExcessAmountRefundItemWriter.java`  
  - Batch job config for proactive refunds

- **Related accounting flows impacted**  
  - Excess refund / refund rebooking flows

- **Business impact**  
  - **Customer money movement delay**; silent operational debt; escalations.

---

## HTTP internal client has no retry/circuit breaker

- **What breaks (failure mode + file path)**  
  Internal HTTP calls have no platform retry/backoff/circuit breaker; in a multi-service financial flow this can create **partial progress** (one service commits, downstream call fails) → inconsistency.  
  - File: `novopay-platform-lib/infra-http-client/src/main/java/in/novopay/infra/api/client/NovopayHttpAPIClient.java`

- **Early warning signs (logs/metrics to watch)**  
  - Spike in downstream `5xx` + upstream fatal exceptions without retries.  
  - “Stuck” states where upstream DB shows progressed status but downstream never received/processed corresponding request.

- **Immediate mitigation (2am, step-by-step)**  
  - Step 1: Identify the failing downstream dependency (which service + apiName).  
  - Step 2: Stop the caller trigger if it is high-volume (consumer/batch) to prevent mass partial progress.  
  - Step 3: Pull a sample of correlation keys (external_ref_number / stan) from logs.  
  - Step 4: Compare state across both services’ DBs for the same keys.  
  - Step 5: Apply compensating action: replay idempotent call (safe) or run manual sync/patch for non-idempotent legs.  
  - Step 6: Resume traffic only after downstream is healthy or circuit protection is in place.

- **Permanent fix (what to build + ETA)**  
  - Resilience in `infra-http-client`: retries for idempotent requests, circuit breaker + bulkhead + timeouts; enforce idempotency keys for writes.  
  - Effort: **5–10 days** (platform-lib + service validation).

- **Files to check (exact paths)**  
  - `novopay-platform-lib/infra-http-client/src/main/java/in/novopay/infra/api/client/NovopayHttpAPIClient.java`  
  - Call sites across services (see `.cursor/service-contracts.md`)

- **Related accounting flows impacted**  
  - Any accounting flow calling Actor/Payments/Masterdata/Task during disbursement/repayment/posting and any callback/inquiry path

- **Business impact**  
  - **Data inconsistency + money-state drift**; reconciliation effort; SLA breach and manual corrections.

---

## Gradle Novopay plugin classpath vs published dependency-mgmt version mismatch

- **What breaks (failure mode + file path)**  
  Services pin one plugin patch, but dependency-mgmt publishes another → resolved artifacts drift across CI/prod → binary incompatibility and runtime surprises.  
  - Files: `novopay-platform-accounting-v2/build.gradle`, `novopay-platform-dependency-mgmt/build.gradle`

- **Early warning signs (logs/metrics to watch)**  
  - NoSuchMethodError / ClassNotFound in prod after “minor” release.  
  - Local vs CI dependency trees differ.

- **Immediate mitigation (2am, step-by-step)**  
  - Step 1: Stop promotion of new builds.  
  - Step 2: Compare `./gradlew dependencies` output between last-good and broken build.  
  - Step 3: Roll back to last known-good artifact set; align all service buildscript coordinates.

- **Permanent fix (what to build + ETA)**  
  - Central version catalog; remove hard-coded plugin versions where possible.  
  - Effort: **3–5 days**.

- **Files to check (exact paths)**  
  - All `*/build.gradle` buildscript blocks  
  - `novopay-platform-dependency-mgmt/build.gradle`

- **Related accounting flows impacted**  
  - All (platform-wide)

- **Business impact**  
  - Release instability; outages during deploy windows.

---

## (Test absence) No automated test for `LmsMessageBrokerConsumer` async disburse path

- **What breaks (failure mode + file path)**  
  No CI coverage for consumer idempotency, Redis lock cleanup, and publish-back contract → regressions ship to prod.  
  - File: `novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java`

- **Early warning signs (logs/metrics to watch)**  
  - Post-deploy spike in: `Request is already in processing, skipping this record with cacheKey:`  
  - Increased consumer lag + disbursement SLA misses.

- **Immediate mitigation (2am, step-by-step)**  
  - Step 1: Use `scripts/disburse_loan_sanity.py` against the exact build to reproduce.  
  - Step 2: If prod is impacted, pause consumer, remediate stale Redis keys (carefully), and replay limited set.  
  - Step 3: Add temporary dashboard/alerts on skip logs and Kafka lag.

- **Permanent fix (what to build + ETA)**  
  - Integration tests (embedded Kafka/Testcontainers) + deterministic fixtures.  
  - Effort: **3–5 days**.

- **Files to check (exact paths)**  
  - Consumer class + `MessageBroker.xml` topic config

- **Related accounting flows impacted**  
  - Disbursement async pipeline

- **Business impact**  
  - High Sev-1 risk; money movement delays.

---

## (Test absence) No automated test for `glBalanceZeroisation` / `reverseTransaction` / `postManualJournalEntry`

- **What breaks (failure mode + file path)**  
  Finance close and correction flows lack automated guardrails → misposting risk at statutory close.  
  - ORC: `novopay-platform-accounting-v2/deploy/application/orchestration/product_transaction_orc.xml`

- **Early warning signs (logs/metrics to watch)**  
  - TB mismatch caught late; manual UAT only once/year.

- **Immediate mitigation (2am, step-by-step)**  
  - Step 1: Freeze config changes touching these requests.  
  - Step 2: Run a small-scope dry run in UAT with reconciliation queries.  
  - Step 3: Prepare reversal/JE fallback procedure before prod run.

- **Permanent fix (what to build + ETA)**  
  - ORC integration tests asserting transaction counts and sums.  
  - Effort: **~5 days**.

- **Files to check (exact paths)**  
  - `system_brain/flows/gl_balance_zeroisation_posting.md`  
  - `system_brain/flows/reversals_manual_journal_transaction_engine.md`

- **Related accounting flows impacted**  
  - GL close; reversals; manual journal entries

- **Business impact**  
  - **Money/GL correctness** at close; audit risk.

---

## (Test absence) No automated test for DCF / insurance inbound batch posting

- **What breaks (failure mode + file path)**  
  Insurance inbound posting paths are untested → regressions only caught in reconciliation.  
  - Flow notes: `system_brain/flows/insurance_inbound_posting.md`

- **Early warning signs (logs/metrics to watch)**  
  - Staging vs posted mismatch; repeated job reruns.

- **Immediate mitigation (2am, step-by-step)**  
  - Step 1: Stop inbound jobs.  
  - Step 2: Reconcile staging rows vs posted txns.  
  - Step 3: Reverse duplicates / backfill missing postings with controlled replay.

- **Permanent fix (what to build + ETA)**  
  - Writer-level tests with anonymized fixtures; step-scope integration test.  
  - Effort: **~1 week**.

- **Files to check (exact paths)**  
  - Insurance inbound writers under `novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/batchnew/`  
  - `system_brain/flows/insurance_inbound_posting.md`

- **Related accounting flows impacted**  
  - Insurance inbound / DCF / death foreclosure insurance posting

- **Business impact**  
  - Insurance settlement errors; delayed claim processing; customer harm.

---

## Multi-node batch scheduler has no distributed leader/lock (race across batch instances)

- **What breaks (failure mode + file path)**  
  Two `novopay-platform-batch` instances can both read “not running” from DB and start the same scheduled group/job in parallel, because coordination is based on **read-checks** (`isJobRunning`) and in-JVM `synchronized` methods rather than a distributed lock/leader election.  
  - Files:  
    - `novopay-platform-batch/src/main/java/in/novopay/batch/batchschedule/daoservice/BatchScheduleService.java` (status checks)  
    - `novopay-platform-batch/src/main/java/in/novopay/batch/core/service/SchedulerCommonService.java` (starts jobs)

- **Early warning signs (logs/metrics to watch)**  
  - Duplicate “Starting job …” logs for the same `jobName` close together.  
  - Schedule flips between RUNNING/COMPLETED unexpectedly; more than one execution for same schedule window.  
  - Spring Batch tables show two executions created near-simultaneously for the same job instance/run.

- **Immediate mitigation (2am, step-by-step)**  
  - Step 1: Identify if multiple batch pods/instances are running. If yes, **scale down to 1** immediately.  
  - Step 2: Check Spring Batch execution tables for duplicate concurrent runs (same job + overlapping start times).  
  - Step 3: If duplicates exist, stop the later execution first; prevent downstream side-effects (posting, file generation, callbacks).  
  - Step 4: Reconcile side effects for the overlap window (DB writes, emitted Kafka events, generated files).  
  - Step 5: Resume scheduling only after single-instance or lock hotfix is in place.

- **Permanent fix (what to build + ETA)**  
  - Implement **leader election** or a **distributed lock** per `batchScheduleId` (DB row lock / Redis lock with TTL) before starting any group/job.  
  - Make “start decision” atomic (compare-and-set status to RUNNING) at DB level.  
  - Effort: **3–6 days** (design + implementation + multi-instance QA).

- **Files to check (exact paths)**  
  - `novopay-platform-batch/src/main/java/in/novopay/batch/batchschedule/daoservice/BatchScheduleService.java`  
  - `novopay-platform-batch/src/main/java/in/novopay/batch/core/service/SchedulerCommonService.java`  
  - `novopay-platform-batch/src/main/java/in/novopay/batch/core/service/SchedulingGroupProcessor.java`

- **Related accounting flows impacted**  
  - Any batch job that triggers accounting internal APIs (EOD jobs, interest accrual, posting, insurance inbound) — duplicate runs are a direct money/state risk.

- **Business impact**  
  - **Money at risk / double posting**, duplicate files/events, SLA breach, manual reconciliation load.

---

## Redis `set` without TTL — platform primitive (GAP-031)

- **What breaks**  
  Callers of `RedisCacheClient#set(tenant, key, value, dbIndex)` (and thin wrappers) create Redis keys **with no expiry**. Stale entries persist until manual delete/flush; memory grows if misused for high-cardinality keys.

- **Early warning**  
  Redis memory pressure; keys with `-1` TTL for unexpected prefixes; “wrong rule” behaviour after masterdata updates when cache should have expired.

- **2am mitigation**  
  Identify offending key pattern via `SCAN` / keyspace metrics; delete known-bad keys after confirming no in-flight flow depends on them; prefer targeted `remove` over `flushDb`.

- **Permanent fix**  
  Require TTL on new writes; deprecate non-TTL overload; audit call sites. See `GAP-031` in `.cursor/gaps-and-risks.md`.

- **Files**  
  `novopay-platform-lib/infra-cache/src/main/java/in/novopay/infra/cache/RedisCacheClient.java`, `NovopayCacheClient.java`, `CacheDataService.java`

---

## Paytm client logs bearer token and raw responses (GAP-032)

- **What breaks**  
  `PaytmApiClient#invokeApi` logs the **Authorization** token and full HTTP **response** at INFO → credential + PII/financial data in log stores.

- **Early warning**  
  Log volume spikes on remittance traffic; security scans flag secrets in Splunk/ELK.

- **2am mitigation**  
  Rotate Paytm credentials if logs may have leaked; restrict log access; hotfix branch to remove logging (no behaviour change).

- **Permanent fix**  
  Redact logging; correlation-id-only diagnostics. See `GAP-032`.

- **Files**  
  `novopay-platform-lib/infra-transaction-paytm/src/main/java/in/novopay/infra/transaction/paytm/common/PaytmApiClient.java`

---

## `HttpClientUtil` keystore password logging + permissive TLS (GAP-033)

- **What breaks**  
  `enableHttpsTunnelWithCertificate` logs the **keystore password** at INFO and builds an `SSLConnectionSocketFactory` with **`NoopHostnameVerifier`** and trust material loaded from the provided keystore.

- **Early warning**  
  Password strings appearing in app logs during HTTPS client init.

- **2am mitigation**  
  Rotate keystore/password if exposure suspected; limit egress; deploy patch removing password logging first.

- **Permanent fix**  
  Never log secrets; use standard CA trust + hostname verification for production paths. See `GAP-033`.

- **Files**  
  `novopay-platform-lib/infra-transaction-interface/src/main/java/in/novopay/infra/util/HttpClientUtil.java`

---

## Internal same-service API failure logs full request JSON (GAP-034)

- **What breaks**  
  `NovopayInternalAPIClient#doSameServiceCall` logs the entire formatted **request** when the nested orchestration returns `FAIL` — payloads can include PII and financial fields.

- **Early warning**  
  Large INFO log lines on internal API failures; repeated failures during incidents.

- **2am mitigation**  
  Treat logs as potentially compromised for the incident window; scrub retention if policy allows; deploy redacted logging hotfix.

- **Permanent fix**  
  Log codes, `stan`, tenant, apiName only; redact body. See `GAP-034`.

- **Files**  
  `novopay-platform-lib/infra-navigation/src/main/java/in/novopay/infra/api/client/NovopayInternalAPIClient.java`

---

## LOS Kafka null record key on `disburse_loan_api_` and other topics (GAP-038)

- **What breaks**  
  `LosMessageKafkaProducer#pushDataToKafkaQueue` passes **null** as the Kafka message key → partition assignment is not stable per loan / `external_ref_number`. Ordering and replay semantics are harder to guarantee for the async disburse pipeline.

- **Early warning**  
  Intermittent “out of order” symptoms on `disburse_loan_api_*` consumers; duplicate-looking processing across partitions after retries.

- **2am mitigation**  
  Correlate by `external_ref_number` + offset; do **not** assume partition-local ordering across the full disburse lifecycle. If stuck, use existing disburse replay/runbooks (Redis in-flight key, accounting consumer) before re-publishing.

- **Permanent fix**  
  Set a stable business key on produce; align with accounting consumer partition strategy. See `GAP-038`.

- **Files**  
  `novopay-mfi-los/src/main/java/in/novopay/los/kafka/LosMessageKafkaProducer.java`

---

## LOS disbursement sync consumer logs full payload at INFO (GAP-039)

- **What breaks**  
  `DisbursementSyncConsumer` logs the entire parsed `clientMap` at INFO after each record — sync payloads can carry identifiers and error detail suitable for log-store reconstruction.

- **Early warning**  
  High-volume INFO lines on `los_lms_disbursement_sync` consumer; DLP/security tooling hits on log exports.

- **2am mitigation**  
  Restrict log access for the incident window; treat as potential data exposure if logs are broadly retained.

- **Permanent fix**  
  Log correlation fields only; redact body. See `GAP-039`.

- **Files**  
  `novopay-mfi-los/src/main/java/in/novopay/los/kafka/DisbursementSyncConsumer.java`

---

## Payments Kafka producer null key on allocation/task topics (GAP-042)

- **What breaks**  
  `PaymentsKafkaProducer#pushDataToKafkaQueue` always uses **null** key → no per-collection / per-entity ordering guarantee on `collection_primary_allocation_*`, `collection_task_processing_*`, etc.

- **Early warning**  
  Sporadic allocation/task anomalies under load + consumer retries; lag spikes without obvious single-partition hotspot.

- **2am mitigation**  
  Triage with `np_collection_id` / `col_ext_ref_id` across all partitions; verify consumer idempotency before replaying bulk messages.

- **Permanent fix**  
  Stable key per topic contract + regression on replay. See `GAP-042`.

- **Files**  
  `novopay-platform-payments/src/main/java/in/novopay/payments/common/util/PaymentsKafkaProducer.java`

---

## Bulk collection consumer — parse failure commits with no DLQ (GAP-044)

- **What breaks**  
  `CreateOrUpdateBulkCollectionConsumer#parseData` returns **null** on JSON parse error; outer flow skips work without surfacing failure to a dead-letter path → **silent loss** of that message if offsets commit.

- **Early warning**  
  Accounting/LMS expect collections that never appear in LCS; bulk file “succeeded” from producer side.

- **2am mitigation**  
  Find the bad payload in Kafka by time/topic; re-publish fixed JSON **only** after confirming consumer will not double-apply (check idempotency on `col_ext_ref_id` / NP id). Until fixed, manual LCS row reconciliation for affected refs.

- **Permanent fix**  
  DLQ or fail-fast with capped retry; never commit without explicit policy. See `GAP-044`.

- **Files**  
  `novopay-platform-payments/src/main/java/in/novopay/payments/collections/mfi/consumer/CreateOrUpdateBulkCollectionConsumer.java`

---

## Field collection — SMS / leader notification suppressed after DB commit (GAP-045)

- **What breaks**  
  After `collectionsRepository.saveAll`, `sendSms` and `sendNotificationToLeader` run in a try/catch that **logs and swallows** all exceptions → payment/collection state can be persisted while comms never fire.

- **Early warning**  
  Customers/leaders report “no SMS” while LCS shows successful collection; Kafka notification topics quiet.

- **2am mitigation**  
  Confirm collection row state in LCS; if money path is correct, trigger manual comms/ops notification if policy allows; open ticket for notification pipeline (Kafka/SMS provider).

- **Permanent fix**  
  Durable outbox or retry queue for notifications; metrics on failure; avoid blanket swallow. See `GAP-045`.

- **Files**  
  `novopay-platform-payments/src/main/java/in/novopay/payments/collections/mfi/repository/MfiCollectionsDAOService.java`

---

## Batch `AutoScheduler` only bootstraps schedules for `getAllTenants().get(0)` (GAP-046)

- **What breaks**  
  On startup, `AutoScheduler#onLoadScheduleGroups` calls `autoSchedule` using **only the first** tenant returned by `getAllTenants()`. Other tenants may not load cron schedules until a separate manual/API path runs.

- **Early warning**  
  One tenant’s batches fire; another tenant’s EOD never triggers after deploy/restart; `batch_schedule` rows exist but no Spring `ScheduledFuture` for that tenant.

- **2am mitigation**  
  Confirm which tenant index `0` is; for affected tenants, invoke the documented schedule registration API (or restart with hotfix) so `groupScheduleNovo` runs per tenant; verify `SchedulingGroupProcessor` map has entries for each group.

- **Permanent fix**  
  Loop tenants (or config allowlist) on startup; add integration test for 2+ tenants. See `GAP-046`.

- **Files**  
  `novopay-platform-batch/src/main/java/in/novopay/batch/core/service/AutoScheduler.java`

---

## Reject-expired batch uses hardcoded `user_id` = `2` for workflow API (GAP-048)

- **What breaks**  
  `RejectExpiredBatchJobItemWriter` sets `user_id` to literal `"2"` before `taskWorkflowAPIExecutionService.callAPI` — automated rejects are attributed to user 2 in audit trails.

- **Early warning**  
  Compliance asks “who rejected”; all auto-expiry traces to the same user id; mismatch with real system account.

- **2am mitigation**  
  Do not change historical rows without approval; document incident window; use dedicated system user id in config for new deploys after fix.

- **Permanent fix**  
  Configurable system user per tenant; verify orchestration/audit processors. See `GAP-048`.

- **Files**  
  `novopay-platform-task/src/main/java/in/novopay/batch/writer/RejectExpiredBatchJobItemWriter.java`

---

## Batch scheduler threads retain `ThreadLocalContext` tenant (GAP-049)

- **What breaks**  
  `ScheduleBatchGroupExecutor`, `DirectGroupJobExecutor`, and `DirectJobExecutor` set `ThreadLocalContext.setTenant` but **do not clear** tenant in `finally`. Only `MDC.clear()` in some paths. Pooled scheduler/worker threads can carry the **wrong tenant** into the next runnable.

- **Early warning**  
  Intermittent wrong-tenant `job_time`, Redis masterdata key delete, or internal API calls after a multi-tenant batch window.

- **2am mitigation**  
  Reduce to single active batch node if cross-tenant symptoms appear; bounce JVM to clear thread locals (short-term); capture logs with `tenant` MDC vs actual schedule tenant.

- **Permanent fix**  
  `try/finally { ThreadLocalContext.clear(); MDC.clear(); }` on all scheduler runnables and async job workers. See `GAP-049`.

- **Files**  
  `novopay-platform-batch/src/main/java/in/novopay/batch/core/service/ScheduleBatchGroupExecutor.java`  
  `novopay-platform-batch/src/main/java/in/novopay/batch/core/service/DirectGroupJobExecutor.java`  
  `novopay-platform-batch/src/main/java/in/novopay/batch/core/service/DirectJobExecutor.java`  
  `novopay-platform-batch/src/main/java/in/novopay/batch/core/service/SchedulerCommonService.java` (`setCompletionStatus`)

---

## Finnone collection task CREATE_PTP branch — broken `task_id` guard (GAP-051)

- **What breaks**  
  `processForCreatePtp` uses `isNotEmpty(taskId) && "null".equalsIgnoreCase(taskId)` — normal numeric task ids never satisfy this; completion update block is effectively dead; `Long.valueOf("null")` would throw if ever hit.

- **Early warning**  
  Finnone PTP messages processed but prior task never marked `COMPLETED`; duplicate or stuck tasks in task service.

- **2am mitigation**  
  Identify affected `task_id` / `stan` in Kafka; manually reconcile task status if business approves; replay only after fix to avoid inconsistent duplicates.

- **Permanent fix**  
  Correct null/blank logic; unit tests for CREATE_PTP payloads. See `GAP-051`.

- **Files**  
  `novopay-platform-task/src/main/java/in/novopay/task/mfi/consumer/FinnoneCollectionTaskCreationConsumer.java`

---

## `rejectExpiredBatchJob` job bean config uses `chunk = Integer.MAX_VALUE` (GAP-053)

- **What breaks**  
  `RejectExpiredTasksBatchJobConfig#getJobBeanConfigParameters` sets chunk to `Integer.MAX_VALUE` for `setUpJobAdvanceV2` — risk of extreme chunk/transaction scope vs the step builder path that uses `WORKER_CHUNK_SIZE`.

- **Early warning**  
  Reject-expired job OOM, long TX timeouts, or partial writes across large partitions.

- **2am mitigation**  
  Pause schedule for the job; reduce chunk via `batch_job_parameter` / DB if supported; scale memory only as stopgap.

- **Permanent fix**  
  Align chunk with platform constants; confirm production code path (`buildJobForTenant` vs advance setup). See `GAP-053`.

- **Files**  
  `novopay-platform-task/src/main/java/in/novopay/batch/config/RejectExpiredTasksBatchJobConfig.java`

---

## API Gateway — permission check skipped when `api_usecase_mapping` row missing (GAP-054)

- **What breaks**  
  `AuthorizationCheckFilter` only calls `checkPermissionByUsecase` when a DB mapping exists for `apiName` + `function_code` + `function_sub_code`. Missing row ⇒ request proceeds with session/client auth only ⇒ **default-allow** for that tuple.

- **Early warning**  
  New API deployed without mapping row; pen-test finds callable endpoints without role alignment; `api_usecase_mapping` gaps after data refresh.

- **2am mitigation**  
  Insert mapping rows or add API to deny-by-default list; temporarily block route at WAF/ingress if abuse suspected; audit recent access logs by `apiName` + user_id.

- **Permanent fix**  
  Fail closed when mapping absent (except explicit public list); CI validation of mapping coverage. See `GAP-054`.

- **Files**  
  `novopay-platform-api-gateway/src/main/java/in/novopay/apigateway/filter/AuthorizationCheckFilter.java`

---

## API Gateway `/forward/*` bypasses standard filters + logs bodies at INFO (GAP-055)

- **What breaks**  
  `RequestForwardController` is **not** under `/api/*` filter registrations — no session validation, client auth, STAN dedupe, rate limit, or `AuthorizationCheckFilter` on that path. `RequestForwardProcessor` logs full headers and body at INFO.

- **Early warning**  
  Unexpected traffic to `/forward/json|xml/...`; spikes in downstream systems from forwarded URLs; large INFO logs containing request payloads.

- **2am mitigation**  
  Block `/forward/*` at load balancer if not required; review `request_forward` table for dangerous targets; rotate secrets if logged; restrict network to trusted callers.

- **Permanent fix**  
  Apply same filter chain or dedicated mTLS + signed requests; redact logs; least-privilege forward targets. See `GAP-055`.

---

## RESOLVED — Child MFT CRR response-fidelity mismatch on webclient error path (GAP-061)

- **What breaks (failure mode + file path)**  
  Child MFT post-processor decides CRR status from callback `apiResponse` but stores CRR `response` from shared `ExecutionContext.response`. On transport failures (`Connection reset`, timeout), decorator calls `execute(..., null)` and CRR can carry stale body from earlier call.  
  - Files:  
    - `novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/processor/PostMFTChildLoanBankDisbursementProcessor.java`  
    - `novopay-platform-lib/infra-transaction-interface/src/main/java/in/novopay/infra/decorator/WebClientServiceExecutorDecorator.java`

- **Early warning signs (logs/metrics to watch)**  
  - CRR row has `status=FAIL` but response body contains success-like `replyCode=0` with mismatched `client_reference_number` / template shape.  
  - Same timestamp window shows webclient transport error (`Connection reset by peer`, read timeout, EOF).

- **Immediate mitigation (2am, step-by-step)**  
  - Step 1: Correlate by `external_ref_number`, `client_reference_number`, `transaction_type`, and minute-level timestamp.  
  - Step 2: Validate source of truth from logs: callback `apiResponse` null/error path vs CRR stored response body.  
  - Step 3: Treat transport error as infra failure; do not infer bank success from stale CRR body.  
  - Step 4: If replay needed, follow disbursement idempotency checks first (loan status, existing successful CRR for same leg).

- **Fix applied (2026-04-14)**  
  - `PostMFTChildLoanBankDisbursementProcessor` now sets CRR response from callback `apiResponse` only (or explicit null-envelope), and uses null-safe request capture.
  - Commit: `1a789b6c7` on `mfi_integration_v3.2.8.4.1`.

- **Business impact**  
  - Wrong RCA path and delayed incident recovery; operators may take unsafe replay decisions based on misleading CRR evidence.

- **Files**  
  `novopay-platform-api-gateway/src/main/java/in/novopay/apigateway/config/FilterConfig.java`  
  `novopay-platform-api-gateway/src/main/java/in/novopay/apigateway/requestforward/RequestForwardController.java`  
  `novopay-platform-api-gateway/src/main/java/in/novopay/apigateway/requestforward/RequestForwardProcessor.java`

---

## LPPD multi-node batch — node map + log locations

- **Nodes**
  - **Master batch node**: `10.212.144.25`
  - **Worker 1**: `10.212.144.20`
  - **Worker 2**: `10.212.145.20`
  - **Worker 3**: `10.212.146.20`

- **Logs (per node IP)**
  - **Accounting (MFI)**: `/apps/applogs/{NODE_IP}/mfi/accounting-mfi.log`
  - **Common**: `/apps/applogs/{NODE_IP}/common/accounting-common.log`

- **Triage tip (cross-node)**
  - Start by searching the same correlator across **all** nodes: `jobName` / `scheduleId`, plus `tenant_code`, `stan`, `external_ref_number` (as applicable), and timestamps.

---

## GAP-062: `loanWriteoff` vs `PrepaymentApproppriationProcessor` — wrong or missing ExecutionContext keys

- **What breaks**  
  Final write-off posting branch invokes `prepaymentApproppriationProcessor` with orchestration keys that **do not match** what the Java processor reads (`total_foreclosure_amount`, `penal_amount`, `foreclosure_date`, `fee_amount` vs `prepayment_amount`, `penalty_amount`, `value_date`, unset fee). Runtime may throw (**null** → `BigDecimal` / `Long.parseLong`) or compute **wrong principal/interest/penalty/fee splits** before nested `postTransaction`.

- **Early warning signs**  
  - Logs/stack traces referencing `PrepaymentApproppriationProcessor` line ~85–90 on `loanWriteoff` APPROVE / auto-post path.  
  - `transaction_master` for `LOAN_WRITE_OFF` / `FINAL_WRITE_OFF` with amounts that don’t match expected outstanding components for the account.

- **Immediate mitigation (2am)**  
  1. Capture `account_number`, `stan`, `tenant_code`, and whether the failure is **exception** vs **wrong amounts**.  
  2. Compare `loan_due_details` outstanding components vs posted `transaction_details` for the same `client_reference_number` / business date.  
  3. **Do not** bulk-retry write-off without confirming idempotency (`client_reference_number` = `stan` on nested `postTransaction`).  
  4. If code fix not yet deployed: coordinate **manual GL / loan adjustment** per finance ops procedure (out of band of this runbook).

- **Permanent fix**  
  Align orchestration `IParam` / processor reads (see **GAP-062** in `.cursor/gaps-and-risks.md`): supply `total_foreclosure_amount` (or change processor), map `penalty_amount` ↔ `penal_amount`, map `value_date` → `foreclosure_date`, set `fee_amount`; add regression test for `loanWriteoff` REAL posting.

- **Files**  
  - `novopay-platform-accounting-v2/deploy/application/orchestration/loans_orc.xml` (`loanWriteoff`)  
  - `.../ValidateLoanWriteOffDataProcessor.java`  
  - `.../PrepaymentApproppriationProcessor.java`  
  - `novopay-platform-lib/.../DefaultExecutionContext.java` (`get` local-then-shared)

- **Business impact**  
  Write-off is a **terminal credit event**; wrong splits or failed completion blocks portfolio cleanup and statutory reporting accuracy.

---

## Cross-service transaction map (Flow Sync Wave 4)

- **When to use:** RCA touches **batch + Kafka + HTTP** in one incident; unclear which service owns the “commit point.”
- **Map:** `.cursor/cross-service-transactions.md` — happy path, failure step, compensation / reconciliation / monitoring posture per flow.
- **Related gaps:** disburse async (`entity_type`, Redis TTL), **GAP-019** producer swallow, multi-node batch scheduler race, time-based `client_reference_number` batch posting, auto-closure writer swallow, death-foreclosure insurance partial progress.

---

## Disbursement sync contract revalidation (2026-04-22)

- **When to use:** LOS reports stale/unchanged disbursement failure state while accounting logs show processing.

- **Checks**
  1. Inspect accounting producer payload fields in `LmsMessageBrokerConsumer.sendResultMessageToKafka`:
     - expected currently: `external_ref_number`, `status`, `tenant_code`, `timestamp`, optional `error_code`/`error_message`.
     - verify missing `entity_type` / `stan` in current runtime code.
  2. Inspect LOS consumer gate in `DisbursementSyncService`:
     - `entity_type` blank -> early return.
  3. Inspect accounting skip reason path:
     - `ALREADY_ACTIVE` publishes sync,
     - `LOCK_LOAN_STATUS` / `LOCK_CACHE_IN_PROGRESS` do not publish sync.

- **Immediate mitigation (2am)**
  - If LOS is stale and accounting skipped on lock/cache, publish manual reconciliation update using known `external_ref_number` and accurate failure reason (ops path).
  - Clear stale Redis in-flight keys only with tenant-safe scoped cleanup (never broad DB flush).
  - Correlate by `external_ref_number` + timestamps when `stan` is absent in sync payload.

- **Related gaps**
  - `GAP-070`, `GAP-071`, `GAP-072`, `GAP-073` in `.cursor/gaps-and-risks.md`.

---

## Appendix — quick triage checklist (all runbooks)

- **Correlators to capture first (copy/paste)**  
  - `tenant_code`, `stan`, `external_ref_number`, `account_number` (LAN), Kafka partition/offset, job name (if batch), and the exact request `apiName`.

- **Accounting DB checks (Yugabyte / `mfi_accounting`)**  
  - Confirm terminality: `loan_account.loan_status`, `loan_account.disbursement_status`, `loan_account.updated_on`  
  - Confirm bank leg trace: `client_request_response_log` rows for the same correlation keys  
  - Confirm posting trace: `transaction_master.client_reference_number`, `transaction_master.created_on`

- **Replay safety rule of thumb**  
  - If bank leg may have executed, never “retry the whole flow” blindly. Prefer inquiry/callback path or idempotent continuation stages.

- **When to stop and escalate**  
  - Any symptom of double-posting, duplicate disbursement, or GL imbalance → stop the trigger immediately and reconcile before any further retries.


