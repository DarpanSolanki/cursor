GENERATED FILE — edit gaps-and-risks.md, never this digest.

# Gaps digest (session bootstrap)

SoT: `.cursor/gaps-and-risks.md`. Escalate to full file when task touches a GAP-id/area below, needs Medium/Low narrative, or digest missing/stale.

## Open High (verbatim summary-table rows)

| Gap | Risk level | Evidence (file:lines) | What can go wrong |
|-----|-----------|------------------------|-------------------|
| **LOS disbursement sync no-ops if `entity_type` missing** | **High** | `trustt-platform-los/src/main/java/in/novopay/los/service/disbursement/DisbursementSyncService.java` L33-L37 | Producer can send failure but LOS skips DB update (failure_reason not updated). |
| **Broad Redis `flushDb()` helper exists** | **High** | `trustt-platform-lib/infra-cache/src/main/java/in/novopay/infra/cache/RedisCacheClient.java` L164 (`connection.flushDb()`) — citation drifted from old L109-L118 | Wrong/over-broad invocation can wipe an entire redis DB index for a service/tenant scope. |
| **Interest accrual posting uses time-based `client_reference_number`** | **High** | `trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/interest/interestaccrualbooking/InterestAccrualBookingBatchService.java` L251-L259 | Retry/replay can bypass client-ref dedupe and double-post if partial commits occur. |
| **Batch posting uses time-based `client_reference_number` in multiple flows (replay/double-post risk)** | **High** | Billing: `.../loanaccountbilling/LoanAccountBillingBatchService.java` L168; Asset criteria: `.../batchnew/npa/primary/loanaccountassetcriteriajob/LoanAccountAssetCriteriaBatchProcessor.java` L296 (`accountNumber + new Date().getTime()`); DCF writer: `.../DeathForeclosureInsuranceWriter.java` L530-L532 (`System.currentTimeMillis()`) — path/line citations refreshed 2026-07-23; plus `system_brain/edge_cases/batch_time_based_client_reference_number_replay_risk.md` | Re-run/retry generates a new client ref, bypasses `ClientReferenceNumberDedupProcessor`, and can double-post on partial progress unless additional idempotency markers exist. |
| **GAP-076 — 3.7.1 initial-setup omits `loan_account.dpi_suspense_amount`** | **High** (3.7.1 / DPI train only) | On watermark `trustt-platform-accounting@mfi_integration_v3.4.2.5`: **no** `dpiSuspenseAmount` field (N/A this train). On 3.7.1: entity maps `dpiSuspenseAmount`; fresh `trustt-platform-initial-setup@mfi_integration_v3.7.1` tip `e4ade8c3f8` has no `flyway/**/*.sql` hit for `dpi_suspense_amount`; local-only guard `scripts/sql/setup/local_setup_dpi_suspense_amount.sql` | Fresh QA/prod schemas on **3.7.1 DPI train** can start accounting without a required entity column. Do not treat as open defect on 3.4.2.5 accounting checkout. |
| **GAP-077 — 3.7.1 initial-setup duplicate Flyway migration versions (masterdata + notifications)** | **High** | `trustt-platform-initial-setup@mfi_integration_v3.7.1` tip `e4ade8c3f8`: masterdata `V000119` (`__add_global_audit_fallback_config.sql` + `__add_code_masters_for_dpic.sql`) and `V000120` (`__add_service_wise_audit_fallback_config.sql` + `__dpi_presentation_configuration.sql`) each have two files; notifications `V9000423` likewise. Flyway 5.2.4 aborts at scan: "Found more than one migration with version …". | Fresh `sh localhost.sh masterdata` / `notifications` fails entirely on any env (local/QA/prod) → bootstrap blocked. Workspace wrapper `scripts/bin/initial-setup-local.sh` detects and skips the affected service while continuing independent dependencies; it does not modify initial-setup. **Durable fix must renumber one file of each colliding pair on upstream 3.7.1** (release-owned). Runbook: brain `services/trustt-platform-initial-setup.md`. |
| **Proactive excess refund writer swallows exceptions** | **High** | `trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/refund/proactiveexcessamountrefund/ProactiveExcessAmountRefundItemWriter.java` L156-L158 | Silent failure can leave staging in inconsistent state; reruns may re-pick items. |
| **LoanAccountAutoClosureItemWriter logs and continues on unexpected exceptions** | **High** | `trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/loanaccountclosure/LoanAccountAutoClosureItemWriter.java` L114-L118 | Step can partially apply updates for some loans then silently skip remaining failures, leaving “looks successful” runs with inconsistent closure state unless downstream reconciliation exists. |
| **HTTP internal client has no retry/circuit breaker** | **High** | `trustt-platform-lib/infra-http-client/.../NovopayHttpAPIClient.java` `callAPI` L54+ — still no retry/circuit (verified 2026-07-23; old L94-L142 span drifted) | Transient failure can cause cross-service partial progress (caller commits, callee doesn’t) → **data inconsistency**, not only availability loss. |
| **Death-foreclosure insurance reverse-feed `Pending for FR` can partially progress and block the whole batch** | **High** | Cross-service path now in `.../deathforeclosure/service/DeathForeclosureInsuranceReUploadService.java` L92-L93 (`updateTaskWorkflow`) + `DeathForeclosureInsuranceReUploadCommitService` (`claim_status=REJECTED`); staging still selected via `claim_status='Pending for FR'` + `INBOUND_SUCCESS` (repository). Writer L247-L283 citation **stale**. Edge: `system_brain/edge_cases/death_foreclosure_insurance_pending_fr_partial_progress_blocks_batch.md` | Task update commits in separate service txn; if accounting chunk fails/rolls back after the call, staging stays eligible (`Pending for FR` + `INBOUND_SUCCESS`) and poison rows can repeatedly fail the job, blocking unrelated loans from progressing/closing. |
| **Gradle Novopay plugin classpath `3.2.6.6-1` vs dependency-mgmt published `3.2.6.6.2-1`** | **High** | `trustt-platform-accounting/build.gradle` L14 (`accounting.dependency.gradle.plugin:3.2.6.6-1`) vs `trustt-platform-dependency-mgmt/build.gradle` (e.g. accounting plugin `version = "3.2.6.6.2-1"`) | Resolved `trustt-platform-lib` / platform artifacts may **not** match the BOM developers believe they use — subtle cross-service binary drift at runtime. |
| **No `src/test` coverage for `LmsMessageBrokerConsumer` async disburse path** | **High** | Workspace `grep` `LmsMessageBrokerConsumer` in `**/src/test/**/*.java` → **no hits** (2026-04-07); see `.cursor/test-coverage-map.md` | Redis skip / Kafka result publish / orchestration regressions reach production without CI signal. |
| **No `src/test` coverage for `glBalanceZeroisation` / `reverseTransaction` / `postManualJournalEntry`** | **High** | Workspace `grep` those strings in `**/src/test/**/*.java` → **no hits** (2026-04-07); `.cursor/test-coverage-map.md` | Year-end GL and finance correction flows lack automated guard — misposting risk at close. |
| **No `src/test` coverage for DCF / insurance inbound batch posting** | **High** (mitigated locally) | `grep` `DeathForeclosure` in `**/trustt-platform-accounting/src/test/**/*.java` → **no hits**; **local money e2e:** `ntest run dcf.group_parent_last_child_e2e` + `scripts/dcf_sanity/*` on `mfi_integration_v3.7.1` | Unit tests still missing in CI; group last-child path covered by registry flow (SDCP-10199). |
| **GAP-074 — SDCP-10199 last-child parent INT/DPI under-settlement (INT-180)** | **High** (open; parked) | `DeathForeclosureInsuranceWriter.doParentPartPrePayment` (released trains / `mfi_integration_v3.7.1@f45dbe3bd` still use child `INT_AMT`); fix parked on `fix/sdcp-10199-parent-int-dpi-last-child-dfc` @ `61278d5f8` — **do not merge/push to `mfi_integration_v3.7.1` until QA/prod discuss**; runbook `cursor-bundle/brain/runbooks/sdcp-10199-group-parent-last-child-dfc.md`; ASK-057 **DEFERRED** | SHG/JLG parent can CLOSE after last-child DFC with residual pending INT (latent 3.4.2.1+); DPI residual risk on 3.7.1. Missed via lucky INT=0 e2e / UI-focused QA. |
| **Multi-node batch scheduler has no distributed leader/lock (race across batch instances)** | **High** | `trustt-platform-batch/src/main/java/in/novopay/batch/batchschedule/daoservice/BatchScheduleService.java` (`canStart`, `isJobRunning`) + `trustt-platform-batch/src/main/java/in/novopay/batch/core/service/SchedulerCommonService.java` (job start) | Two batch nodes can both decide “not running” and start the same job/group → duplicate job execution or inconsistent schedule status updates. |
| **No `src/test` coverage for API Gateway `AuthorizationCheckFilter` (permission / mapping-miss path)** | **High** | Workspace `grep` `AuthorizationCheckFilter` in `**/src/test/**/*.java` → **no hits** (2026-04-10); pairs **GAP-054** | Bypass / mis-configuration paths for mapped APIs ship without CI guard. |
| **No `src/test` coverage for API Gateway `RequestForward*` (`RequestForwardProcessor`, controller)** | **High** | Workspace `grep` `RequestForward` in `**/src/test/**/*.java` → **no hits** (2026-04-10); pairs **GAP-055** | `/forward/*` ingress (documented as filter-bypass + payload logging risk) has no automated regression tests. |

