> **Dual-home (2026-07-15):** **SoT = `.cursor/gaps-and-risks.md`**. This brain file is a **mirror** for brain-first agents — keep money-path rows identical. Last money sync: **GAP-075 RESOLVED** (A2 EXTRA-net + B force-bill labd @ `5b1b928ed`); **GAP-074** INT-180 still **OPEN** — parked on `fix/sdcp-10199-parent-int-dpi-last-child-dfc` @ `61278d5f8`; **do not merge to `mfi_integration_v3.7.1` until discuss**.

# Identified gaps, risks, and inconsistencies (evidenced)

Every item below has **description + file path + line evidence + risk level**. Sources are either **code** or a named `system_brain/edge_cases/*` note plus its backing code.

> **File is 1500+ lines.** For a 30-second triage, read the **TL;DR** below; only scroll to the full gap list when you need the file:line evidence for a specific item.

## TL;DR — open High items as of 2026-05-08

(Updated whenever an item flips status. If this list is older than the latest entry in [`changelog/CHANGELOG.md`](changelog/CHANGELOG.md), trust the changelog.)

> **2026-05-08 audit pass** confirmed every open item below against `mfi_integration_v3.3.1.0.1` (head `149009993`). New consolidated delta map: [`accounting/11-deltas-3.3.1.0.1.md`](accounting/11-deltas-3.3.1.0.1.md). New skills for fast lookup: `txn-graph`, `batch-atlas-lookup`, `posting-rule-resolver`, `state-machine-safety`, `delta-3-3-1`. New brain doc: [`platform/state-machine-safety.md`](platform/state-machine-safety.md).


| # | Open High gap | Surface | One-liner |
|---|---|---|---|
| 1 | LOS disbursement sync `entity_type` missing | accounting → LOS | Producer can send failure but LOS skips DB update; LOS row stays "in progress" while accounting has terminal state. |
| 2 | Disbursement Redis in-flight key has no TTL (LOS + accounting) | LOS, accounting | Crash before cleanup ⇒ key persists ⇒ future replays skipped. |
| 3 | Lock-recovery on CRR save failure locks loan but doesn't set `disbursement_status` | accounting CRR | Loan goes `LOCK`; ops reset needed. (Medium) |
| 4 | Broad Redis `flushDb()` helper exists | platform-lib infra-cache | Wrong/over-broad invocation can wipe an entire Redis DB index for a service/tenant. |
| 5 | Interest accrual posting uses time-based `client_reference_number` | accounting batch | Retry/replay can bypass dedupe and double-post on partial commits. |
| 6 | Batch posting time-based CRN — multiple flows | billing, asset criteria, DCF insurance, proactive refund | Same dedupe-bypass risk on rerun. |
| 7 | Proactive excess refund writer swallows exceptions | accounting refund batch | Silent failure → inconsistent staging; re-runs may re-pick. |
| 8 | LoanAccountAutoClosureItemWriter logs+continues on unexpected exceptions | accounting closure batch | Looks-successful runs with inconsistent closure state. |
| 9 | HTTP internal client has no retry/circuit breaker | platform-lib infra-http-client | Cross-service partial progress; data inconsistency, not just availability. |
| 10 | Death-foreclosure insurance reverse-feed `Pending for FR` partial-progress blocks batch | accounting DCF | Poison rows fail repeatedly; blocks unrelated loans. |
| 11 | Gradle plugin classpath drift (`3.2.6.6-1` vs published `3.2.6.6.2-1`) | accounting build | Resolved platform-lib may differ from BOM expectation. |
| 12 | Multi-node batch scheduler — no distributed leader/lock | batch | Two batch nodes can both start the same job. |
| 13 | Money-path Kafka consumers omit explicit `maxPollRecords` in `MessageBroker.xml` | accounting | Backpressure / SLO not codified in-repo. |
| 14 | LOS→ACC disburse pipe delimiter contract is implicit | LOS, accounting consumer | Deploy skew breaks parsing or wrong `externRefNumber`. |
| 15 | Money-path observability checklist not met uniformly | cross-flow | Ops blind spots on several hops. |
| 16 | NEFT v2 MFT failure-branch `dao.save` (`PostMFTChildLoanBankDisbursementProcessor:145`) | accounting disbursement | Only path still vulnerable to outer-tx Hibernate auto-flush race; NEFT v2 path closed `4c339282f`+`09295c377`, MFT pending. |
| 17 | GAP-076: 3.7.1 initial-setup omits `loan_account.dpi_suspense_amount` | accounting / initial-setup | Fresh schemas can fail DPI/foreclosure/NPA paths; local setup is not a QA/prod migration. |
| 18 | GAP-077: 3.7.1 initial-setup duplicate Flyway versions (masterdata `V000119`/`V000120`, notifications `V9000423`) | initial-setup | Flyway 5.2.4 aborts scan → fresh masterdata/notifications bootstrap fails; needs upstream renumber. |

**Recently CLOSED:**