## Medium/Low index

GAP-018 | Platform-lib crypto utilities swallow exceptions and hardcod | see-full
GAP-019 | Kafka producer wrapper swallows send failures (no signal to  | see-full
GAP-020 | Async orchestration execution is fire-and-forget (no complet | see-full
GAP-021 | Hardcoded credentials committed across multiple services (Gr | see-full
GAP-022 | Notifications OTP/SMS/email flows ignore errors at orchestra | see-full
GAP-023 | Notifications service logs sensitive payloads and access tok | see-full
GAP-024 | DMS download endpoint is query-param based and uses caller-s | see-full
GAP-025 | DMS S3 util writes temp files using `urn` directly (path tra | see-full
GAP-026 | API Gateway logs decrypted secret keys and full request/resp | see-full
GAP-027 | API Gateway outbound HttpClient trusts all certificates and  | see-full
GAP-028 | Authorization service logs access tokens and has doc-vs-conf | see-full
GAP-029 | Masterdata business-date cache invalidation failures are non | see-full
GAP-030 | Task service has multiple replay/consistency risks (no TTL c | see-full
GAP-061 | Child MFT post-processor CRR response can diverge from callb | see-full
GAP-063 | `PopulateAndValidateAccountDetailsProcessor` — no null guard | see-full
GAP-065 | Accounting MessageBroker consumers — no explicit `maxPollRec | see-full
GAP-066 | Disburse sync Kafka message lacks correlation IDs (`stan` /  | see-full
GAP-067 | LOS → Accounting disburse Kafka message — implicit pipe-deli | see-full
GAP-068 | `collectionLoanRepayment` retry loop — nested `loanRepayment | see-full
GAP-069 | Critical money paths — partial observability vs six-point co | see-full
GAP-070 | Accounting disburse sync producer does not emit `entity_type | see-full
GAP-071 | Accounting consumer skip paths do not always publish LOS syn | see-full
GAP-072 | Consumer payload parsing happens before try/finally lock cle | see-full
GAP-073 | NEFT callback UTR map key mismatch in array branch | see-full
GAP-079 | GAP-079 — DCF non-last parent RSCH `lapd.amount` ≠ principa… | dcf.non_last_rsch_amount_eq_
GAP-080 | GAP-080 — Parent vs member future INT ₹1 schedule drift (pr… | dcf.parent_member_future_int
GAP-081 | GAP-081 — ship auto-drafts `unknownApi` when apiName unreso… | scripts
ROW-accounting-money-path-kafka-consumers-om | Accounting money-path Kafka consumers omit explicit `maxPol… | accounting
ROW-createorupdatebulkcollectionconsumer-col | `CreateOrUpdateBulkCollectionConsumer` — `collection_list` … | payments
ROW-lock-recovery-on-crr-save-failure-locks- | Lock recovery on CRR save failure locks loan but doesn’t se… | accounting
ROW-los-acc-disburse-pipe-delimiter-contract | LOS→ACC disburse pipe delimiter contract (`api\ | platform
ROW-money-path-observability-six-point-check | Money-path observability — six-point checklist not met unif… | .cursor
ROW-multi-node-batch-dependency-tracking-is- | Multi-node batch dependency tracking is in-memory only | batch
ROW-payments-collectionloanrepayment-retry-l | Payments `collectionLoanRepayment` retry loop over nested `… | MfiCollectionsDAOService.cal
ROW-posttransaction-populateandvalidateaccou | `postTransaction` — `PopulateAndValidateAccountDetailsProce… | accounting
ROW-proactive-excess-refund-uses-time-based- | Proactive excess refund uses time-based `client_reference_n… | ...
ROW-reopened-2026-04-22-los-lms-disbursement | REOPENED (2026-04-22) — `los_lms_disbursement_sync` still o… | accounting

<!-- digest high=18 medium=12 low=1 idx=37 max=14000 -->