- **NEFT v2 child CLMT race series** (2026-05-07, `4c339282f`+`09295c377` after PR #260) — atomic CAS + post-CAS in-memory mutation removal. Closes the seven-iteration race-fix sequence + Hibernate auto-flush race. See full row in the table below + `engines/disbursement-engine.md` §writer-registry.
- Parent NEFT v2 ST_NEI idempotency (2026-04-16).
- TOCTOU race in cursor's Redis in-flight gate (2026-05-04, `4cb437b28`+`ede4aa325`).
- Child NEFT v2 stage-1 evidence guard too strict (2026-05-04, `ede4aa325`).
- Task-id orphan freeze flip (2026-05-04, `154b500c0`, branch `mfi_integration_v3.2.8.4`; forward-port pending to other branches).
- DCF billed-principal split + BPI-hack removal (2026-05-07, SDCP-9301, branch `sdcp-9301-hotfix-3.2.8.4`).

**For deferred / not-yet-addressed High gaps**, the table below is the source of truth. Search by symptom keyword (e.g. "Redis in-flight", "trial balance", "DCF").

---

## Gaps (evidenced)

| Gap | Risk level | Evidence (file:lines) | What can go wrong |
|-----|-----------|------------------------|-------------------|
| **LOS disbursement sync no-ops if `entity_type` missing** | **High** | `trustt-platform-los/src/main/java/in/novopay/los/service/disbursement/DisbursementSyncService.java` L33-L37 | Producer can send failure but LOS skips DB update (failure_reason not updated). |
| **REOPENED (2026-04-29) — Accounting → LOS sync payload does NOT include `entity_type` on branch `mfi_integration_v3.2.8.4.1`** | **High** | `trustt-platform-accounting/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java` `sendResultMessageToKafka` L239-L271 — payload has only `external_ref_number, status, error_code, error_message, tenant_code, timestamp` | LOS `DisbursementSyncService.java` L33-L37 still skips when `entity_type` absent → silent skip on FAILED/SUCCESS sync; LOS row stays "in progress" while accounting has terminal state. **Re-fix:** add `entity_type` from EC to the JSON payload (and verify it survives mfi/product template precedence). |
| **Disbursement Redis in-flight key has no TTL (LOS producer)** | **High** | `trustt-platform-los/src/main/java/in/novopay/los/util/DisburseLoanAPIUtil.java` L72-L83 | Crash before cleanup ⇒ key persists ⇒ future replays skipped. |
| **Disbursement Redis in-flight key has no TTL (Accounting consumer)** | **High** | `trustt-platform-accounting/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java` L108-L122, L148-L151 | Same stale-lock risk on consumer-side “dl” key. |
| **RESOLVED — Child MFT CRR response now aligns with callback payload source** | **Resolved (was High)** | `trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/disbursement/processor/PostMFTChildLoanBankDisbursementProcessor.java` L98-L105 (`setResponse` from callback `apiResponse`/null-envelope, status from `apiResponse`) | Eliminates stale `ExecutionContext.response` mismatch in child MFT CRR rows on null-callback transport errors. |
| **Lock recovery on CRR save failure locks loan but doesn’t set `disbursement_status`** | **Medium** | `trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/client/repository/ClientRequestResponseLogDAOService.java` L50-L65 | Recovery makes loan `LOCK`; stage routing relying on disbursement_status may stall or require ops reset. |
| **Broad Redis `flushDb()` helper exists** | **High** | `trustt-platform-lib/infra-cache/src/main/java/in/novopay/infra/cache/RedisCacheClient.java` L109-L118 | Wrong/over-broad invocation can wipe an entire redis DB index for a service/tenant scope. |
| **RESOLVED — Parent NEFT v2 ST_NEI idempotency vs child (stage-1 success lag)** | **Resolved (was Medium)** | `trustt-platform-accounting/.../CallBankAPIForDisbursementProcessor.java` — `shouldSkipNeftStage2Initiation(loanAccountNumber, disbursementStatus, neiTransactionType)` skips when SUCCESS CRR exists for orchestration-scoped `…_NEFT_NEI` for **both** `NEFT_STAGE_1_SUCCESS` and `NEFT_STAGE_2_PENDING`; `doNEFTTransaction` repeats check before `neftPaymentV2Stage2` (2026-04-16) | Eliminates duplicate ST_NEI API risk when loan/queue still shows stage-1 success but NEI CRR already SUCCESS (parent–child parity). |
| **RESOLVED — NEFT v2 child CLMT race series (stuck-row class on `loan_account_events_queue`)** | **Resolved (was High)** | accounting-v2 PR #260 (`e3d84a53b` … `f6e83c9fe`) replaced rank-guard-before-`dao.save` with atomic CAS via new `ChildClmtStateMachineService` / `LoanAccountStateMachineService`. Final fix `4c339282f` + `09295c377` (2026-05-07) removed all post-CAS in-memory entity mutations and routed advisory/error writes through new state-agnostic `patchJsonFields`. See `claude/engines/disbursement-engine.md` §4.8 + §writer-registry. | Closes the seven-iteration race-fix sequence (`8abd48f49`, `a6fdc1c88`, `c2583dca9`, `5bb49d7a4`, `ede4aa325`, `55e58d31d`, `c704969ec`, `ccf7f6b89`) plus the Hibernate auto-flush race that survived all of them. State-machine race-class closed without `@Version`; **only remaining gap: `PostMFTChildLoanBankDisbursementProcessor:145` failure branch still uses `dao.save` and is vulnerable to the same auto-flush pattern — open follow-up.** |
| **Interest accrual posting uses time-based `client_reference_number`** | **High** | `trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/interest/interestaccrualbooking/InterestAccrualBookingBatchService.java` L251-L259 | Retry/replay can bypass client-ref dedupe and double-post if partial commits occur. |
| **GAP-076 — 3.7.1 initial-setup omits `loan_account.dpi_suspense_amount`** | **High** | Accounting `LoanAccountEntity.java` L106 maps `dpiSuspenseAmount`; fresh `trustt-platform-initial-setup@mfi_integration_v3.7.1` tip `e4ade8c3f8` has no `flyway/**/*.sql` hit for `dpi_suspense_amount`; local-only guard `scripts/sql/setup/local_setup_dpi_suspense_amount.sql` | Fresh QA/prod schemas can start accounting without a required entity column, causing DPI/foreclosure/NPA SQL failures. Local setup unblocks local tests but is not a release migration; initial-setup Flyway + prod manual DDL/history pack remain required. |
| **GAP-077 — 3.7.1 initial-setup duplicate Flyway migration versions (masterdata + notifications)** | **High** | `trustt-platform-initial-setup@mfi_integration_v3.7.1` tip `e4ade8c3f8`: masterdata `V000119` (`__add_global_audit_fallback_config.sql` + `__add_code_masters_for_dpic.sql`) and `V000120` (`__add_service_wise_audit_fallback_config.sql` + `__dpi_presentation_configuration.sql`); notifications `V9000423` — two files share one version. Flyway 5.2.4 aborts scan ("Found more than one migration with version …"). | Fresh `sh localhost.sh masterdata`/`notifications` fails entirely (local/QA/prod) → bootstrap blocked. Workspace wrapper `scripts/bin/initial-setup-local.sh` detects/skips the affected service and continues independent dependencies without changing initial-setup. Durable fix = release-owned renumbering upstream on 3.7.1. Runbook: `services/trustt-platform-initial-setup.md`. |
| **Batch posting uses time-based `client_reference_number` in multiple flows (replay/double-post risk)** | **High** | `trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/loanaccountbilling/LoanAccountBillingBatchService.java` L168, `.../loanaccountassetcriteriajob/LoanAccountAssetCriteriaBatchProcessor.java` L286, `.../loan/deathforeclosure/writer/DeathForeclosureInsuranceWriter.java` L441-L453, plus `system_brain/edge_cases/batch_time_based_client_reference_number_replay_risk.md` | Re-run/retry generates a new client ref, bypasses `ClientReferenceNumberDedupProcessor`, and can double-post on partial progress unless additional idempotency markers exist. |
| **Proactive excess refund writer swallows exceptions** | **High** | `trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/refund/proactiveexcessamountrefund/ProactiveExcessAmountRefundItemWriter.java` L156-L158 | Silent failure can leave staging in inconsistent state; reruns may re-pick items. |
| **Proactive excess refund uses time-based `client_reference_number`** | **Medium** | `.../ProactiveExcessAmountRefundItemWriter.java` L209-L211 | Same dedupe-risk pattern if a rerun happens after partial progress. |
| **LoanAccountAutoClosureItemWriter logs and continues on unexpected exceptions** | **High** | `trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/loanaccountclosure/LoanAccountAutoClosureItemWriter.java` L114-L118 | Step can partially apply updates for some loans then silently skip remaining failures, leaving “looks successful” runs with inconsistent closure state unless downstream reconciliation exists. |
| **HTTP internal client has no retry/circuit breaker** | **High** | `trustt-platform-lib/infra-http-client/src/main/java/in/novopay/infra/api/client/NovopayHttpAPIClient.java` L54-L92, L94-L142 | Transient failure can cause cross-service partial progress (caller commits, callee doesn’t) → **data inconsistency**, not only availability loss. |
| **Death-foreclosure insurance reverse-feed `Pending for FR` can partially progress and block the whole batch** | **High** | `trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/deathforeclosure/writer/DeathForeclosureInsuranceWriter.java` L247-L283 (calls `updateTaskWorkflow` then marks staging as `REJECTED`), plus `system_brain/edge_cases/death_foreclosure_insurance_pending_fr_partial_progress_blocks_batch.md` | Task update commits in separate service txn; if accounting chunk fails/rolls back after the call, staging stays eligible (`Pending for FR` + `INBOUND_SUCCESS`) and poison rows can repeatedly fail the job, blocking unrelated loans from progressing/closing. |
| **Gradle Novopay plugin classpath `3.2.6.6-1` vs dependency-mgmt published `3.2.6.6.2-1`** | **High** | `trustt-platform-accounting/build.gradle` L14 (`accounting.dependency.gradle.plugin:3.2.6.6-1`) vs `trustt-platform-dependency-mgmt/build.gradle` (e.g. accounting plugin `version = "3.2.6.6.2-1"`) | Resolved `trustt-platform-lib` / platform artifacts may **not** match the BOM developers believe they use — subtle cross-service binary drift at runtime. |
| **No `src/test` coverage for `LmsMessageBrokerConsumer` async disburse path** | **High** | Workspace `grep` `LmsMessageBrokerConsumer` in `**/src/test/**/*.java` → **no hits** (2026-04-07); see `.cursor/test-coverage-map.md` | Redis skip / Kafka result publish / orchestration regressions reach production without CI signal. |
| **No `src/test` coverage for `glBalanceZeroisation` / `reverseTransaction` / `postManualJournalEntry`** | **High** | Workspace `grep` those strings in `**/src/test/**/*.java` → **no hits** (2026-04-07); `.cursor/test-coverage-map.md` | Year-end GL and finance correction flows lack automated guard — misposting risk at close. |
| **No `src/test` coverage for DCF / insurance inbound batch posting** | **High** | `grep` `DeathForeclosure` / inbound insurance writer symbols in `**/trustt-platform-accounting/src/test/**/*.java` → **no hits** (2026-04-07) | Insurance → LMS posting regressions undetected until staging/prod reconciliation. |
| **Multi-node batch scheduler has no distributed leader/lock (race across batch instances)** | **High** | `trustt-platform-batch/src/main/java/in/novopay/batch/batchschedule/daoservice/BatchScheduleService.java` (`canStart`, `isJobRunning`) + `trustt-platform-batch/src/main/java/in/novopay/batch/core/service/SchedulerCommonService.java` (job start) | Two batch nodes can both decide “not running” and start the same job/group → duplicate job execution or inconsistent schedule status updates. |
| **Multi-node batch dependency tracking is in-memory only** | **Medium** | `trustt-platform-batch/src/main/java/in/novopay/batch/core/service/SchedulerCommonService.java` (`jobCompletionStatus` map, `areDependenciesCompleted`) | In multi-instance deployment, node A’s dependency completion is invisible to node B → dependency ordering can be violated cluster-wide. |
| **No `src/test` coverage for API Gateway `AuthorizationCheckFilter` (permission / mapping-miss path)** | **High** | Workspace `grep` `AuthorizationCheckFilter` in `**/src/test/**/*.java` → **no hits** (2026-04-10); pairs **GAP-054** | Bypass / mis-configuration paths for mapped APIs ship without CI guard. |
| **No `src/test` coverage for API Gateway `RequestForward*` (`RequestForwardProcessor`, controller)** | **High** | Workspace `grep` `RequestForward` in `**/src/test/**/*.java` → **no hits** (2026-04-10); pairs **GAP-055** | `/forward/*` ingress (documented as filter-bypass + payload logging risk) has no automated regression tests. |
| **`loanWriteoff` orchestration vs `PrepaymentApproppriationProcessor` ExecutionContext contract mismatch** | **High** | `loans_orc.xml` `loanWriteoff` passes `prepayment_amount` (not `total_foreclosure_amount`); `ValidateLoanWriteOffDataProcessor` sets `penalty_amount` but processor reads `penal_amount`; write-off uses `value_date`, processor reads `foreclosure_date`; `fee_amount` not set pre-processor — **GAP-062** | Appropriation/posting branch can **NPE** or apply **wrong component splits** for final write-off ledger and dues updates. |
| **`postTransaction` — `PopulateAndValidateAccountDetailsProcessor` assumes non-null `account_details` array** | **Medium** | `trustt-platform-accounting/.../PopulateAndValidateAccountDetailsProcessor.java` L60-L61 — direct cast/iterate without null check | Malformed request, partial internal-api merge, or bypassed validation → **NPE** before business validation messages. |
| **`CreateOrUpdateBulkCollectionConsumer` — `collection_list` null before `size()`** | **Medium** | `trustt-platform-payments/.../CreateOrUpdateBulkCollectionConsumer.java` L81-L83 — `collection_list` cast without null check | Valid JSON envelope with missing `collection_list` → **NPE**; offsets stuck / poison message behaviour depends on broker config — **GAP-064**. |
| **Accounting money-path Kafka consumers omit explicit `maxPollRecords` in MessageBroker.xml** | **Medium** | `trustt-platform-accounting/deploy/application/messagebroker/MessageBroker.xml` L15-L28 — only `pollTime` / threads; no `maxPollRecords` (cf. payments bulk consumer) | Broker/framework defaults apply; backpressure/lag tuning and “financial topic SLO” not codified in-repo — **GAP-065**. |
| **REOPENED (2026-04-29) — `los_lms_disbursement_sync` does NOT include `stan` on branch `mfi_integration_v3.2.8.4.1`** | **Medium** | `LmsMessageBrokerConsumer.sendResultMessageToKafka` L239-L271 — no `stan` field set on payload | **GAP-066 REOPENED** — async correlation with LOS `DisburseLoanAPIUtil` header `stan` is broken; structured consumer logs use `external_ref_number` only. **Re-fix:** thread `stan` from EC headers into payload alongside `entity_type`. |
| **LOS→ACC disburse pipe delimiter contract (`api\|json\|cacheKey`) is implicit cross-service** | **Medium** | `DisburseLoanAPIUtil.java` L66-L69; `LmsMessageBrokerConsumer` L160-L162, L79-86 | Deploy skew if either side changes separator or cacheKey shape → parse failures or wrong `externRefNumber` — **GAP-067**. |
| **Payments `collectionLoanRepayment` retry loop over nested `loanRepayment` (dedupe reliance)** | **Medium** | `MfiCollectionsDAOService.callPushLMSUpdateAPI` L1038-L1084; `CollectionRepaymentProcessor` L68-L74 (`client_reference_number` = receipt) | Retries re-drive full processor; **usually** guarded by accounting CRR dedupe — residual double-post if dedupe bypassed, partial multi-item failure, or receipt semantics change — **GAP-068**. |
| **Money-path observability — six-point checklist not met uniformly** | **Medium** | See `.cursor/knowledge-graph.md` money paths + Part B Wave 6 matrix in **GAP-069** | Ops blind spots: missing universal structured entry/exit+correlation, completion events, and alerting hooks on several hops — **GAP-069**. |

**Counts (open items, summary table rows not marked RESOLVED):** **High: 17**, **Medium: 10**, **Low: 0** (after 2026-04-29 resync on `mfi_integration_v3.2.8.4.1` reopened `entity_type` and `stan` rows). Runbooks: `.cursor/runbooks.md`.

**2026-04-29 branch resync findings (verified by reading code on `mfi_integration_v3.2.8.4.1`):**
- **GAP — entity_type missing in sync payload — REOPENED to High.** `LmsMessageBrokerConsumer.sendResultMessageToKafka` L239–L271 builds the payload with only `external_ref_number, status, error_code, error_message, tenant_code, timestamp`. The earlier "RESOLVED" row was either reverted or was never propagated to this branch. LOS-side guard in `DisbursementSyncService.java` still depends on `entity_type`.
- **GAP-066 — stan missing in sync payload — REOPENED to Medium.** Same method; no `stan` field set.
- **No new High gaps** introduced by branch-specific code (NEFT v2 hardening from 2026-04-15/16/27/29 is reflected in code: `shouldSkipNeftStage2Initiation`, `NeftStage1InquiryGate`, ST_NEF double-debit guard, child NEFT v2 transaction_type fallback, lane-scoped CRR selection — see `disbursement-engine.md` §6).
- **Confirmed existing High items still present in code:**
  - Disburse Redis `dl*` key has no TTL (consumer L111).
  - `RedisCacheClient.flushDb()` (platform-lib).
  - Time-based `client_reference_number` in `InterestAccrualBookingBatchService.java` L251–L259, `LoanAccountBillingBatchService.java`, `ProactiveExcessAmountRefundItemWriter.java` L209–L211, `DeathForeclosureInsuranceWriter.java` L441–L453.
  - `LoanAccountAutoClosureItemWriter.java` L114–L118 swallow-and-continue.
  - `ProactiveExcessAmountRefundItemWriter.java` L156–L158 swallow.
  - CRR save lock-recovery sets `LoanStatus=LOCK` without setting `disbursement_status`.
  - Zero `src/test` for `LmsMessageBrokerConsumer`, `glBalanceZeroisation`, `reverseTransaction`, `postManualJournalEntry`, DCF / insurance writers.


**Wave 1 mining (2026-04-10):** +7 additional documented items — **GAP-031..037** — **High: 4**, **Medium: 2**, **Low: 1** (see section *Wave 1 gap mining* below; excludes duplicates of GAP-018..030 / table rows).

**Wave 2 mining (2026-04-10):** +8 additional documented items — **GAP-038..045** — **High: 5**, **Medium: 3**, **Low: 0** (`trustt-platform-los` + `trustt-platform-payments`, Java + orchestration XML; excludes table-row duplicates for disburse Redis TTL, `entity_type` sync, platform `NovopayKafkaProducer` swallow — cite those where relevant).

**Wave 3 mining (2026-04-10):** +8 additional documented items — **GAP-046..053** — **High: 5**, **Medium: 3**, **Low: 0** (`trustt-platform-task`, `trustt-platform-actor` lens pass, `trustt-platform-batch`; excludes **table-row** duplicates for multi-node scheduler race + in-memory dependency map — see rows above; cross-ref `.cursor/multinode-batch.md`).

**Wave 4 mining (2026-04-10):** +5 additional documented items — **GAP-054..058** — **High: 2**, **Medium: 3**, **Low: 0** (`trustt-platform-masterdata-management`, `trustt-platform-authorization`, `trustt-platform-approval`, `trustt-platform-audit`, `trustt-platform-notifications`, `trustt-platform-api-gateway`, `trustt-platform-dms` — Java `src/main/java`; authorization service has **no** “default allow” in `CheckPermissionProcessor` when usecase resolves; gateway **skips** permission call when mapping row missing).

**Flow Sync Wave 4 (2026-04-17):** Batch → accounting mapping (`trustt-platform-batch` scheduler + **71** accounting `*BatchConfigService` entry points), Actor/Masterdata contract pass from accounting `callInternalAPI` grep, **cross-service transaction synthesis** — **NEW** file `.cursor/cross-service-transactions.md`. **No new High/Medium gap IDs** beyond existing summary table: mapped flows consolidate known rows (multi-node batch, time-based `client_reference_number`, Kafka swallow, disburse sync, auto-closure writer swallow, DCF insurance, collections recon).

**Flow Sync Wave 5 (2026-04-17):** **API catalogue** — `.cursor/api-catalogue.md` (**1797** unique orchestration `Request name` across 14 service repos; **146** Kafka topic headings from `event-registry.md`; batch + scheduler sections). **Knowledge graph** — `.cursor/knowledge-graph.md` + `.cursor/knowledge-graph.mmd` (accounting-centered, money paths, SPOFs, representative **16** edges with ALIGNED/DRIFT/MISMATCH). **No new gap IDs** from this wave.

**Flow Sync Wave 6 (2026-04-17):** Cross-service gap mining + flow completeness + final KB sync — **GAP-065..069** (**High: 0**, **Medium: 5**). Evidence: accounting `MessageBroker.xml`, `LmsMessageBrokerConsumer`, `DisburseLoanAPIUtil`, `MfiCollectionsDAOService` / `CollectionRepaymentProcessor`, observability matrix (**GAP-069**). **Silent field drift (Type 1):** `entity_type` + **`stan` in sync payload** — **mitigated in accounting** (2026-04-17): templates + `LmsMessageBrokerConsumer.sendResultMessageToKafka`; LOS guard in `DisbursementSyncService.java` L33-37 still applies to other publishers. **Compensation missing (Type 5):** confirmed in code path terms — no saga in `NovopayHttpAPIClient` / `NovopayInternalAPIClient` (single execute); see `.cursor/cross-service-transactions.md` per-txn **Compensation: MISSING** rows.

**Test-registry closure (2026-04-10):** +2 additional documented items — **GAP-059..060** — **High: 2** (no `src/test` hits for critical gateway paths; pairs with **GAP-054** / **GAP-055**).

## Notes kept as rules/runbooks (not “gaps”)

- **API contract safety**: `.cursor/rules/api-contract-safety.md` (not a gap; it’s the guardrail).
- **Boot version skew**: `.cursor/platform-lib.md` “Version skew” section (fact, not a gap).

---

*Update only when verified from code, with file:line evidence.*

## GAP-018: Platform-lib crypto utilities swallow exceptions and hardcode secrets

Service: trustt-platform-lib  
Lens: 1 (Exception swallowing), 10 (Security & data leakage)  
Risk: 🔴 High  
File: `trustt-platform-lib/infra-transaction-interface/src/main/java/in/novopay/infra/util/EncryptionUtil.java`  
Line: `EncryptionUtil#HMAC_SHA256`, `EncryptionUtil#getEncryptedTextForRefNumber`, `EncryptionUtil#getRequestTokenForFiller2`  
Description: Multiple crypto helpers have empty `catch` blocks and/or print stack traces; one method hardcodes an AES key string in source and uses it for encryption.  
Failure scenario: Crypto failures are silently converted to empty/trimmed outputs → downstream request signing/encryption can proceed with invalid data; hardcoded key exposure enables offline decryption/forgery if code leaks.  
Financial impact: Potential request integrity failure in bank/payment legs; compliance incident due to embedded secret and weak error handling.  
Evidence:
```97:106:trustt-platform-lib/infra-transaction-interface/src/main/java/in/novopay/infra/util/EncryptionUtil.java
		try {
			Mac sha256_HMAC = Mac.getInstance("HmacSHA256");
			SecretKeySpec secret_key = new SecretKeySpec(secret.getBytes(), "HmacSHA256");
			sha256_HMAC.init(secret_key);
			hash = Base64.getEncoder().encodeToString(sha256_HMAC.doFinal(message.getBytes()));
		} catch (Exception e) {
		}
		return hash.trim();
```
```109:126:trustt-platform-lib/infra-transaction-interface/src/main/java/in/novopay/infra/util/EncryptionUtil.java
			String key = "HDFCBANK!@#987MOBAPP";
			byte[] b = key.getBytes("UTF-8");
			// ...
		} catch (Exception e) {
			throw new NovopayFatalException("Unable to Encrypt the Data",e.toString());
		}
```
Fix: Remove hardcoded secrets (externalize to secret manager/config + rotation). Replace empty catches with explicit failures (typed `NovopayFatalException` with error code), and ensure callers handle failures (do not proceed with empty HMAC / malformed encrypted blocks). Add unit tests asserting exception propagation and non-empty outputs.  
Effort: 1–2 days  
Status: OPEN  
Found in branch: (scan-time)  
Date found: 2026-04-09

## GAP-019: Kafka producer wrapper swallows send failures (no signal to caller)

Service: trustt-platform-lib  
Lens: 1 (Exception swallowing), 4 (Retry & circuit breaker), 11 (Observability gaps)  
Risk: 🔴 High  
File: `trustt-platform-lib/infra-message-broker/src/main/java/in/novopay/infra/message/broker/producer/NovopayKafkaProducer.java`  
Line: `NovopayKafkaProducer#sendMessage`  
Description: `sendMessage` wraps producer send in a broad `try/catch` and only logs on failure; there’s no rethrow, no returned future, and no persistence fallback (outbox).  
Failure scenario: Producer send fails (broker outage, auth, serialization) → caller assumes event is emitted; downstream consumers never act; cross-service state diverges.  
Financial impact: Loss of financial sync events or audit events; silent data loss in money-moving flows that use Kafka for side effects or reconciliation.  
Evidence:
```107:140:trustt-platform-lib/infra-message-broker/src/main/java/in/novopay/infra/message/broker/producer/NovopayKafkaProducer.java
	public void sendMessage(String topic, String key, String message, Map<String, String> headers, Callback callback) {
		try {
			// ...
			producer.send(producerRecord, callback);
		} catch (Exception e) {
			LOG.error("Fail to send message to Kafka for <topic, key> = {} , {} ", topic, key, e);
		}
	}
```
Fix: Expose delivery outcome to callers: return the `Future`/`CompletableFuture` and require callers to handle failures, or implement an outbox table + publisher with retries. At minimum: configurable “fail-fast” mode for critical topics to throw and trigger transaction rollback/compensation.  
Effort: 2–5 days (L0 fail-fast flag), 1–2 weeks (L2 outbox)  
Status: OPEN  
Found in branch: (scan-time)  
Date found: 2026-04-09

## GAP-020: Async orchestration execution is fire-and-forget (no completion/error contract)

Service: trustt-platform-lib  
Lens: 6 (Transaction boundaries), 7 (Async & thread safety), 11 (Observability gaps)  
Risk: 🔴 High  
File: `trustt-platform-lib/infra-navigation/src/main/java/in/novopay/infra/navigation/orchestrator/ServiceOrchestrator.java`  
Line: `ServiceOrchestrator#processAsyncRequest`  
Description: Async request processing uses `CompletableFuture.runAsync` without capturing completion/failure, and without persisting async job state; failures can only be seen in logs and are not surfaced to the triggering flow.  
Failure scenario: Async processor chain throws (validation, DB, downstream API) → request is lost with no durable status; retries may re-run without idempotency guard or may never occur depending on caller.  
Financial impact: Money-moving async requests can fail silently, leading to stuck workflows and reconciliation gaps.  
Evidence:
```56:64:trustt-platform-lib/infra-navigation/src/main/java/in/novopay/infra/navigation/orchestrator/ServiceOrchestrator.java
	public void processAsyncRequest(ExecutionContext executionContext, Request orcRequest) {
		PlatformTenant tenant = ThreadLocalContext.getTenant();
		CompletableFuture.runAsync(() -> {
			MDC.put("tenant", tenant.getTenantCode().toLowerCase());
			MDC.put("stan", executionContext.getValue("stan", String.class));
			ThreadLocalContext.setTenant(tenant);
			processRequest(executionContext, orcRequest);
		}, npThreadPoolExecutor.getExecutor());
	}
```
Fix: Introduce a durable async execution record (status, attempt, error_code/message, correlation ids) and ensure every async run updates it on success/failure. Return a job id to caller; provide retry semantics and idempotency keys. At minimum: attach `.exceptionally(...)` handler that logs structured context and publishes an alert/event.  
Effort: 3–7 days (durable status + minimal API), 2–3 weeks (full async framework)  
Status: OPEN  
Found in branch: (scan-time)  
Date found: 2026-04-09

## GAP-021: Hardcoded credentials committed across multiple services (Gradle + application.properties)

Service: platform-wide  
Lens: 10 (Security & data leakage)  
Risk: 🔴 High  
File: multiple (see evidence)  
Line: buildscript / config properties  
Description: Multiple services commit plaintext credentials (Nexus repo creds; SMTP; ES; Firebase private keys).  
Failure scenario: Credential exfiltration → repo compromise, email takeover, ES access, push-notification spoofing; audit/compliance incident.  
Financial impact: Platform compromise can enable data theft and fraudulent notifications/flows.  
Evidence:
```4:15:trustt-platform-task/build.gradle
    credentials {
        username "novopay"
        password "novopay#25"
    }
```
```26:30:trustt-platform-task/src/main/resources/application.properties
actor.email.password=novopay#123
```
```18:28:trustt-platform-audit/src/main/resources/application.properties
novopay.platform.es.password=Novopay#25
```
```1:13:trustt-platform-notifications/deploy/application/service-account.json
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIE...
```
Fix: Remove secrets from repo, rotate all exposed credentials, enforce `${ENV_VAR}`/secret manager usage, add secret-scanning CI gate.  
Effort: 1–3 days (removal + rotation)  
Status: OPEN  
Found in branch: (scan-time)  
Date found: 2026-04-09

## GAP-022: Notifications OTP/SMS/email flows ignore errors at orchestration level (silent delivery failure)

Service: trustt-platform-notifications  
Lens: 1 (Exception swallowing), 11 (Observability gaps)  
Risk: 🔴 High  
File: `trustt-platform-notifications/deploy/application/orchestration/product_otp.xml`, `custom_mfi.xml`  
Line: `ignoreErrorCodes="ALL"`  
Description: Notification send processors are configured to ignore all errors, so OTP/SMS/email send can fail silently while upstream flow continues as success.  
Failure scenario: OTP not delivered but auth flow proceeds; users locked out or (worse) flows assume verification happened.  
Financial impact: Authentication failures, support load; potential security bypass if caller assumes OTP delivered.  
Evidence:
```6:20:trustt-platform-notifications/deploy/application/orchestration/product_otp.xml
<Processor bean="sendSMSNotificationProcessor" ignoreErrorCodes="ALL">
```
```3:7:trustt-platform-notifications/deploy/application/orchestration/custom_mfi.xml
<Processor bean="sendSMSProcessor" ignoreErrorCodes="ALL">
```
Fix: Remove blanket ignore; convert to explicit retry/DLQ or fail-fast depending on flow; emit metrics for delivery failures.  
Effort: 0.5–2 days  
Status: OPEN  
Found in branch: (scan-time)  
Date found: 2026-04-09

## GAP-023: Notifications service logs sensitive payloads and access tokens (PII + secret leakage)

Service: trustt-platform-notifications  
Lens: 10 (Security & data leakage), 11 (Observability gaps)  
Risk: 🔴 High  
File: multiple (see evidence)  
Line: FCM token log + message payload logs  
Description: Service logs raw notification payloads and FCM access token at info/debug, and logs SMS message + sharedMap.  
Failure scenario: Logs expose phone numbers, message content (OTP), tokens enabling push spoofing.  
Financial impact: Account takeover vectors; compliance breach.  
Evidence:
```94:106:trustt-platform-notifications/src/main/java/in/novopay/notifications/fcm/service/FcmPushNotificationService.java
String accessToken = getAccessToken();
LOG.info("Access Token: {}", accessToken);
```
```83:88:trustt-platform-notifications/src/main/java/in/novopay/notifications/sms/processor/SendSMSNotificationProcessor.java
LOG.info("Before Notification message ::: {}", message);
LOG.info("Notification sharedMap ::: {}", map);
```
Fix: Redact/mask logs; never log access tokens or full payload maps; add allowlisted structured logging.  
Effort: 1–2 days  
Status: OPEN  
Found in branch: (scan-time)  
Date found: 2026-04-09

## GAP-024: DMS download endpoint is query-param based and uses caller-supplied tenant_code (IDOR/tenant-hop risk)

Service: trustt-platform-dms  
Lens: 10 (Security & data leakage), 5 (Contract drift / context integrity)  
Risk: 🔴 High  
File: `trustt-platform-dms/src/main/java/in/novopay/dms/controller/DownloadDocumentController.java`  
Line: `serveFile(...)`  
Description: Download endpoint accepts `tenant_code` as request param and builds file path using it; no auth headers are consumed in the controller method signature.  
Failure scenario: If perimeter/gateway validation is misconfigured, attacker can fetch cross-tenant documents by changing tenant_code and guessing document_code.  
Financial impact: PII/document exfiltration (KYC docs), regulatory incident.  
Evidence:
```73:85:trustt-platform-dms/src/main/java/in/novopay/dms/controller/DownloadDocumentController.java
@GetMapping(value = "/{apiVersion}/downloadDocument")
public ResponseEntity<Object> serveFile(...,
        @RequestParam(TENANT) String tenantCode, @RequestParam(DOCUMENT_CODE) String documentCode,
```
```107:113:trustt-platform-dms/src/main/java/in/novopay/dms/controller/DownloadDocumentController.java
String fileLocation = this.documentUtils.getFileStorageLocation() + File.separator + tenantCode;
```
Fix: Bind tenant from authenticated context (MDC/headers) not query param; enforce authorization before serving bytes; use signed URLs or tokenized access.  
Effort: 2–5 days  
Status: OPEN  
Found in branch: (scan-time)  
Date found: 2026-04-09

## GAP-025: DMS S3 util writes temp files using `urn` directly (path traversal arbitrary write/delete risk)

Service: trustt-platform-dms  
Lens: 10 (Security), 6 (Transaction boundaries/side effects)  
Risk: 🔴 High  
File: `trustt-platform-dms/src/main/java/in/novopay/dms/aws/S3ServiceUtil.java`  
Line: `uploadToBucket`, `downloadFromBucket`  
Description: Uses `new File(urn)` and deletes `Path.of(urn)` in finally; if `urn` can contain path separators, it can write/delete arbitrary files.  
Failure scenario: Crafted `urn` → overwrite/delete server files; potential RCE pivot depending on file locations.  
Financial impact: Service compromise, data loss.  
Evidence:
```56:67:trustt-platform-dms/src/main/java/in/novopay/dms/aws/S3ServiceUtil.java
file = new File(urn);
FileUtils.writeByteArrayToFile(file, content);
```
```88:94:trustt-platform-dms/src/main/java/in/novopay/dms/aws/S3ServiceUtil.java
Files.delete(Path.of(urn));
```
Fix: Write temp files to a fixed safe directory using generated filenames; validate `urn` against strict regex; never use user-influenced paths directly.  
Effort: 1–2 days  
Status: OPEN  
Found in branch: (scan-time)  
Date found: 2026-04-09

## GAP-026: API Gateway logs decrypted secret keys and full request/response payloads (PII/secret leakage)

Service: trustt-platform-api-gateway  
Lens: 10 (Security & data leakage), 11 (Observability gaps)  
Risk: 🔴 High  
File: `.../SecureRequestAuthenticatorV2.java`, `.../MfiRequestResponseLogFilter.java`  
Line: debug logs  
Description: Gateway logs encrypted/decrypted keys and full request/response for allowed APIs, and logs request body on parsing errors.  
Failure scenario: Logs become a trove of secrets + customer payloads; insider or log access compromise leads to mass data leakage and potential forging of requests.  
Financial impact: Account takeover, fraud, compliance breach.  
Evidence:
```108:123:trustt-platform-api-gateway/src/main/java/in/novopay/apigateway/authentication/SecureRequestAuthenticatorV2.java
LOG.debug("Encrypted Secret Key: {}", encryptedClientKey);
LOG.debug("Decrypted Secret Key: {}", secretKey);
```
```88:90:trustt-platform-api-gateway/src/main/java/in/novopay/apigateway/filter/MfiRequestResponseLogFilter.java
LOG.debug("API request: {}", requestData);
```
Fix: Remove secret logging entirely; redact payload logs; gate with strict secure-debug toggle and masking utility.  
Effort: 1–3 days  
Status: OPEN  
Found in branch: (scan-time)  
Date found: 2026-04-09

## GAP-027: API Gateway outbound HttpClient trusts all certificates and disables hostname verification

Service: trustt-platform-api-gateway  
Lens: 10 (Security), 4 (Retry/circuit posture for outbound calls)  
Risk: 🔴 High  
File: `trustt-platform-api-gateway/src/main/java/in/novopay/apigateway/requestforward/HttpClientUtil.java`  
Line: SSL trust strategy  
Description: Request-forward client disables TLS verification (trust-all + NoopHostnameVerifier).  
Failure scenario: MITM interception of upstream calls; data tampering.  
Financial impact: Fraud and data compromise across forwarded requests.  
Evidence:
```189:206:trustt-platform-api-gateway/src/main/java/in/novopay/apigateway/requestforward/HttpClientUtil.java
SSLContext sslContext = SSLContexts.custom().loadTrustMaterial(null, new TrustStrategy() {
  public boolean isTrusted(X509Certificate[] chain, String authType) { return true; }
}).build();
SSLConnectionSocketFactory factory = new SSLConnectionSocketFactory(sslContext, NoopHostnameVerifier.INSTANCE);
```
Fix: Enforce proper truststore and hostname verification; fail fast on invalid certs; add config-driven TLS.  
Effort: 1–2 days  
Status: OPEN  
Found in branch: (scan-time)  
Date found: 2026-04-09

## GAP-028: Authorization service logs access tokens and has doc-vs-config drift for Kafka usage

Service: trustt-platform-authorization  
Lens: 10 (Security), 12 (Dead code/ghost infra), 11 (Observability)  
Risk: 🔴 High  
File: `GetMapMyIndiaAccessTokenProcessor.java`, `deploy/application/messagebroker/MessageBroker.xml`, `CLAUDE.md`  
Line: token log + broker enabled vs doc claim  
Description: Service logs MapMyIndia access token; MessageBroker.xml enables producer and includes plaintext SSL passwords + legacy TLS; service doc claims no Kafka usage.  
Failure scenario: Token leakage + Kafka SSL secret exposure; operators assume Kafka unused but it is configured/enabled leading to unmanaged event behavior.  
Financial impact: Secret leakage; operational misconfiguration risk.  
Evidence:
```28:33:trustt-platform-authorization/src/main/java/in/novopay/authorization/processor/GetMapMyIndiaAccessTokenProcessor.java
LOG.info("Access token: {}", accessToken);
```
```3:19:trustt-platform-authorization/deploy/application/messagebroker/MessageBroker.xml
<ssl.truststore.password>novopay</ssl.truststore.password>
<ssl.enabled.protocols>TLSv1.2,TLSv1.1,TLSv1</ssl.enabled.protocols>
```
Fix: Remove token logging; rotate Kafka secrets; restrict TLS to 1.2+; align docs with runtime config; disable Kafka producer if truly unused.  
Effort: 1–3 days  
Status: OPEN  
Found in branch: (scan-time)  
Date found: 2026-04-09

## GAP-029: Masterdata business-date cache invalidation failures are non-fatal (platform-wide business-date drift risk)

Service: trustt-platform-masterdata-management  
Lens: 1 (Exception swallowing), 5 (Contract/state drift), 11 (Observability gaps)  
Risk: 🔴 High  
File: `BusinessDateItemWriter.java`  
Line: catch-and-continue around cache remove/set  
Description: Writer persists business date to DB but cache invalidation is best-effort and failures are swallowed.  
Failure scenario: DB business date changes but Redis cache still serves old date; downstream services compute `job_time` and cutoffs incorrectly until cache is refreshed.  
Financial impact: Wrong cutoff dates → incorrect accrual/posting/batch behavior (money/state correctness).  
Evidence:
```35:46:trustt-platform-masterdata-management/src/main/java/in/novopay/masterdata/batch/writer/BusinessDateItemWriter.java
try {
    cacheClient.remove(...);
    cacheClient.set(...);
    removedCachedAPI(entities);
} catch(Exception ex) {
    LOGGER.error("Unable to remove cached business date, error: ",ex);
}
```
Fix: Make cache update part of correctness contract: either fail the step (so ops can retry) or write a “cache_refresh_required” marker and have a reliable refresher; add metric/alert.  
Effort: 1–3 days  
Status: OPEN  
Found in branch: (scan-time)  
Date found: 2026-04-09

## GAP-030: Task service has multiple replay/consistency risks (no TTL cache writes + async fire-and-forget + likely bug on taskId == 'null')

Service: trustt-platform-task  
Lens: 2 (Idempotency), 3 (Locks/TTL), 7 (Async/thread safety), 10 (Security)  
Risk: 🔴 High  
File: multiple (see evidence)  
Line: cache set without expiry; consumer logic; async notifications  
Description: Task service writes cache keys without expiry, uses fire-and-forget async notifications, and has a suspicious conditional that only processes when taskId equals `"null"`.  
Failure scenario: stale cache causes wrong routing/permissions; Kafka replays can re-close/delete tasks; `"null"` taskId path can skip completion updates or throw parsing errors.  
Financial impact: Workflow correctness issues: missed task closures, duplicate task side effects, operational debt; potential indirect money impact through collections workflows.  
Evidence:
```143:147:trustt-platform-task/src/main/java/in/novopay/task/mgmt/datamodel/dao/TaskDao.java
// expire for cache key will be -1
cacheClient.set(tenantCode, key, value, dbIndex);
```
```89:92:trustt-platform-task/src/main/java/in/novopay/task/mfi/consumer/FinnoneCollectionTaskCreationConsumer.java
if (StringUtils.isNotEmpty(taskId) && "null".equalsIgnoreCase(taskId)) {
    Optional<TaskEntity> taskEntity = taskDao.findOneById(Long.valueOf(taskId));
```
Fix: Enforce TTL on cache writes; fix taskId validation (`"null"` treated as empty); add idempotency keys/locks for consumer state transitions; replace runAsync common-pool usage with bounded executor and durable status tracking.  
Effort: 2–5 days  
Status: OPEN  
Found in branch: (scan-time)  
Date found: 2026-04-09

---

## Wave 1 gap mining — 2026-04-10 (`trustt-platform-lib` + `trustt-platform-accounting`)

**Method:** Exhaustive lens-oriented scan over all `src/main/java` sources (pattern grep for the 12 lenses + targeted file reads on hits). **Additive count:** +7 (GAP-031..037): **High 4**, **Medium 2**, **Low 1**. Does not re-open items already captured above (e.g. GAP-018..020, EncryptionUtil, Kafka swallow, async orchestration, disburse Redis TTL, time-based `client_reference_number` batch class, proactive refund / auto-closure writers).

### GAP-031: Redis cache `set` without TTL is a first-class API (unbounded key lifetime)

- Service: trustt-platform-lib  
- Lens: 3 (Distributed locks & TTL), 11 (Observability / stale state)  
- Risk: High  
- File: `trustt-platform-lib/infra-cache/src/main/java/in/novopay/infra/cache/RedisCacheClient.java`  
- Line/Method: `RedisCacheClient#set(String tenantCode, String key, Object value, String dbIndex)` (and delegating `NovopayCacheClient#set` / `CacheDataService`)  
- Description: The 4-arg overload calls Spring `opsForValue().set(key, value)` with **no expiry**. Any caller using this overload (vs the 5-arg TTL overload) creates keys that live until explicit delete or manual flush.  
- Failure scenario: Memory growth, stale authoritative cache entries, and “stuck” behaviour if a key was meant as a short-lived marker but no TTL was passed (distinct from known disbursement-specific keys but same primitive risk).  
- Financial impact: Wrong cached master/product/accounting rules served; operational incidents requiring Redis surgery; indirect money-flow risk if cache drives decisions.  
- Evidence:
```64:67:trustt-platform-lib/infra-cache/src/main/java/in/novopay/infra/cache/RedisCacheClient.java
	@Override
	public void set(String tenantCode, String key, Object value, String dbIndex) {
		getRedisTemplate(dbIndex).opsForValue().set(getTenantSpecificKey(tenantCode,key), value);
	}
```
- Fix: Deprecate non-TTL `set` for production paths; require TTL or default sensible max TTL; static analysis / CI rule to flag call sites; document allowed exceptions (if any).  
- Effort: 2–4 days (API hardening + call-site audit)  
- Status: OPEN  
- Date found: 2026-04-10

### GAP-032: Paytm remittance client logs bearer token and full API response at INFO

- Service: trustt-platform-lib  
- Lens: 10 (Security & data leakage), 11 (Observability)  
- Risk: High  
- File: `trustt-platform-lib/infra-transaction-paytm/src/main/java/in/novopay/infra/transaction/paytm/common/PaytmApiClient.java`  
- Line/Method: `invokeApi`  
- Description: Logs `Authorization` token and raw Paytm HTTP response at INFO.  
- Failure scenario: Log aggregation exposes live credentials and transaction payloads; insider or log-store breach enables API abuse and PII leakage.  
- Financial impact: Fraudulent transfers / status inquiries; regulatory breach.  
- Evidence:
```68:86:trustt-platform-lib/infra-transaction-paytm/src/main/java/in/novopay/infra/transaction/paytm/common/PaytmApiClient.java
		String authToken = getAuhtorizationToken(agentId);
		LOG.info("Authorization Token: {}", authToken);
		// ...
				response = getToApiGateway(txnUrl + apiName, headers, requestName);
				LOG.info("Paytm Remittance Response: {}", response);
```
- Fix: Remove token/response body logging; use correlation id + masked outcome; DEBUG behind secure flag if needed.  
- Effort: 0.5–1 day  
- Status: OPEN  
- Date found: 2026-04-10

### GAP-033: Shared `HttpClientUtil` logs keystore password and builds trust-all-style TLS tunnel

- Service: trustt-platform-lib  
- Lens: 10 (Security), 4 (Outbound HTTP hardening)  
- Risk: High  
- File: `trustt-platform-lib/infra-transaction-interface/src/main/java/in/novopay/infra/util/HttpClientUtil.java`  
- Line/Method: `enableHttpsTunnelWithCertificate`  
- Description: Logs certificate path **and password** at INFO; uses `TrustSelfSignedStrategy` and `NoopHostnameVerifier` for the constructed client.  
- Failure scenario: Keystore password in logs; MITM or hostile cert acceptance if this client is used against non-trusted endpoints.  
- Financial impact: Credential leak; possible interception of bank/partner traffic depending on deployment.  
- Evidence:
```167:179:trustt-platform-lib/infra-transaction-interface/src/main/java/in/novopay/infra/util/HttpClientUtil.java
	public static CloseableHttpClient enableHttpsTunnelWithCertificate(String certificatePath, String certificatePassword) {
		LOG.info("Inside Enable HTTPS Tunnel with certificate With Path :{} AND certificate Password: {}"+ certificatePath +" "+certificatePassword);
		// ...
			SSLConnectionSocketFactory factory = new SSLConnectionSocketFactory(sslContext, NoopHostnameVerifier.INSTANCE);
```
- Fix: Never log passwords; use standard truststore + hostname verification for production; isolate mTLS setup behind explicit config profile.  
- Effort: 1–2 days  
- Status: OPEN  
- Date found: 2026-04-10

### GAP-034: Same-service internal API path logs full request JSON when callee returns FAIL

- Service: trustt-platform-lib  
- Lens: 10 (Security & data leakage), 11 (Observability)  
- Risk: High  
- File: `trustt-platform-lib/infra-navigation/src/main/java/in/novopay/infra/api/client/NovopayInternalAPIClient.java`  
- Line/Method: `doSameServiceCall`  
- Description: On `status == FAIL`, logs entire `requestString` built from the outgoing internal API map at INFO.  
- Failure scenario: Failed money/servicing calls write full payloads (PII, amounts, account identifiers) into centralized logs.  
- Financial impact: Compliance incident; easier lateral abuse if logs are compromised.  
- Evidence:
```88:92:trustt-platform-lib/infra-navigation/src/main/java/in/novopay/infra/api/client/NovopayInternalAPIClient.java
		if ("FAIL".equalsIgnoreCase(responseStatus)) {
			LOG.info("Internal API Call Failed for API: {}, Request: {}", apiName, requestString);
			NovopayFatalException e = new NovopayFatalException((String) newExecutionContext.get("code"),(String) newExecutionContext.get("message"));
```
- Fix: Log only `apiName`, error code/message, `stan`, and hashed/redacted identifiers; never full JSON body.  
- Effort: 0.5–1 day  
- Status: OPEN  
- Date found: 2026-04-10

### GAP-035: Loan installment SMS notification batch writers swallow all exceptions per row

- Service: trustt-platform-accounting  
- Lens: 1 (Exception swallowing), 11 (Observability), 8 (Batch job safety)  
- Risk: Medium  
- File: `trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/notifications/loaninstallmentduenotificationjob/LoanInstallmentDueNotificationWriter.java`, `.../loaninstallmentbouncenotificationjob/LoanInstallmentBounceNotificationWriter.java`  
- Line/Method: `write`  
- Description: Per-row `try/catch (Exception)` logs and continues; chunk/step can still complete successfully.  
- Failure scenario: Kafka publish or upstream customer fetch fails silently for some loans → no SMS; operations assume job success.  
- Financial impact: Collections communication gap; repayment behaviour risk; SLA/support load (not direct double-post).  
- Evidence:
```96:113:trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/notifications/loaninstallmentduenotificationjob/LoanInstallmentDueNotificationWriter.java
				try {
					// ... build SMS payload, pushDataToKafkaQueue
				} catch (Exception e) {
					logger.error("",e);
				}
```
- Fix: Fail the chunk or use skip policy with persisted failure rows + metrics; alert on any notification publish failure.  
- Effort: 1–2 days  
- Status: OPEN  
- Date found: 2026-04-10

### GAP-036: Bulk collection failed-record Kafka consumer has no validation, dedupe, or error handling

- Service: trustt-platform-accounting  
- Lens: 2 (Idempotency), 11 (Observability), 5 (Contract)  
- Risk: Medium  
- File: `trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/recurring/entity/BulkCollectionFailedRecordConsumer.java`  
- Line/Method: `computeRecords`  
- Description: Blindly persists `consumerRec.value()` to `BulkCollectionLog` with no try/catch, no idempotency key, no schema validation.  
- Failure scenario: Poison message fails the poll loop; or replay creates duplicate log rows; malformed payload breaks save and retries indefinitely.  
- Financial impact: Operational noise; obscured collection failure analysis; possible consumer stall.  
- Evidence:
```20:28:trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/recurring/entity/BulkCollectionFailedRecordConsumer.java
	public void computeRecords(ConsumerRecords<String, String> records, PlatformTenant tenant) {
		for (ConsumerRecord<String, String> consumerRec : records) {
			String consumerRecords = consumerRec.value();
			BulkCollectionLog bulkCollectionLog = new BulkCollectionLog();
			bulkCollectionLog.setFailedRecord(consumerRecords);
			bulkCollectionLog.setCreatedOn(new Date());
			bulkCollectionLogDaoService.save(bulkCollectionLog);
		}
	}
```
- Fix: Validate payload; surround with typed error handling + DLQ; dedupe by offset/topic/partition or business key; align with `.cursor/event-registry.md` risk flags.  
- Effort: 1–3 days  
- Status: OPEN  
- Date found: 2026-04-10

### GAP-037: NOC file job swallows customer pincode lookup failures and continues with blank pincode

- Service: trustt-platform-accounting  
- Lens: 1 (Exception swallowing), 8 (Batch job safety)  
- Risk: Low  
- File: `trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/bulknoc/dispatch/generatenocfilejob/GenerateNocFileItemWriter.java`  
- Line/Method: `getPincode`  
- Description: Catches broad `Exception`, logs a generic INFO message, returns `pincode` unchanged (may be blank) → directory path may omit pincode segment.  
- Failure scenario: NOC files land in wrong folder or collide; harder to retrieve by expected path.  
- Financial impact: Operational/doc retrieval issues; low direct money risk.  
- Evidence:
```107:113:trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/bulknoc/dispatch/generatenocfilejob/GenerateNocFileItemWriter.java
		try {
			pincode = getCustomerPincodeFromCustomerId(loanAccountEntity.getCustomerId(), localExecutionContext);
		}catch (Exception e){
			LOG.info(ERROR_WHILE_CALLING_GET_CUSTOMER_DETAILS);
		}
		return pincode;
```
- Fix: Fail fast or mark row failed when pincode mandatory; structured log with `customer_id` / LAN.  
- Effort: 0.5–1 day  
- Status: OPEN  
- Date found: 2026-04-10

---

## Wave 2 gap mining — 2026-04-10 (`trustt-platform-los` + `trustt-platform-payments`)

**Method:** Enumerated all `src/main/java` sources + orchestration XML under `deploy/application/orchestration/`; grep for 12 lenses; deep read on disburse → accounting, `bulk_collection_data`, collection repayment/LMS push, Kafka producers/consumers.

### GAP-038: LOS Kafka producer uses null message key for `disburse_loan_api_` (and other LOS topics)

- Service: trustt-platform-los  
- Lens: 5 (Contract / ordering), 7 (Async), 2 (Idempotency coupling)  
- Risk: High  
- File: `trustt-platform-los/src/main/java/in/novopay/los/kafka/LosMessageKafkaProducer.java`  
- Line/Method: `pushDataToKafkaQueue(String tenantCode, String message, String topicPrefix, Map<String, String> headers)`  
- Description: Calls `novopayKafkaProducer.sendMessage(..., null, message, headers, null)` — **record key is always null**, so partition assignment is not stable per `external_ref_number` / loan.  
- Failure scenario: Messages for the same disbursement can land on different partitions → ordering not guaranteed across retries; harder to reason about replay and consumer side effects.  
- Financial impact: Contributes to race/reordering risk on async disburse path (pairs with consumer idempotency — see table rows on Redis + accounting consumer).  
- Evidence:
```51:62:trustt-platform-los/src/main/java/in/novopay/los/kafka/LosMessageKafkaProducer.java
    public void pushDataToKafkaQueue(String tenantCode, String message, String topicPrefix,
        Map<String, String> headers) {
        NovopayKafkaProducer novopayKafkaProducer = (NovopayKafkaProducer) context.getBean("NovopayKafkaProducer");
        StringBuilder stringBuilder = new StringBuilder();
        if (StringUtils.isNotBlank(topicPrefix)) {
            stringBuilder.append(topicPrefix.toLowerCase());
        }
        stringBuilder.append(tenantCode);
        if (StringUtils.isNotBlank(environment)) {
            stringBuilder.append("_").append(environment.toLowerCase());
        }
        novopayKafkaProducer.sendMessage(stringBuilder.toString(), null, message, headers, null);
    }
```
- Fix: Set Kafka key to stable business id (e.g. `external_ref_number` or parsed from pipe-payload); align with accounting consumer partition strategy.  
- Effort: 1–2 days + regression on replay  
- Status: OPEN  
- Date found: 2026-04-10

### GAP-039: LOS disbursement sync consumer logs full Kafka payload map at INFO

- Service: trustt-platform-los  
- Lens: 10 (Security & data leakage), 11 (Observability)  
- Risk: High  
- File: `trustt-platform-los/src/main/java/in/novopay/los/kafka/DisbursementSyncConsumer.java`  
- Line/Method: `computeRecords`  
- Description: After JSON parse, logs entire `clientMap` at INFO — includes status, errors, and any other fields present on the sync message.  
- Failure scenario: Central logs accumulate PII/financial sync payloads at default log level.  
- Financial impact: Compliance / breach risk; easier reconstruction of customer/loan identifiers from logs.  
- Evidence:
```40:43:trustt-platform-los/src/main/java/in/novopay/los/kafka/DisbursementSyncConsumer.java
                Map<String, Object> clientMap = objectMapper.readValue(consumerRec.value(), Map.class);
                executionContext.putAll(clientMap);
                LOG.info("Disbursement Sync Consumer Record: {}", clientMap);
                disbursementSyncService.handleDisbursementSyncRecord(executionContext);
```
- Fix: Log correlation fields only (`external_ref_number`, `tenant_code`, `status`, `error_code`, offset); redact body.  
- Effort: 0.5–1 day  
- Status: OPEN  
- Date found: 2026-04-10

### GAP-040: LOS Kafka “wakeup” posts dummy `{}` to `disburse_loan_api_mfi_*` on startup

- Service: trustt-platform-los  
- Lens: 7 (Async & side effects), 12 (Ghost / surprising infra), 11 (Observability)  
- Risk: Medium  
- File: `trustt-platform-los/src/main/java/in/novopay/los/kafka/LosMessageKafkaProducer.java`  
- Line/Method: `wakeupKafkaProducer` (`@PostConstruct`)  
- Description: `CompletableFuture.runAsync` builds topic `disburse_loan_api_` + hardcoded tenant `mfi` + env suffix and sends `"{}"` with **null** key to “wake” the producer.  
- Failure scenario: Accounting consumer may process/no-op junk messages; metrics/alerts noise; misleading load on disburse topic; wrong tenant if multi-tenant differs from `mfi`.  
- Financial impact: Low direct money risk if consumer rejects empty payload; operational and monitoring confusion.  
- Evidence:
```90:98:trustt-platform-los/src/main/java/in/novopay/los/kafka/LosMessageKafkaProducer.java
            LOG.info("Wakeup Kafka: producer obtained, {}", System.currentTimeMillis());
            StringBuilder stringBuilder = new StringBuilder();
            stringBuilder.append("disburse_loan_api_");
            stringBuilder.append("mfi");//setting default tenant as thread local context is empty
            if (StringUtils.isNotBlank(environment)) {
                stringBuilder.append("_").append(environment.toLowerCase());
            }
            LOG.debug("Pushing an empty message to test the producer");
            novopayKafkaProducer.sendMessage(stringBuilder.toString(), null, "{}", null);
```
- Fix: Use admin client / metadata ping or dedicated health topic; never publish to production disburse topic; drive tenant from config explicitly.  
- Effort: 1–2 days  
- Status: OPEN  
- Date found: 2026-04-10

### GAP-041: LOS `DisburseLoanAPIUtil` logs full pipe-delimited disburse request at DEBUG

- Service: trustt-platform-los  
- Lens: 10 (Security & data leakage)  
- Risk: Medium  
- File: `trustt-platform-los/src/main/java/in/novopay/los/util/DisburseLoanAPIUtil.java`  
- Line/Method: `callDisburseLoanAPI`  
- Description: `LOG.debug("Disburse Loan Request: {}", request)` where `request` is `apiName|full_json|cacheKey`.  
- Failure scenario: DEBUG enabled in prod → full disburse payloads in logs.  
- Financial impact: PII / financial data leakage.  
- Evidence:
```69:70:trustt-platform-los/src/main/java/in/novopay/los/util/DisburseLoanAPIUtil.java
            request = apiName+"|" + request +"|"+cacheKey;
            LOG.debug("Disburse Loan Request: {}", request);
```
- Fix: Log cache key hash + `external_ref_number` only; never full JSON.  
- Effort: 0.5 day  
- Status: OPEN  
- Date found: 2026-04-10

### GAP-042: Payments `PaymentsKafkaProducer` always sends null Kafka record key

- Service: trustt-platform-payments  
- Lens: 5 (Contract / ordering), 2 (Replay semantics)  
- Risk: High  
- File: `trustt-platform-payments/src/main/java/in/novopay/payments/common/util/PaymentsKafkaProducer.java`  
- Line/Method: `pushDataToKafkaQueue`  
- Description: `sendMessage(stringBuilder.toString(), null, message, null)` — key always null for **collection_primary_allocation_**, **collection_secondary_allocation_**, **collection_task_processing_**, etc.  
- Failure scenario: No per-collection or per-group ordering guarantee; duplicate/reordered messages harder to diagnose; amplifies at-least-once consumer quirks.  
- Financial impact: Indirect collections/allocation correctness and operational risk; pairs with consumer idempotency design.  
- Evidence:
```19:27:trustt-platform-payments/src/main/java/in/novopay/payments/common/util/PaymentsKafkaProducer.java
    public void pushDataToKafkaQueue(String message, String topic) {
        String tenantCode = ThreadLocalContext.getTenant().getTenantCode();
        NovopayKafkaProducer novopayKafkaProducer = (NovopayKafkaProducer) context.getBean("NovopayKafkaProducer");
        StringBuilder stringBuilder = new StringBuilder(topic.toLowerCase());
        stringBuilder.append(tenantCode);
        if (StringUtils.isNotBlank(environment)) {
            stringBuilder.append("_").append(environment.toLowerCase());
        }
        novopayKafkaProducer.sendMessage(stringBuilder.toString(), null, message, null);
    }
```
- Fix: Pass stable key (e.g. first `col_ext_ref_id` / `np_collection_id` from JSON batch); document per-topic key policy.  
- Effort: 2–4 days (consumers + producers + QA)  
- Status: OPEN  
- Date found: 2026-04-10

### GAP-043: Bulk collection consumer declares success/failure trackers that are never populated

- Service: trustt-platform-payments  
- Lens: 11 (Observability), 1 (Misleading control flow)  
- Risk: Medium  
- File: `trustt-platform-payments/src/main/java/in/novopay/payments/collections/mfi/consumer/CreateOrUpdateBulkCollectionConsumer.java`  
- Line/Method: `computeRecords`  
- Description: Local `failedRecords` / `successCollectionRefs` at top of loop are **never passed** into `processCollectionData` (which uses its own maps). INFO logs reporting “successful collections processed” / “failed collections” use the **outer** lists and misstate reality (typically always zero).  
- Failure scenario: Ops and SRE cannot trust logs for bulk ingestion health; incidents mis-triaged.  
- Financial impact: Delayed detection of LCS–LMS collection pipeline issues.  
- Evidence:
```73:99:trustt-platform-payments/src/main/java/in/novopay/payments/collections/mfi/consumer/CreateOrUpdateBulkCollectionConsumer.java
                Map<String, JSONObject> failedRecords = new HashMap<>();
                List<String> successCollectionRefs = new ArrayList<>();
                // ...
                    processedCollections = processCollectionData(extIdEntityMap, extIdCollDetMap, requestTimeStamp);
                    processCollectionForAllocation(processedCollections);
                }
                if (!failedRecords.isEmpty()) {
                    LOGGER.info("Total failed records : {}", failedRecords.size());
                }
                LOGGER.info("Total number of successful collections processed : {}", successCollectionRefs.size());
```
- Fix: Return `failedRecords`/counts from `processCollectionData` or use shared structure; log actual sizes from inner maps.  
- Effort: 0.5–1 day  
- Status: OPEN  
- Date found: 2026-04-10

### GAP-044: Bulk collection consumer drops poison/invalid JSON messages without failing the poll

- Service: trustt-platform-payments  
- Lens: 1 (Exception handling), 11 (Observability), 2 (Data loss)  
- Risk: High  
- File: `trustt-platform-payments/src/main/java/in/novopay/payments/collections/mfi/consumer/CreateOrUpdateBulkCollectionConsumer.java`  
- Line/Method: `parseData`, `computeRecords`  
- Description: `parseData` catches parse exceptions, logs, returns **null**; caller skips processing when `bulkCollectionDetails == null` but does **not** rethrow — consumer completes normally → offset can commit with **no** DLQ / failed-record publish for that message.  
- Failure scenario: Permanent silent loss of bulk collection payload on bad JSON or schema drift.  
- Financial impact: Missing collection rows in LCS vs accounting expectation; reconciliation gaps.  
- Evidence:
```128:138:trustt-platform-payments/src/main/java/in/novopay/payments/collections/mfi/consumer/CreateOrUpdateBulkCollectionConsumer.java
    private JSONObject parseData(String dataString) {
        JSONParser parser = new JSONParser();
        JSONObject collectionData = null;
        try {
            collectionData = (JSONObject) parser.parse(dataString);
        } catch(Exception e) {
            LOGGER.error("Error while parsing collection details ", e);
            // What to throw here
            // Do we need to push here
        }
        return collectionData;
    }
```
- Fix: On parse failure, push raw payload to `bulk_collection_data_failed_` (or DLQ) and/or throw to trigger retry with cap; never commit without explicit handling policy.  
- Effort: 1–2 days  
- Status: OPEN  
- Date found: 2026-04-10

### GAP-064: Bulk collection consumer NPE when `collection_list` is absent

- Service: trustt-platform-payments  
- Lens: 1 (Exception handling), 2 (Data loss / stuck consumer)  
- Risk: Medium  
- File: `trustt-platform-payments/src/main/java/in/novopay/payments/collections/mfi/consumer/CreateOrUpdateBulkCollectionConsumer.java`  
- Line/Method: `computeRecords` after successful `parseData`  
- Description: When `bulkCollectionDetails != null` but **`collection_list` key is missing or null**, `(JSONArray) bulkCollectionDetails.get("collection_list")` yields null and **`collectionList.size()`** throws **NPE**. Related to **GAP-044** (parse returns null) but distinct: **valid JSON**, wrong shape.  
- Failure scenario: Consumer thread fails; behaviour depends on framework — possible stuck partition / retry storm until message skipped.  
- Financial impact: Bulk collection batch not applied in payments LCS for that offset; divergence vs accounting until replay or manual fix.  
- Evidence:
```81:83:trustt-platform-payments/src/main/java/in/novopay/payments/collections/mfi/consumer/CreateOrUpdateBulkCollectionConsumer.java
                    String requestTimeStamp = consumerUtility.getStringValue(bulkCollectionDetails, "timestamp");
                    collectionList = (JSONArray) bulkCollectionDetails.get("collection_list");
                    LOGGER.info("Total number of collections to be processed : {}", collectionList.size());
```
- Fix: Null/empty guard on `collection_list`; treat as parse-level failure → DLQ / failed-record topic (**GAP-044** pattern).  
- Effort: 0.5 day  
- Status: OPEN  
- Date found: 2026-04-17 (Flow Sync Wave 3)

### GAP-045: Field collection path suppresses SMS / leader notification after collection rows are persisted

- Service: trustt-platform-payments  
- Lens: 1 (Exception swallowing), 11 (Observability), 6 (Ordering vs side effects)  
- Risk: High  
- File: `trustt-platform-payments/src/main/java/in/novopay/payments/collections/mfi/repository/MfiCollectionsDAOService.java`  
- Line/Method: block after `collectionsRepository.saveAll` in collection completion path  
- Description: `sendSms` + `sendNotificationToLeader` wrapped in `try/catch` that logs **“Suppressing execption”** and swallows all exceptions **after** DB saves for the collection transaction.  
- Failure scenario: Money/collection state is committed in LCS but customer/group notifications never fire; no fatal to caller.  
- Financial impact: Customer unaware of payment; group leader not notified; support churn — **not** double-charge, but **paired inconsistency** between money trail and comms.  
- Evidence:
```501:508:trustt-platform-payments/src/main/java/in/novopay/payments/collections/mfi/repository/MfiCollectionsDAOService.java
       try {
           sendSms( sendSMSList);
           sendNotificationToLeader(executionContext, groupId, clientCode, collectionsRefNumber, loanAccountNumbers);
       } catch(Exception e) {
         LOG.error("Suppressing execption: Unable to send the SMS through kafka",e);
       }
```
- Fix: Structured retry/DLQ for notifications; metrics; optional compensating alert; do not swallow without durable outbox.  
- Effort: 2–4 days  
- Status: OPEN  
- Date found: 2026-04-10

---

## Wave 3 gap mining — 2026-04-10 (`trustt-platform-task` + `trustt-platform-actor` + `trustt-platform-batch`)

**Method:** Enumerated Java under `src/main/java` (task ~307, actor ~2133, batch ~99); grep for 12 lenses; deep read on batch scheduler (`AutoScheduler`, `SchedulingGroupProcessor`, `SchedulerCommonService`, `ScheduleBatchGroupExecutor`), task Kafka consumers + expiry batch writer, actor `ActorKafkaProducer` (null key cited in edge doc only — same pattern as GAP-042).

### GAP-046: Batch `AutoScheduler` loads schedules only for the first tenant in `getAllTenants()`

- Service: trustt-platform-batch  
- Lens: 3 (Multi-tenant), 12 (Operational surprise), 11 (Observability)  
- Risk: High  
- File: `trustt-platform-batch/src/main/java/in/novopay/batch/core/service/AutoScheduler.java`  
- Line/Method: `onLoadScheduleGroups` (`@PostConstruct`)  
- Description: `platformTenantList.get(0)` is used as the sole tenant for `batchScheduleService.autoSchedule(context)` on startup. Order is whatever `getAllTenants()` returns; **other tenants never get this bootstrap path** on this JVM.  
- Failure scenario: In multi-tenant deployments, schedules for non-first tenants may not register until a separate API/manual path runs; missed EOD windows for those tenants.  
- Financial impact: Missed batch triggers (e.g. accounting-adjacent jobs) for affected tenants → stale data, SLA breaches.  
- Evidence:
```30:37:trustt-platform-batch/src/main/java/in/novopay/batch/core/service/AutoScheduler.java
    public void onLoadScheduleGroups(){
       try {
           List<PlatformTenant> platformTenantList = tenantDetailsDAOService.getAllTenants();
           PlatformTenant batchPlatformTenant = platformTenantList.get(0);
           ThreadLocalContext.setTenant(batchPlatformTenant);
           MDC.put("tenant",batchPlatformTenant.getTenantCode());
           ExecutionContext context=batchExecutionContextHelper.buildExecutionContext();
           batchScheduleService.autoSchedule(context);
```
- Fix: Iterate all active tenants (or config-driven list) and call `autoSchedule` per tenant with correct `ThreadLocalContext`; or document single-tenant-only deployment and enforce.  
- Effort: 1–2 days + QA per tenant  
- Status: OPEN  
- Date found: 2026-04-10

### GAP-047: `TriggerNotificationsProcessor` swallows all exceptions (escalation path)

- Service: trustt-platform-task  
- Lens: 1 (Exception swallowing), 11 (Observability)  
- Risk: Medium  
- File: `trustt-platform-task/src/main/java/in/novopay/task/mgmt/processor/TriggerNotificationsProcessor.java`  
- Line/Method: `process`  
- Description: Outer `try/catch (Exception e)` only logs — no `NovopayFatalException` / rethrow — so upstream orchestration can succeed while **no notifications** were sent.  
- Failure scenario: TAT / escalation notifications silently skipped; ops discovers only via user complaints.  
- Financial impact: SLA and compliance exposure on task workflows (not direct money movement).  
- Evidence:
```32:48:trustt-platform-task/src/main/java/in/novopay/task/mgmt/processor/TriggerNotificationsProcessor.java
    protected void process(ExecutionContext executionContext) throws NovopayFatalException, NovopayNonFatalException {
        try {
            // ...
        } catch (Exception e) {
            LOGGER.error("An error occurred during processing escalation notifications", e);
        }
    }
```
- Fix: Classify errors; fail the step for non-retryable config errors; metrics + DLQ for notification failures.  
- Effort: 1–2 days  
- Status: OPEN  
- Date found: 2026-04-10

### GAP-048: Reject-expired task batch writer uses hardcoded `user_id` = `"2"` for workflow API callback

- Service: trustt-platform-task  
- Lens: 10 (Audit / identity), 8 (Compliance)  
- Risk: High  
- File: `trustt-platform-task/src/main/java/in/novopay/batch/writer/RejectExpiredBatchJobItemWriter.java`  
- Line/Method: `write`  
- Description: `executionContext.putLocal("user_id", "2");` before `taskWorkflowAPIExecutionService.callAPI` — all auto-rejects appear as user **2**, not a system service account or configurable actor.  
- Failure scenario: Audit trail and maker-checker attribution wrong; investigations misattribute automated expiry rejects.  
- Financial impact: Compliance / forensic traceability weakness on task-driven approvals tied to loans/collections.  
- Evidence:
```99:105:trustt-platform-task/src/main/java/in/novopay/batch/writer/RejectExpiredBatchJobItemWriter.java
                try {
                    executionContext.putLocal("run_mode", "REAL");
                    executionContext.putLocal("task_id", Long.toString(task.getId()));
                    executionContext.putLocal("user_id", "2");
                    taskWorkflowAPIExecutionService.callAPI(executionContext, taskTypeApiExecutionEntity.getApiName(),
                            taskTypeApiExecutionEntity.getApiFunctionCode(),
                            taskTypeApiExecutionEntity.getApiFunctionSubCode(), request);
```
- Fix: Use dedicated system user id from tenant config; document in runbooks; migrate audit if needed.  
- Effort: 0.5–1 day + config rollout  
- Status: OPEN  
- Date found: 2026-04-10

### GAP-049: Batch scheduler runnables set `ThreadLocalContext` tenant but do not clear it (pool threads)

- Service: trustt-platform-batch  
- Lens: 3 (Multi-tenant / thread safety), 7 (Async)  
- Risk: High  
- File: `trustt-platform-batch/src/main/java/in/novopay/batch/core/service/ScheduleBatchGroupExecutor.java` (and related: `DirectGroupJobExecutor`, `DirectJobExecutor` — `setTenant` in `run()` without `ThreadLocalContext.clear()` in `finally`)  
- Line/Method: `ScheduleBatchGroupExecutor#run`  
- Description: `ThreadLocalContext.setTenant(platformTenant)` then work; **only** `MDC.clear()` at end — **tenant ThreadLocal can remain** on the scheduler thread when it is returned to `ThreadPoolTaskScheduler`’s pool. Next task on that thread can inherit wrong tenant.  
- Failure scenario: Cross-tenant batch actions, wrong `job_time`/cache key clears (`setJobTime` uses tenant), or wrong internal API routing.  
- Financial impact: Wrong-tenant job triggers or metadata — severity depends on downstream job (potential accounting invocation).  
- Evidence:
```62:89:trustt-platform-batch/src/main/java/in/novopay/batch/core/service/ScheduleBatchGroupExecutor.java
    public void run(){
        ThreadLocalContext.setTenant(platformTenant);
        MDC.put("tenant",platformTenant.getTenantCode());
        // ...
        if(canStart){
            batchScheduleService.updateExecutionRunningState(batchScheduleId);
            this.schedulerCommonService.processJobs(this.jobs,batchScheduleId,executionContext);
        }else{
            batchScheduleService.updateNextRun(batchSchedule);
            LOGGER.info("ScheduleID {} is already running for group name {} ",batchSchedule.getId(),batchGroup.getName());
        }
        MDC.clear();
    }
```
```47:73:trustt-platform-batch/src/main/java/in/novopay/batch/core/service/DirectJobExecutor.java
    public void run(){
        ThreadLocalContext.setTenant(platformTenant);
        MDC.put("tenant",platformTenant.getTenantCode());
        startNormalJob();
    }
    // startNormalJob finally: MDC.clear() only — no ThreadLocalContext clear
```
- Fix: `try/finally { ThreadLocalContext.clear(); MDC.clear(); }` on every scheduler runnable and on `setCompletionStatus` worker threads.  
- Effort: 0.5–1 day + multi-tenant regression  
- Status: OPEN  
- Date found: 2026-04-10

### GAP-050: Scheduler marks job dependency satisfied when target job is “already running”

- Service: trustt-platform-batch  
- Lens: 2 (Idempotency / lifecycle), 11 (Observability)  
- Risk: Medium  
- File: `trustt-platform-batch/src/main/java/in/novopay/batch/core/service/SchedulerCommonService.java`  
- Line/Method: `setCompletionStatus`  
- Description: If `isJobRunning` is true, branch still does `jobCompletionStatus.put(job.getPriority(), true)` — dependent jobs proceed **without verifying** this run belongs to the current schedule or completed successfully.  
- Failure scenario: Stale RUNNING execution or another schedule’s run unblocks dependents incorrectly (pairs with multi-instance race in table row).  
- Financial impact: Out-of-order job groups if dependency graph is trusted cluster-wide.  
- Evidence:
```198:235:trustt-platform-batch/src/main/java/in/novopay/batch/core/service/SchedulerCommonService.java
            boolean isRunning = batchScheduleService.isJobRunning(job.getJobName());
            if (!isRunning) {
                // ... start job, wait, update status ...
 jobCompletionStatus.put(job.getPriority(), true);
            } else {
                LOGGER.debug("Scheduler cannot start job as this job {} is already running or dependencies not met!", job.getJobName());
                jobCompletionStatus.put(job.getPriority(), true);
            }
```
- Fix: Distinguish “skipped because ours is running” vs “dependency met”; use execution id / schedule id correlation; distributed lock (see multinode-batch.md).  
- Effort: 2–4 days  
- Status: OPEN  
- Date found: 2026-04-10

### GAP-051: `FinnoneCollectionTaskCreationConsumer#processForCreatePtp` guard is logically broken

- Service: trustt-platform-task  
- Lens: 1 (Control flow / defects), 2 (Data loss)  
- Risk: High  
- File: `trustt-platform-task/src/main/java/in/novopay/task/mfi/consumer/FinnoneCollectionTaskCreationConsumer.java`  
- Line/Method: `processForCreatePtp`  
- Description: Condition `StringUtils.isNotEmpty(taskId) && "null".equalsIgnoreCase(taskId)` requires `taskId` to be the literal `"null"`; real numeric ids never enter the block. If entered, `Long.valueOf("null")` throws. Intended logic was almost certainly **empty/null check** (inverted or wrong predicate).  
- Failure scenario: PTP / task completion updates never run for normal messages; or NPE/NFE if bad data hits the branch.  
- Financial impact: Wrong task state vs Finnone/collections expectations; operational rework.  
- Evidence:
```87:101:trustt-platform-task/src/main/java/in/novopay/task/mfi/consumer/FinnoneCollectionTaskCreationConsumer.java
    private void processForCreatePtp(DefaultExecutionContext executionContext, Map<String, Object> data)
            throws NovopayFatalException, NovopayNonFatalException {
        String taskId = (String) data.get(CollectionTaskConstants.TASK_ID);
        String userId = (String) data.get(MfiTaskConstants.USER_ID);
        if (StringUtils.isNotEmpty(taskId) && "null".equalsIgnoreCase(taskId)) {
            Optional<TaskEntity> taskEntity = taskDao.findOneById(Long.valueOf(taskId));
            if (taskEntity.isPresent()) {
                taskEntity.get().setCurrentStatus("COMPLETED");
                // ...
                taskDao.save(taskEntity.get());
            }
        }
        createTaskByTaskCodeProcessor.execute(executionContext);
    }
```
- Fix: Correct null/blank handling; add tests for CREATE_PTP payloads with real `task_id`.  
- Effort: 0.5–1 day  
- Status: OPEN  
- Date found: 2026-04-10

### GAP-052: `FinnoneCollectionTaskCreationConsumer` logs entire `ConsumerRecords` on parse error

- Service: trustt-platform-task  
- Lens: 11 (Observability / noise), 10 (PII in logs — if record bodies echo)  
- Risk: Medium  
- File: `trustt-platform-task/src/main/java/in/novopay/task/mfi/consumer/FinnoneCollectionTaskCreationConsumer.java`  
- Line/Method: `computeRecords`  
- Description: On exception, logs `records` (full batch) not just `consumerRec` — large log lines and possible payload duplication.  
- Evidence:
```81:83:trustt-platform-task/src/main/java/in/novopay/task/mfi/consumer/FinnoneCollectionTaskCreationConsumer.java
            } catch(Exception e) {
                LOGGER.error("Error while parsing the consumer record {}", records, e);
            }
```
- Fix: Log topic/partition/offset + single record value length or hash.  
- Effort: 0.25 day  
- Status: OPEN  
- Date found: 2026-04-10

### GAP-053: `rejectExpiredBatchJob` bean config sets `chunk` to `Integer.MAX_VALUE`

- Service: trustt-platform-task  
- Lens: 9 (Performance / memory), 6 (Transaction boundaries)  
- Risk: High  
- File: `trustt-platform-task/src/main/java/in/novopay/batch/config/RejectExpiredTasksBatchJobConfig.java`  
- Line/Method: `getJobBeanConfigParameters`  
- Description: `jobSetupParameters.put("chunk", Integer.MAX_VALUE)` is passed into `parallelBatchJobV2.setUpJobAdvanceV2(getJobBeanConfigParameters(), ...)` — can force **single-chunk** semantics with absurd upper bound vs `Constants.WORKER_CHUNK_SIZE` used only in `buildJobForTenant`’s step config. Risk of huge transaction, memory pressure, or framework misconfiguration depending on which path runs in prod.  
- Failure scenario: OOM, long DB locks, or rollback blast radius on reject-expired job.  
- Financial impact: Task expiry processing stalls or fails mid-flight; approval tasks left inconsistent.  
- Evidence:
```75:101:trustt-platform-task/src/main/java/in/novopay/batch/config/RejectExpiredTasksBatchJobConfig.java
    public  Map<String, Object> getJobBeanConfigParameters() {
        Map<String, Object> jobSetupParameters = new HashMap<>();
        jobSetupParameters.put("name", JOB_NAME);
        jobSetupParameters.put("grid_size", GRID_SIZE);
        jobSetupParameters.put("chunk", Integer.MAX_VALUE);
        return jobSetupParameters;
    }
    // ...
        	parallelBatchJobV2.setUpJobAdvanceV2(getJobBeanConfigParameters(), getJobSetupParameters(),customStepV2s);
```
- Fix: Align chunk with `Constants.WORKER_CHUNK_SIZE` (or explicit sane cap); verify which setup path production uses.  
- Effort: 0.5–1 day + batch QA  
- Status: OPEN  
- Date found: 2026-04-10

---

## Wave 4 gap mining — 2026-04-10 (masterdata, authorization, approval, audit, notifications, api-gateway, dms)

**Method:** Grep + targeted reads for 12 lenses; gateway filter URL patterns vs controllers; auth processors vs gateway contract.

### GAP-054: API Gateway `AuthorizationCheckFilter` skips permission check when `api_usecase_mapping` row is missing

- Service: trustt-platform-api-gateway  
- Lens: 10 (AuthZ bypass), 5 (Contract)  
- Risk: High  
- File: `trustt-platform-api-gateway/src/main/java/in/novopay/apigateway/filter/AuthorizationCheckFilter.java`  
- Line/Method: `doFilter`  
- Description: Permission is enforced only when `findOneByApiNameAndFunctionCodeAndFunctionSubCode` returns non-null. If the row is **absent** (migration gap, typo, new API), the filter **falls through** to `chain.doFilter` with **no** `checkPermissionByUsecase` call — **default-allow** for that combination.  
- Failure scenario: Sensitive API reachable with valid session + client auth but **without** mapped usecase / role check.  
- Financial impact: Unauthorized operations if mapping table is incomplete.  
- Evidence:
```74:100:trustt-platform-api-gateway/src/main/java/in/novopay/apigateway/filter/AuthorizationCheckFilter.java
		String apiName = (String) wrappedRequest.getAttribute(API_NAME);
		Map<String, Object> bodyHeaderMap = (Map<String, Object>) wrappedRequest.getAttribute(BODY_HEADER_NAME);
		String functionCode = (String) bodyHeaderMap.get(FUNCTION_CODE_HEADER_TAG);
		String functionSubCode = (String) bodyHeaderMap.get(FUNCTION_SUB_CODE_HEADER_TAG);
		APIUsecaseMappingEntity entity = apiUsecaseMappingDAOService.findOneByApiNameAndFunctionCodeAndFunctionSubCode(apiName, functionCode, functionSubCode);
		if(entity != null){
			// ... checkPermissionByUsecase ...
		}
		chain.doFilter(wrappedRequest, response);
```
- Fix: Fail closed: if not in `ignoreFilterList` and no mapping entity → reject with clear error; or require wildcard default-deny mapping. Add CI check that every routed apiName+f+c has a row.  
- Effort: 1–2 days + data fix  
- Status: OPEN  
- Date found: 2026-04-10

### GAP-055: `/forward/*` endpoints bypass gateway security filters and log full forwarded payloads at INFO

- Service: trustt-platform-api-gateway  
- Lens: 10 (Auth bypass / trust boundary), 11 (Logging / PII)  
- Risk: High  
- File: `trustt-platform-api-gateway/src/main/java/in/novopay/apigateway/config/FilterConfig.java` (URL patterns); `.../requestforward/RequestForwardController.java`; `.../requestforward/RequestForwardProcessor.java`  
- Line/Method: filter `addUrlPatterns` vs `@RequestMapping("/forward")`; `RequestForwardProcessor#execute` / `forwardRequest`  
- Description: Registered filters target `/api/*`, `/api/novopay/*`, `/mfi/*`, document paths — **not** `/forward/*`. `RequestForwardController` accepts POST `/forward/json|xml/{tenantCode}/{requestName}` and forwards to URLs from config/cache with **no** session validation, client authentication, STAN dedupe, rate limit, or permission filter from the main gateway chain. `forwardRequest` logs **URL, all headers, and full request body** at INFO.  
- Failure scenario: Anyone who can reach the gateway host and guess `tenantCode` + `requestName` may trigger downstream HTTP calls subject only to `RequestForwardProcessor` header forwarding and target URL ACLs. Log stores receive full payloads.  
- Financial impact: Severe if `request_forward` table points to privileged internal URLs; compliance exposure from body logging.  
- Evidence:
```51:55:trustt-platform-api-gateway/src/main/java/in/novopay/apigateway/config/FilterConfig.java
    private static final String DMS_APIS ="/document/*";
    private static final String NOVOPAY_DMS_APIS ="/api/novopay/document/*";
    private static final String ALL_APIS = "/api/*";
    private static final String NOVOPAY_APIS = "/api/novopay/*";
    private static final String MFI_APIS = "/mfi/*";
```
```19:21:trustt-platform-api-gateway/src/main/java/in/novopay/apigateway/requestforward/RequestForwardController.java
@RestController
@RequestMapping("/forward")
public class RequestForwardController {
```
```68:71:trustt-platform-api-gateway/src/main/java/in/novopay/apigateway/requestforward/RequestForwardProcessor.java
	private HttpClientUtil.StringResponse forwardRequest(String url, HashMap<String, String> header, String requestBody) throws NovopayNonFatalException {
		log.info("request url for forward : {}", url);
		log.info("request headers : {}", header);
		log.info("request sent for forward : {}", StringUtils.isNotBlank(requestBody) ? requestBody.replaceAll("[\n\r\t]", "_") : "");
```
- Fix: Register `/forward/*` on the same filter chain **or** terminate forward at a dedicated internal ingress with mTLS + allowlist; redact logging; audit `request_forward` targets.  
- Effort: 2–5 days (network + code + data)  
- Status: OPEN  
- Date found: 2026-04-10

### GAP-056: Masterdata bulk code-master cache read errors return empty list (masquerades as “no data”)

- Service: trustt-platform-masterdata-management  
- Lens: 1 (Error handling), 11 (Observability)  
- Risk: Medium  
- File: `trustt-platform-masterdata-management/src/main/java/in/novopay/masterdata/codemaster/processor/GetBulkDatatypeMasterProcessor.java`  
- Line/Method: `getCachedData`  
- Description: On **any** exception from `cacheClient.get`, logs warn and returns `Collections.emptyList()` — caller may treat as valid empty masterdata instead of **degraded/failed** cache.  
- Failure scenario: Redis outage → UI/API sees empty dropdowns and validation passes/fails incorrectly.  
- Evidence:
```88:97:trustt-platform-masterdata-management/src/main/java/in/novopay/masterdata/codemaster/processor/GetBulkDatatypeMasterProcessor.java
	private List<CodeValue> getCachedData(String dataType, String datasubtype, String locale) {
		try {
			String cacheKey = dataType + "_" + datasubtype + "_" + locale;
			@SuppressWarnings("unchecked")
			List<CodeValue> cachedData = (List<CodeValue>) cacheClient.get(ThreadLocalContext.getTenant().getTenantCode(), cacheKey, RedisDBConfig.MASTER_DATA.getDbIndex());
			return cachedData;
		} catch (Exception e) {
			logger.warn("Error retrieving cached data for dataType: {}, datasubtype: {}, locale: {}", dataType, datasubtype, locale, e);
			return Collections.emptyList();
		}
	}
```
- Fix: Fall back to DB load on cache failure; or rethrow / return distinct error to caller; metrics on cache failures.  
- Effort: 1 day  
- Status: OPEN  
- Date found: 2026-04-10

### GAP-057: Audit ES consumer silently drops malformed JSON audit payloads

- Service: trustt-platform-audit  
- Lens: 2 (Data loss), 11 (Observability)  
- Risk: Medium  
- File: `trustt-platform-audit/src/main/java/in/novopay/audit/consumer/AuditMessageBrokerConsumer.java`  
- Line/Method: `parseData`  
- Description: `ParseException` → log error, return **empty** `JSONObject`; `computeRecords` then skips ES index for empty object — **no** DLQ, offset may commit → **lost audit event**.  
- Evidence:
```49:56:trustt-platform-audit/src/main/java/in/novopay/audit/consumer/AuditMessageBrokerConsumer.java
	private JSONObject parseData(String auditData) {
		try {
			return (JSONObject) parser.parse(auditData);
		} catch (ParseException e) {
			LOG.error("Error while parsing audit data", e);
		}
		return new JSONObject();
	}
```
- Fix: Push poison messages to DLQ or fail consumer; never treat parse failure as empty success.  
- Effort: 1–2 days  
- Status: OPEN  
- Date found: 2026-04-10

### GAP-058: Notifications response-code message cache uses `set` without explicit TTL

- Service: trustt-platform-notifications  
- Lens: 12 (Stale cache / ops), 3 (Consistency)  
- Risk: Medium  
- File: `trustt-platform-notifications/src/main/java/in/novopay/notifications/dao/NotificationDAOService.java`  
- Line/Method: `findNotificationMessageByResponseCodeAndLocale`  
- Description: After DB load, `cacheClient.set(tenant, cacheKey, message, NOTIFICATION db)` — **no TTL parameter** → relies on platform default expiry; template text updates in DB can remain **stale** until key eviction or manual clear.  
- Evidence:
```49:56:trustt-platform-notifications/src/main/java/in/novopay/notifications/dao/NotificationDAOService.java
	public String findNotificationMessageByResponseCodeAndLocale(String responseCode, String locale) throws NovopayFatalException {
		String cacheKey = responseCode + "_" + locale;
		String message = cacheClient.get(ThreadLocalContext.getTenantCode(), cacheKey, String.class, RedisDBConfig.NOTIFICATION.getDbIndex());
		if(StringUtils.isBlank(message)) {
			message = notificationMessageRepository.findNotificationMessageByResponseCodeAndLocale(responseCode, locale);
			cacheClient.set(ThreadLocalContext.getTenantCode(), cacheKey, message, RedisDBConfig.NOTIFICATION.getDbIndex());
		}
```
- Fix: TTL aligned to change cadence; invalidate on notification_message update path; or versioned keys.  
- Effort: 0.5–1 day  
- Status: OPEN  
- Date found: 2026-04-10

### GAP-059: No automated tests for API Gateway `AuthorizationCheckFilter`

- Service: trustt-platform-api-gateway  
- Lens: 11 (Observability / quality gates), 10 (Security — pairs GAP-054)  
- Risk: High  
- File: `trustt-platform-api-gateway/src/main/java/in/novopay/apigateway/filter/AuthorizationCheckFilter.java`  
- Line/Method: (filter `doFilter` / registration in `FilterConfig`)  
- Description: **GAP-054** documents runtime behaviour when `api_usecase_mapping` is missing (permission call skipped). There are **no** `src/test` references to `AuthorizationCheckFilter` workspace-wide → mapping-miss, ignore-list, and internal `checkPermissionByUsecase` integration paths can regress silently.  
- Evidence (test absence):
```text
grep -r "AuthorizationCheckFilter" --include="*.java" **/src/test → no matches (2026-04-10)
```
- Fix: Servlet/WebMvc or filter-unit tests with mocked `NovopayInternalAPIClient` / DAO; cases: mapping present, mapping absent, ignore list, FAIL response from auth service.  
- Effort: 1–2 days  
- Status: OPEN  
- Date found: 2026-04-10

### GAP-060: No automated tests for API Gateway request-forward path

- Service: trustt-platform-api-gateway  
- Lens: 10 (Security / data leakage — pairs GAP-055), 11 (Quality gates)  
- Risk: High  
- File: `trustt-platform-api-gateway/src/main/java/in/novopay/apigateway/requestforward/RequestForwardProcessor.java`, `RequestForwardController.java`  
- Line/Method: forward handling / controller entry  
- Description: **GAP-055** notes `/forward/*` bypasses normal gateway filters and logs forwarded payloads at INFO. No `RequestForward*` symbols appear under any service’s `src/test` → config resolution, error handling, and logging level changes are unguarded.  
- Evidence (test absence):
```text
grep -r "RequestForward" --include="*.java" **/src/test → no matches (2026-04-10)
```
- Fix: WebTestClient/integration tests per forward rule; assert filter chain, redaction, and failure modes.  
- Effort: 1–2 days  
- Status: OPEN  
- Date found: 2026-04-10

### RESOLVED-2026-04-13-A: Child NEFT duplicate ST_NEF re-trigger guard

- Service: `trustt-platform-accounting`
- Risk: High (duplicate bank trigger risk on child NEFT stage-1)
- Files: `DoGenericSyncSTPBankNeftCallBackProcessor.java`
- Resolution: In child failed callback handling, duplicate ST_NEF failures (`*0004`) no longer regress CLMT queue `disbursement_status` to `DTFC_SUCCESS`; it is preserved as `NEFT_STAGE_1_SUCCESS`, preventing repeated ST_NEF re-initiation by `childLoanEventProcessingBatchJob`. L1 extension also hardens ST_NEI duplicate-like failed callbacks with evidence-gated completion (queue/CRR) so stage-2 is not regressed without proven success.
- Status: RESOLVED
- Date resolved: 2026-04-13

### RESOLVED-2026-04-13-B: Payment reinitiation lane isolation in parent disbursement

- Service: `trustt-platform-accounting`
- Risk: High (reinit idempotency collision with normal disbursement lane)
- Files: `CallBankAPIForDisbursementProcessor.java`, `mfi_orc.xml`
- Resolution: Parent payment reinitiation now uses dedicated CRR transaction identifiers (`*_REINIT`) for MFT/NEFT paths, NEFT inquiry stage alignment for reinit lane, and prevents loan `disbursement_status` regression during reinit progression; `REINITIATE_BANK` path disables child bank calls (`do_child_bank_transactions=false`).
- Status: RESOLVED
- Date resolved: 2026-04-13

### RESOLVED-2026-04-15-C: Child NEFT retry skipped inquiry when CLMT stayed `DTFC_SUCCESS`

- Service: `trustt-platform-accounting`
- Risk: High (stuck child-lane progression on retry with repeated `PARENT_SUCCESS`)
- Files: `CallBankAPIForIndividualChildLoanDisbursementProcessor.java`
- Resolution: `performNEFTTransactionInquiry` now runs stage-1 inquiry (`ST_NEF`) when `disbursement_status=DTFC_SUCCESS` and prior child-scoped NEF CRR is non-success (`FAIL`/`UNKNOWN`/blank), instead of hard-skipping with `DO_TRANSACTION=false`. This preserves duplicate-NEF protection while enabling inquiry-led reconciliation for stuck child lanes.
- Status: RESOLVED
- Date resolved: 2026-04-15

## GAP-061: Child MFT post-processor CRR response can diverge from callback decision payload

Service: `trustt-platform-accounting` (+ `trustt-platform-lib` callback path)  
Lens: 5 (Contract/state integrity), 11 (Observability), 1 (Error-path correctness)  
Risk: 🔴 High  
File: `trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/disbursement/processor/PostMFTChildLoanBankDisbursementProcessor.java`  
Line: `logClientRequestResponse`  
Description: Historical gap where child MFT callback path could persist CRR `response` from `ExecutionContext.response` while deciding CRR `status` from callback `apiResponse`.  
Resolution: `PostMFTChildLoanBankDisbursementProcessor` now uses callback payload for both CRR decision and persisted body (`entity.setResponse(apiResponse != null ? apiResponse.toString() : NULL_BANK_API_RESPONSE_ENVELOPE)`) with null-safe request capture.  
Evidence (resolved state):
```98:105:trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/disbursement/processor/PostMFTChildLoanBankDisbursementProcessor.java
        Object requestPayload = executionContext.get(REQUEST);
        entity.setRequest(requestPayload != null ? requestPayload.toString() : "{}");
        entity.setResponse(apiResponse != null ? apiResponse.toString() : NULL_BANK_API_RESPONSE_ENVELOPE);
        entity.setBusinessDate(new Date(platformDateUtil.getValueDateInLong()));
        entity.setSystemDate(new Date());
        entity.setUpdatedOn(new Date());
        if (apiResponse != null && String.valueOf(apiResponse.get(RESPONSE_ERROR_CODE)).equalsIgnoreCase("0")) {
            entity.setStatus(SUCCESS);
```
Status: RESOLVED  
Date found: 2026-04-14  
Date resolved: 2026-04-14  
Resolved in branch: `mfi_integration_v3.2.8.4.1` (commit `1a789b6c7`)

## GAP-062: `loanWriteoff` posting branch — ExecutionContext keys do not match `PrepaymentApproppriationProcessor`

Service: `trustt-platform-accounting`  
Lens: 5 (Contract/state integrity), 1 (Money correctness), 7 (Idempotency / partial failure on wrong splits)  
Risk: High  

**Evidence**

- Orchestration (`loanWriteoff`, posting branch) passes **`prepayment_amount`** (local) = `${writeoff_amount}` into `prepaymentApproppriationProcessor`, not **`total_foreclosure_amount`**:  
  `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml` ~L1440-L1442.
- `ValidateLoanWriteOffDataProcessor` sets **`penalty_amount`**, not **`penal_amount`**:  
  `.../loan/writeoff/processor/ValidateLoanWriteOffDataProcessor.java` ~L92-L94.
- `PrepaymentApproppriationProcessor` reads **`total_foreclosure_amount`**, **`penal_amount`**, **`fee_amount`**, **`foreclosure_date`**:  
  `.../loan/prepayment/processor/PrepaymentApproppriationProcessor.java` ~L85-L90.
- Write-off request validates **`value_date`**, not **`foreclosure_date`** (`loans_orc.xml` validators ~L1384-L1398).

`DefaultExecutionContext.get` checks **local** then **shared** maps, so missing keys return **null** → `new BigDecimal(null)` / `Long.parseLong(null)` can fail at runtime; mis-keyed penalty/fee amounts change appropriation logic.

**What can go wrong**

- **Hard failure** on approve/post path (NPE / NumberFormatException) after maker-checker, or  
- **Silent wrong splits** if some keys resolve unexpectedly, producing incorrect `postTransaction` amounts and downstream dues/installment updates.

**Mitigation direction (tiered)**

- **L0:** In `loans_orc.xml`, add `IParam` mappings so `total_foreclosure_amount`, `penal_amount` (or change processor to read `penalty_amount`), `foreclosure_date` (from `value_date`), and `fee_amount` (`0` or computed) are set before `prepaymentApproppriationProcessor`.  
- **L1:** Align processor to accept the write-off contract (single source of key names) and add integration test for `loanWriteoff` REAL posting.  
- **L2:** Static validation: fail in CI if orchestration local keys for a processor bean don’t match processor reads (tooling).

**Status:** Open  
**Date found:** 2026-04-17  
**Runbook:** `.cursor/runbooks.md` → GAP-062

## GAP-063: `PopulateAndValidateAccountDetailsProcessor` — no null guard on `account_details`

Service: `trustt-platform-accounting`  
Lens: 1 (Fail-fast / error-path correctness), 5 (Contract robustness)  
Risk: Medium  

**Evidence:** `PopulateAndValidateAccountDetailsProcessor.java` L60-L61 — `JSONArray accountDetailsJSONArray = (JSONArray) executionContext.get("account_details");` then immediate `for` without null check.

**What can go wrong:** Unexpected client payload, tooling-generated internal call, or future orchestration change can surface as **NPE** instead of a controlled `NovopayFatalException`.

**Mitigation:** Null/blank check → fatal with explicit error code; align with orchestration mandatory validators for `postTransaction`.

**Status:** Open  
**Date found:** 2026-04-17  
**Wave:** Flow Sync Wave 2 (EC contract map)

## GAP-065: Accounting MessageBroker consumers — no explicit `maxPollRecords` for money-critical topics

Service: `trustt-platform-accounting`  
Lens: 11 (Observability / ops), 4 (Backpressure)  
Risk: **Medium**  
File: `trustt-platform-accounting/deploy/application/messagebroker/MessageBroker.xml`  
Line: L15-L28 (`bulk_collection_data_failed_`, `disburse_loan_api_` consumers)  
Description: Consumer blocks declare `pollTime` and `numberOfThreads` only — **no** `<maxPollRecords>` (unlike e.g. `trustt-platform-payments` `bulk_collection_data_` consumer in `event-registry.md`). Behaviour falls back to framework/Kafka defaults → lag handling not explicitly sized for financial throughput.  
Failure scenario: Broker lag grows under burst; tuning is implicit; incident playbooks lack in-repo declared poll batch size for these groups.  
Evidence:
```15:28:trustt-platform-accounting/deploy/application/messagebroker/MessageBroker.xml
	<Consumer>
		<consumersGroupIdPrefix>bulk_collection_failed_record_consumer</consumersGroupIdPrefix>
		<topicPrefix>bulk_collection_data_failed_</topicPrefix>
		<pollTime>100</pollTime>
		<numberOfThreads>1</numberOfThreads>
		<bean>bulkCollectionFailedRecordConsumer</bean>
	</Consumer>
	 <Consumer>
		<consumersGroupIdPrefix>disburse_loan_api_consumer_</consumersGroupIdPrefix>
		<topicPrefix>disburse_loan_api_</topicPrefix>
		<pollTime>100</pollTime>
		<numberOfThreads>1</numberOfThreads>
		<bean>lmsMessageBrokerConsumer</bean>
	</Consumer>
```
Fix: Set explicit `maxPollRecords` (and document lag alerts per tenant topic) aligned with orchestration latency; mirror payments’ explicit pattern where appropriate.  
Status: OPEN  
Date found: 2026-04-17

## GAP-066: Disburse sync Kafka message lacks correlation IDs (`stan` / trace)

Service: `trustt-platform-accounting`  
Lens: 11 (Observability), 8 (Cross-service trace)  
Risk: **Medium** (resolved)  
File: `trustt-platform-accounting/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java`  
Line: `sendResultMessageToKafka` L271-L278; processing log L131; success/fail publish logs L297-L308  
Description (historical): Result payload omitted `stan` though LOS sends it in disburse headers via `DisburseLoanAPIUtil.getHeaders`.  
Resolution (2026-04-17): `stan` and `entity_type` are copied from `ExecutionContext` into the `los_lms_disbursement_sync` JSON when non-blank; consumer logs include tenant, `external_ref_number`, `stan`, `entity_type`, topic/partition/offset. Trace-id propagation (if distinct from `stan`) remains optional/future.  
Evidence:
```271:278:trustt-platform-accounting/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java
            String stan = stringFromExecutionContext(executionContext, JSON_KEY_STAN);
            if (StringUtils.isNotBlank(stan)) {
                payload.put(JSON_KEY_STAN, stan);
            }
            String entityType = stringFromExecutionContext(executionContext, JSON_KEY_ENTITY_TYPE);
            if (StringUtils.isNotBlank(entityType)) {
                payload.put(JSON_KEY_ENTITY_TYPE, entityType);
            }
```
Status: **RESOLVED** (2026-04-17)  
Date found: 2026-04-17

## GAP-067: LOS → Accounting disburse Kafka message — implicit pipe-delimited contract / deploy order

Service: `trustt-platform-los` + `trustt-platform-accounting`  
Lens: 5 (Contract), 12 (Deploy order)  
Risk: **Medium**  
File: `trustt-platform-los/.../DisburseLoanAPIUtil.java` L66-L69; `trustt-platform-accounting/.../LmsMessageBrokerConsumer.java` L160-L162  
Description: Producer builds `apiName + "|" + request + "|" + cacheKey`; consumer splits with `indexOf("|")` / `lastIndexOf("|")`. Any change to delimiter ordering or cacheKey format on one side only → malformed parse or wrong `externRefNumber`.  
Failure scenario: Partial deploy or hotfix on one service breaks async disburse consumption silently.  
Evidence:
```66:69:trustt-platform-los/src/main/java/in/novopay/los/util/DisburseLoanAPIUtil.java
            String request = jsonHelper.formatAPIRequestAsJSONString(apiName, requestMap);
            cacheKey = buildCacheKey(apiName, executionContext);
            request = apiName+"|" + request +"|"+cacheKey;
```
```160:162:trustt-platform-accounting/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java
        String api = data.substring(0, data.indexOf("|"));
        String requestBody = data.substring(data.indexOf("|") + 1, data.lastIndexOf("|"));
```
Fix: Versioned envelope (JSON wrapper) or shared constant + contract test in both repos; deploy checklist: ship both sides together.  
Status: OPEN  
Date found: 2026-04-17

## GAP-068: `collectionLoanRepayment` retry loop — nested `loanRepayment` idempotency reliance

Service: `trustt-platform-payments` (+ accounting `loanRepayment`)  
Lens: 3 (Retry + idempotency), 6 (Transaction boundaries)  
Risk: **Medium**  
File: `trustt-platform-payments/.../MfiCollectionsDAOService.java` L1038-L1084; `.../CollectionRepaymentProcessor.java` L68-L74  
Description: Outer method retries `callInternalAPI(..., "collectionLoanRepayment", ...)` on non-SUCCESS; processor calls accounting `loanRepayment` with `client_reference_number` set from `receipt_number`. Double-post is **usually** prevented by accounting dedupe — not proven here for all edge modes (multi-item loop, SHG `group_receipt_number` L110-L114).  
Failure scenario: Timeout / ambiguous response after accounting committed → retry duplicates allocation if dedupe fails.  
Evidence:
```1038:1042:trustt-platform-payments/src/main/java/in/novopay/payments/collections/mfi/repository/MfiCollectionsDAOService.java
        for (int attempt = 0; attempt < maxRetries; attempt++) {
            try {
                executionContext.putLocal(FUNCTION_CODE, DEFAULT);
                executionContext.putLocal(FUNCTION_SUB_CODE, DEFAULT);
                novopayInternalAPIClient.callInternalAPI(executionContext, "collectionLoanRepayment", "v1", "collectionLoanRepayment_response", -1, -1, false);
```
```68:74:trustt-platform-payments/src/main/java/in/novopay/payments/recurringinterface/CollectionRepaymentProcessor.java
			executionContext.put("client_reference_number", receiptNumber);
			executionContext.put("receipt_number", receiptNumber);
			novopayInternalAPIClient.callInternalAPI(executionContext, LOAN_REPAYMENT,
					"v1", "accounting_" + LOAN_REPAYMENT, -1, -1, false);
```
Fix: Document idempotency contract; integration test retry-after-success; optional idempotency-key header across internal API.  
Status: OPEN  
Date found: 2026-04-17

## GAP-069: Critical money paths — partial observability vs six-point completeness target

Service: platform (see `.cursor/knowledge-graph.md` § Critical money paths)  
Lens: 11 (Observability)  
Risk: **Medium**  
Description: For each money path, ideal = (1) structured entry log + correlation, (2) structured exit + result, (3) durable DB record, (4) completion event, (5) explicit failure recording, (6) monitoring/alert hook. **Wave 6 check:**

| Path | (1) Entry+corr | (2) Exit | (3) DB | (4) Event | (5) Error path | (6) Monitor |
|------|----------------|----------|--------|-----------|----------------|-------------|
| Disbursement | **Improved** (ACC: `stan` / `entity_type` in sync payload + structured logs; GAP-066 resolved) | PARTIAL | Y | Y (sync topic) | Y | PARTIAL |
| Repayment | PARTIAL | PARTIAL | Y | Varies | PARTIAL | PARTIAL |
| Interest accrual | PARTIAL (batch) | PARTIAL | Y | N universal | PARTIAL | PARTIAL |
| Loan closure | PARTIAL | PARTIAL | Y | Y (data sync) | **GAP** auto-closure writer | PARTIAL |
| Bulk collection | PARTIAL | PARTIAL | Y | Y | GAP-064/019 | PARTIAL |
| Reversal / manual JE | PARTIAL | PARTIAL | Y | Varies | PARTIAL | PARTIAL |

Evidence: Representative logs/processors cited in `knowledge-graph.md`, `LmsMessageBrokerConsumer.java`, `gaps-and-risks.md` (auto-closure, Kafka swallow).  
Fix: Standard observability kit per path (correlation, metrics, DLQ/lag alerts); GAP-066 closed 2026-04-17; remaining: producer swallow (**GAP-019**), universal trace-id, metrics hooks.  
Status: OPEN (matrix target; disburse sync correlation slice improved)  
Date found: 2026-04-17

## GAP-070: Foreclosure / disbursement-cancellation task-creation pre-step swallowed exceptions → orphan rows with `task_id IS NULL` (CLOSED)

Severity (was): **High**  
Lens: 1 (Exception swallowing), 5 (Contract/state drift), 6 (Ordering vs side effects), 11 (Observability gaps)  
Path: `trustt-platform-accounting/src/main/java/in/novopay/accounting/common/processor/CreateTaskWorkFlowHelpingProcessor.java`  
Description: `getDataForNotification(...)` caught `Exception`, logged it, and returned `true`; the three callers (`getCustomerDetails`, `getUserDetails`, `getBankEmployeeDetails`) issued bare `return;` on that signal. When any helper API failed, the processor exited cleanly without throwing and without ever calling `createTaskWorkflow`. Downstream `update*TaskDetailsProcessor` then read `task_id = null` and silently committed the prepayment / cancellation row with `task_id IS NULL`. SOF transaction committed (no exception → no rollback), and `loan_status` was already flipped to `FORECLOSURE_FREEZE` / `DISB_CNCL_FREEZE` *before* the task processor in the orchestration chain — leaving orphan rows + stuck loans + no task in the task service.  
Failure scenario observed: production incident on `mfi_integration_v3.2.8.4` — `loanPrepayment` and `loanDisbursementCancellation` initiations from front-end produced rows in `loan_account_part_prepayment_details` / `loan_disbursement_cancellation_details` with NULL `task_id`, loan in `*_FREEZE`, no task to act on; users blocked from progressing.  
Fix: Commit `154b500c0` on `mfi_integration_v3.2.8.4` (PR pending) — `getDataForNotification` now throws `NovopayFatalException("13012", "Task creation pre-step failed: <apiName> — <root-cause>")` with the apiName + underlying message in the `defaultMessage` so app logs carry the WHY without a new notification mapping. Orchestration `<Processor>`s in `loanPrepayment` and `loanDisbursementCancellation` re-ordered so `updateLoanAccountStatusProcessor` / `updateLoanStatusForSHGProcessor` / `updateChildLoanAccountStatusProcessor` run **after** `createTaskWorkFlowHelpingProcessor` — defence in depth. Forward-port to `3.2.8.4.1`, `3.2.8.5`, `3.3.1.0`, `3.3.1.0.0` is a separate task (not yet done).  
Status: **CLOSED on `mfi_integration_v3.2.8.4`** (commit `154b500c0`) — open on later branches until cherry-picked.  
Existing orphan-row data patch for prod: [`runbooks/task-id-orphan-data-patch.md`](runbooks/task-id-orphan-data-patch.md).  
Detail: 2026-05-04 entry in [`changelog/CHANGELOG.md`](changelog/CHANGELOG.md) (`git show 154b500c0`).  
Date closed: 2026-05-04

## GAP-071: TOCTOU race in cursor's "distributed" Redis in-flight gate for child disbursement legs (CLOSED)

Severity (was): **High**  
Lens: 4 (Retry & circuit breaker), 5 (Contract/state drift), 6 (Ordering vs side effects), 12 (Concurrency)  
Path: `trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/disbursement/processor/CallBankAPIForIndividualChildLoanDisbursementProcessor.java`  
Description: Cursor commit `ea5dba734` migrated the child bank-leg in-flight gate from a JVM-local `ConcurrentHashMap.newKeySet()` to a Redis-backed key, but the implementation was a get-then-set sequence: `if (cache.get(key) != null) return false; cache.set(key, "true", TTL); return true;`. `NovopayCacheClient.set()` is unconditional overwrite (no SETNX semantics), so two pods can both observe an absent key, both write, and both believe they acquired — defeating the cross-pod dedup intent and allowing duplicate child bank-leg execution.  
Fix: Commit `4cb437b28` (`trustt-platform-lib`) adds `setIfAbsent(tenantCode, key, value, ttl, dbIndex)` to `ICacheClient`/`NovopayCacheClient`/`RedisCacheClient` mapped to `RedisTemplate.opsForValue().setIfAbsent(...)` (atomic `SET … PX … NX` on the wire, single round-trip). Commit `ede4aa325` (`trustt-platform-accounting`) replaces the get-then-set with the atomic call. Adds zero per-pod heap state.  
Status: **CLOSED on `mfi_integration_v3.2.8.4.1`** (commits `4cb437b28` + `ede4aa325`).  
Date closed: 2026-05-04

## GAP-072: Child NEFT v2 stage-1 evidence guard too strict — async-callback successes permanently blocked from stage-2 (CLOSED)

Severity (was): **High** (active production blocker — qa3 parent `6009682425` had 5 of 10 children stuck mid-flight)  
Lens: 5 (Contract/state drift), 6 (Ordering vs side effects), 11 (Observability gaps)  
Path: `trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/disbursement/bank/child/ChildDisbursementNeftV2BankCall.java`  
Description: Cursor commit `a7328c3f5` introduced `hasSuccessfulChildNeftStage1` — a guard that blocks stage-2 NEI initiation unless a SUCCESS NEFT_NEF outgoing CRR exists. Intent: idempotency under replay/inquiry. Real-world failure mode: synchronous outgoing NEFT call returns an empty response body (logged as CRR `status=FAIL` with `response="{}"`) but the bank actually processes the payment and sends an async SUCCESS callback that flips the queue row's `disbursement_status` to `NEFT_STAGE_1_SUCCESS` via `processLoanAccountForChildLoans`. Under the strict guard those children were permanently blocked from stage-2 NEI — qa3 evidence: parent `6009682425` (2026-05-04) has 5 children at `NEFT_STAGE_1_SUCCESS` with `external_error_code=MFI-40001`, `external_error_message="Waiting to initiate ST NEI - NEFT STAGE 2"`, no SUCCESS NEFT_NEF CRR ever, only FAIL NEF CRRs with empty `{}` response body.  
Fix: Commit `ede4aa325` broadens evidence acceptance to three signals (in order of strength): (1) SUCCESS outgoing NEFT_NEF CRR (original); (2) SUCCESS `NEFT_TRANSACTION_INQUIRY` CRR (bank-attested via the explicit inquiry path); (3) queue row `disbursement_status` ∈ `{NEFT_STAGE_1_SUCCESS, NEFT_STAGE_2_PENDING}` (set only by the async callback handler on `errorCode=0` + `TXTSTATUS=PROCESSED`, so itself an authoritative attestation). The downstream `shouldSkipChildNeftStage2Initiation` guard (SUCCESS NEFT_NEI CRR check) and the inquiry-only nature of NEI mean this loosening cannot cause double money movement.  
Status: **CLOSED on `mfi_integration_v3.2.8.4.1`** (commit `ede4aa325`).  
Existing-data remediation: open — for QA3 parent `6009682425` (5-of-10 stuck children), the recovery is a manual UPDATE on `loan_account_events_queue` to drive the affected rows from `NEFT_STAGE_1_SUCCESS` through stage-2; coordinate with QA before running. Code-fix detail in `git show ede4aa325`.  
Date closed: 2026-05-04

## Synced from .cursor (2026-07-10)

| **GAP-074 — SDCP-10199 last-child parent INT/DPI under-settlement (INT-180)** | **High** (open; parked) | Released trains / `mfi_integration_v3.7.1@f45dbe3bd` still use child `INT_AMT` in `doParentPartPrePayment`; fix parked on `fix/sdcp-10199-parent-int-dpi-last-child-dfc` @ `61278d5f8` — **do not merge/push to 3.7.1 until QA/prod discuss**; SoT narrative `.cursor/gaps-and-risks.md` GAP-074; runbook `sdcp-10199-group-parent-last-child-dfc.md`; ASK-057 **DEFERRED** | Parent can CLOSE after last-child DFC with residual pending INT (latent 3.4.2.1+); DPI residual risk on 3.7.1. Missed via lucky INT=0 e2e / UI-focused QA. |
| **RESOLVED (2026-07-15) — GAP-075 A2 EXTRA-net + B force-bill labd** | **Resolved** | SoT `.cursor/gaps-and-risks.md` GAP-075; acct `5b1b928ed`; e2e `dcf.group_parent_last_child_e2e`; runbook `sdcp-10199-group-parent-last-child-dfc.md` | Parent statement full POS vs EXTRA-net; force-bill without labd txn_ref. |
