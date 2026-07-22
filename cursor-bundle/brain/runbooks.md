# Runbooks — High severity gaps (this codebase)

Cross-reference: `.cursor/gaps-and-risks.md`. **Related diagrams:** `.cursor/architecture.mmd`, `.cursor/accounting-flow.mmd`.

---

## LOS disbursement sync no-ops if `entity_type` missing

- **What breaks:** LOS consumes `los_lms_disbursement_sync` but `DisbursementSyncService` exits early when `entity_type` absent — DB fields like failure/sync reason may **not** update even though accounting published SUCCESS/FAILED. **Files:** `novopay-mfi-los/src/main/java/in/novopay/los/service/disbursement/DisbursementSyncService.java` (L33-L37 per gaps table).
- **Early warning signs:** Kafka message on `los_lms_disbursement_sync` with status FAILED but LOS UI still “in progress”; `LOG` at WARN/INFO showing guard return; mismatch between accounting `loan_account.disbursement_status` and LOS disbursement record.
- **Immediate mitigation (2am):** (1) Identify `external_ref_number` + tenant from Kafka payload or accounting DB. (2) Manually patch LOS disbursement row / retry sync from ops tool if available. (3) If stuck mid-flight, verify accounting side truth first (`loan_account`, CRR) before forcing LOS state. (4) Short-term: ensure producer payload includes required keys (coordinate hotfix branch).
- **Permanent fix:** Add contract tests LOS↔accounting JSON samples; **either** default `entity_type` safely **or** make LOS path tolerant when key missing but status present; align with `LmsMessageBrokerConsumer.sendResultMessageToKafka` keys. **Effort:** ~2–3 days including QA + regression on multi-product LOS.
- **Files to check:** `DisbursementSyncService.java`, `DisbursementSyncConsumer.java`, `LmsMessageBrokerConsumer.java`, `system_brain/edge_cases/disbursement_sync_entity_type_missing.md`.
- **Related flows:** Disbursement, async disburse (`disburse_loan_api_` → `disburseLoan`).
- **Risk if unresolved:** Origination teams see false “not disbursed” states, duplicate manual fixes, SLA breaches on funding.

---

## Accounting → LOS sync payload does not include `entity_type`

- **What breaks:** Accounting builds JSON without `entity_type` while LOS requires it for certain update branches — **silent skip** on LOS side. **Files:** `novopay-platform-accounting-v2/.../LmsMessageBrokerConsumer.java` payload assembly (L191-L207).
- **Early warning signs:** Structured log “Successfully sent … FAILED/SUCCESS” from accounting without corresponding LOS row change; repeated consumer retries on LOS with no DB diff.
- **Immediate mitigation:** Deploy hotfix adding `entity_type` to `JSONObject payload` (value from product/loan type in `ExecutionContext` or loan snapshot); replay dead-letter / republish for affected `external_ref_number` after verification.
- **Permanent fix:** Version the sync contract (additive fields), update `event-registry.md` payload column, add consumer-side defensive defaults **and** producer-side mandatory population. **Effort:** ~1–2 days engineering + 1 day cross-module QA.
- **Files to check:** `LmsMessageBrokerConsumer.java`, `AccountingKafkaProducer.java`, LOS `DisbursementSyncConsumer.java`.
- **Related flows:** Async disburse completion path; LOS mirror of LMS status.
- **Risk if unresolved:** Permanent divergence between LMS and LOS — audit and customer servicing break.

---

## Disbursement Redis in-flight key has no TTL (LOS producer)

- **What breaks:** Crash between `set` and `remove` in LOS `DisburseLoanAPIUtil` leaves key forever; later disburse attempts **never** fire. **Files:** `novopay-mfi-los/.../DisburseLoanAPIUtil.java` (L72-L83).
- **Early warning signs:** “Stuck” disburse with no new Kafka message; Redis key present with no TTL; logs showing skip due to in-flight.
- **Immediate mitigation:** Ops deletes offending Redis keys for tenant/db index after confirming no live in-flight JVM; **coordinate** with accounting duplicate-safe checks. Scale: use `SCAN` + pattern for `disburseLoan*` keys — document in ops playbook only with approval.
- **Permanent fix:** Add TTL (slightly > max orchestration SLA), heartbeat refresh, or fencing token; align with accounting consumer key semantics. **Effort:** ~2 days + chaos test.
- **Files to check:** `DisburseLoanAPIUtil.java`, LOS Redis config, `LmsMessageBrokerConsumer` cleanup paths.
- **Related flows:** LOS-triggered async disburse.
- **Risk if unresolved:** Hard stop for new bookings until manual Redis surgery.

---

## Disbursement Redis in-flight key has no TTL (Accounting consumer)

- **What breaks:** `LmsMessageBrokerConsumer` sets `dl`+original cache keys via `NovopayCacheClient` without TTL; crash mid-`executeServiceOrchestration` can strand keys → perpetual skip at `getDisburseSkipReason`. **Files:** `LmsMessageBrokerConsumer` L108-L122, L148-L151.
- **Early warning signs:** WARN “Request is already in processing”; loan not progressing; keys in Redis accounting DB index without TTL.
- **Immediate mitigation:** Delete stale `dl*` / original keys for known-good completed/failed loans after DB confirms terminal state; re-drive message from LOS if safe.
- **Permanent fix:** TTL + idempotent completion marker in DB as source of truth; unify with LOS producer TTL strategy. **Effort:** ~2 days.
- **Files to check:** `LmsMessageBrokerConsumer.java`, `NovopayCacheClient`, Redis `RedisDBConfig.ACCOUNTING`.
- **Related flows:** Kafka `disburse_loan_api_` consumer.
- **Risk if unresolved:** Async disburse pipeline wedged for specific external refs.

---

## Broad Redis `flushDb()` helper exists

- **What breaks:** Any mistaken call to `RedisCacheClient.flushDb()` wipes **entire** DB index for tenant scope — cache + locks + dedupe gone. **Files:** `novopay-platform-lib/infra-cache/.../RedisCacheClient.java` L109-L118.
- **Early warning signs:** Mass STAN dedupe failures, lock storms, empty gateway session cache, sudden disburse replays.
- **Immediate mitigation:** Freeze deploys touching cache utilities; restore Redis from backup if available; rebuild cold-cache via controlled warm-up; **disable** offending code path via feature flag if present.
- **Permanent fix:** Remove `flushDb` from production code paths or gate behind break-glass IAM + metric; replace with namespaced delete-by-prefix with limits. **Effort:** ~1–2 days hardening + org-wide grep cleanup.
- **Files to check:** All `flushDb(` call sites repo-wide; `RedisCacheClient.java`.
- **Related flows:** Any Redis-backed idempotency (disburse, gateway STAN, collections).
- **Risk if unresolved:** Platform-wide incident potential — multi-tenant data loss in Redis layer.

---

## Interest accrual posting uses time-based `client_reference_number`

- **What breaks:** Batch `InterestAccrualBookingBatchService` derives client ref from time — replay after partial commit can **generate new CREF** → `ClientReferenceNumberDedupProcessor` may **not** dedupe → double GL posting. **Files:** `.../InterestAccrualBookingBatchService.java` L251-L259.
- **Early warning signs:** Duplicate `transaction_master` rows same loan/date; accrual amount 2×; reconciliation mismatch EOD.
- **Immediate mitigation:** Stop accrual job for affected run window; mark bad postings for reversal using `reverseTransaction` runbook (manual); fix data boundaries before restart.
- **Permanent fix:** Deterministic CREF from `(loanAccountId, valueDate, txnType, runId)`; store job checkpoint; idempotent batch item keys. **Effort:** ~3–5 days incl. regression on large portfolios.
- **Files to check:** `InterestAccrualBookingBatchService.java`, `ClientReferenceNumberDedupProcessor`, accrual ORC entry.
- **Related flows:** EOD interest accrual posting (`postTransaction` INTEREST/*).
- **Risk if unresolved:** Silent balance inflation; regulatory/audit exposure.

---

## Proactive excess refund writer swallows exceptions

- **What breaks:** `ProactiveExcessAmountRefundItemWriter` catches and **does not rethrow** — chunk can “complete” while rows stay wrong; reruns duplicate risk. **Files:** `.../ProactiveExcessAmountRefundItemWriter.java` L156-L158.
- **Early warning signs:** Batch “SUCCESS” with unchanged staging counts; partial refunds; logs without stack traces at ERROR for failed items.
- **Immediate mitigation:** Pause proactive refund job; inspect staging table; re-run after code fix or manual item replay with CREF audit.
- **Permanent fix:** Fail chunk on business error; DLQ topic; metrics per skip; align with Spring Batch listener policies. **Effort:** ~2 days + batch QA.
- **Files to check:** `ProactiveExcessAmountRefundItemWriter.java`, job XML, staging repositories.
- **Related flows:** Excess refund / proactive batch (`prepayment_foreclosure_writeoff_refund_rebooking_posting.md`).
- **Risk if unresolved:** Customer money movement wrong or delayed; silent operational debt.

---

## Gradle Novopay plugin classpath vs published dependency-mgmt version mismatch

- **What breaks:** Services pin `*.gradle.plugin:3.2.6.6-1` while `novopay-platform-dependency-mgmt` publishes `3.2.6.6.2-1` for the same logical artifact family — developers assume patch X while CI/release may resolve Y → **unexpected transitive `novopay-platform-lib` revisions**. **Files:** `novopay-platform-accounting-v2/build.gradle` L14; `novopay-platform-dependency-mgmt/build.gradle` (multiple `version = "3.2.6.6.2-1"`).
- **Early warning signs:** “Works locally” after partial publish; NoSuchMethodError at runtime across services; differing bytecode for same class between accounting and LOS.
- **Immediate mitigation:** Freeze promotions; diff resolved dependency trees (`./gradlew :novopay-platform-accounting-v2:dependencies`) between good/bad build; align all service `buildscript` lines to **one** approved plugin version from dependency-mgmt.
- **Permanent fix:** Single BOM source — services **do not** hardcode classpath versions; use `plugins { id ... version from catalog }`. **Effort:** ~3–5 days platform engineering.
- **Files to check:** Every service `build.gradle` buildscript block; `novopay-platform-dependency-mgmt/build.gradle`.
- **Related flows:** All JVM services.
- **Risk if unresolved:** Cross-service runtime incompatibility; incident during release windows.

---

## (Test absence) No automated test for `LmsMessageBrokerConsumer` async disburse path

- **What breaks:** **CI never exercises** Redis skip logic, `sendResultMessageToKafka` failure path, or `executeServiceOrchestration` wiring for Kafka disburse; regressions ship unnoticed until prod. **Evidence:** no `LmsMessageBrokerConsumer` symbol in `**/src/test/**/*.java` (scan 2026-04-07).
- **Early warning signs:** Production-only failures after innocuous refactor to consumer; Sonar coverage gap on consumer package.
- **Immediate mitigation:** Manual replay using `scripts/disburse_loan_sanity.py` (per workspace rule) on candidate build; block release until at least one integration test passes.
- **Permanent fix:** Spring Boot test with embedded Kafka or Testcontainers + Redis mock; golden-message fixtures. **Effort:** ~3–5 days.
- **Files to check:** `LmsMessageBrokerConsumer.java`, `MessageBroker.xml`, `test-coverage-map.md`.
- **Related flows:** Async disburse.
- **Risk if unresolved:** High rate of Sev-1 disburse incidents.

---

## (Test absence) No automated test for `glBalanceZeroisation` / `reverseTransaction` / `postManualJournalEntry`

- **What breaks:** Year-end GL and finance correction paths **unchanged in safety net** — double-post or missed zeroisation hits finance close. **Evidence:** grep of those strings in `**/src/test/**/*.java` → no hits (2026-04-07).
- **Early warning signs:** Finance team catches TB mismatch first; only manual UAT once/year.
- **Immediate mitigation:** Manual JE reversal playbook; freeze GL job config changes; parallel run on subset accounts in UAT.
- **Permanent fix:** Add focused ORC integration tests with H2/YB fixture DB; assert `transaction_master` counts. **Effort:** ~5 days.
- **Files to check:** `product_transaction_orc.xml`, `system_brain/flows/gl_balance_zeroisation_posting.md`, `reversals_manual_journal_transaction_engine.md`.
- **Related flows:** GL zeroisation, reversals, manual JE.
- **Risk if unresolved:** Material misstatement / failed statutory close.

---

## (Test absence) No automated test for DCF / insurance inbound batch posting

- **What breaks:** Insurance file → DCF posting path untested in CI; death foreclosure amounts wrong. **Evidence:** no `DeathForeclosure` / inbound insurance writer tests in `src/test` (grep 2026-04-07).
- **2026-05-07 update — SDCP-9301 fix on `sdcp-9301-hotfix-3.2.8.4`:** sync-runs `loanAccountBillingJob` before claim/posting; new `BILLED_PRIN_AMT` placeholder splits POS into billed-and-unpaid vs truly-unbilled; old BPI hack (hijacking the next INT due row) replaced by absorbing gap-accrual into the existing INT row. Out-of-code: product ops must add `24511 → 13335` legs keyed on `BILLED_PRIN_AMT` / `ADV_BILLED_PRIN_AMT` for `DEATH_FORECLOSURE` and `RSCH_DEATH_FORECLOSURE`. Post-deathDate partial-cycle billing entry (DPI) deferred — out of scope.
- **Early warning signs:** Staging row counts mismatch; claim payment disputes months later.
- **Immediate mitigation:** Stop bulk insurance jobs; reconcile staging vs posted txn; manual reversal where applicable.
- **Permanent fix:** Writer-level tests with fixtures from anonymized production samples; batch step scope tests. **Effort:** ~1 week.
- **Files to check:** `system_brain/flows/insurance_inbound_posting.md`, writers under `batchnew` insurance packages.
- **Related flows:** Insurance inbound / DCF.
- **Risk if unresolved:** Wrong insurance settlement and customer harm.

---

*Medium-severity code gaps retain narratives only in `gaps-and-risks.md` until promoted.*

---

## NEFT v2 JLG local suite runbook (callback-driven, deterministic)

- **When to use:** Local/QA sanity where `disburseLoan` reaches `NEFT_STAGE_1_PENDING` / `NEFT_STAGE_2_PENDING` and does not auto-progress without callback ingress.
- **Flow invariant (validated):** `NEF call -> NEF callback -> NEFT_STAGE_1_SUCCESS -> NEI call -> NEI callback -> COMPLETED`. Inquiry may run between legs; callbacks are still authoritative for stage advancement.
- **`mfi` orchestration replay (critical):** After NEF callback, a `disburseLoan` replay that should initiate ST_NEI must use `function_sub_code=NEFT_STAGE_1_SUCCESS` (with `account_number` populated). `function_sub_code=DEFAULT` is the full create-book path and does not select the mid-stage `do_bank_transactions` flags in `mfi_orc.xml`, so NEI never runs and `doGenericSyncSTPBankNEINeftCallBack` stays a no-op while status is still `NEFT_STAGE_1_SUCCESS`.
- **`disburseLoan` is async for `mfi`:** HTTP returns immediately; poll `loan_account` until `NEFT_STAGE_2_PENDING` before sending the NEI callback.
- **Do not rely on implicit progression:** For NEFT v2, stage movement in accounting is finalized by `doGenericSyncSTPBankNEFNeftCallBack` and `doGenericSyncSTPBankNEINeftCallBack` (`DoGenericSyncSTPBankNeftCallBackProcessor`).

### Simulator seeding contract (must match request parser)

- Seed `mfi_simulator.simulator_response` with exact leg payloads:
  - `doGenericSyncSTPNEF`: success (`replyCode=0`, `errorCode=0`)
  - `doGenericSyncSTPInquiry`: include `faxml.paymentlist.payment` (not header-only)
  - `doGenericSyncSTPNEI`: success (`replyCode=0`, `errorCode=0`)
- Keep **non-blank validation tokens**, else Chameleon returns `400` and accounting records `{}`/FAIL:
  - `doGenericSyncSTPNEF` -> validation contains `ST_NEF`
  - `doGenericSyncSTPInquiry` -> validation contains `GenericSyncSTPInquiryRequestDTO`
  - `doGenericSyncSTPNEI` -> validation contains `ST_NEI`
- **L1 standard gate (mandatory before suite):**
  - Run `bash scripts/neft_v2_local_prepare.sh`
  - This does both:
    1. seed (`scripts/mfi_simulator_neft_v2_seed.sql`)
    2. probe all 3 endpoints with realistic payloads
  - If probe fails, do not run disbursement suite; fix simulator health first.

### Callback payload shape (mandatory gateway envelope)

- Use callback body with top-level wrapper:
  - `headers.tenant_code`
  - `request.<payload>`
- NEF callback (`/api/v1/doGenericSyncSTPBankNEFNeftCallBack`) requires:
  - `request.faxml.header.txtstatus=PROCESSED`
  - `request.faxml.paymentlist.payment.paymentrefno` (must match NEF CRR `client_reference_number`)
  - `errorcode=0` for success stage movement
- NEI callback (`/api/v1/doGenericSyncSTPBankNEINeftCallBack`) requires:
  - `request.faml.inqlist.payment.paymentrefno` (same NEF/NEI client ref family)
  - `codstatus=P` to mark completion

### Minimal DB evidence checklist (pass criteria)

- `loan_account.disbursement_status` transitions:
  - `NEFT_STAGE_1_PENDING` -> `NEFT_STAGE_1_SUCCESS` -> `NEFT_STAGE_2_PENDING` -> `COMPLETED`
- `client_request_response_log` shows expected lane rows for the LAN:
  - `DISBURSEMENT_NEFT_NEF`
  - `NEFT_TRANSACTION_INQUIRY` (optional in some retries, expected in inquiry-led branch)
  - `DISBURSEMENT_NEFT_NEI`
- If stage is stuck at pending, check in this order:
  1. callback endpoint response code/body (`13007` indicates malformed wrapper/headers)
  2. callback body key path (`paymentlist` for ST_NEF, `inqlist` for ST_NEI)
  3. simulator `validation` values and returned HTTP status for NEFT APIs

### Known high-friction failure signatures

- `Cannot invoke ... because "paymentlist" is null` during inquiry:
  - Inquiry response shape or mapping mismatch; verify seeded inquiry includes `faxml.paymentlist.payment`.
- NEF/NEI CRR row `status=FAIL` with `response={}`:
  - Simulator mismatch/400 or callback not yet delivered; verify simulator validation + callback invocation.
- Callback API returns `code=13007`:
  - Missing `headers.tenant_code` or incorrect request envelope (`request.*` absent).

### 2026-04-29 full-suite status coverage (local replay runbook)

- Use this exact command pattern per product payload:
  - `python3 scripts/disburse_loan_sanity.py --request-file <payload.json> --neft-version v2 --stage-suite full --simulator-profile success --report-json /tmp/<name>_v2_full_report.json`
- Verified payload set (canonical):
  - `scripts/disbursement/payloads/canonical/disburse_loan_sanity_request_4495972134234554346565.json` (JLG flat)
  - `scripts/disbursement/payloads/canonical/disburse_loan_sanity_request_370164.json` (INDL flat)
  - `scripts/disbursement/payloads/canonical/disburse_loan_sanity_request_shg_41333333.json` (SHG `member_details[]`)
- Quick wrappers: `scripts/bin/disburse-quick.sh` (JLG), `disburse-indl-quick.sh` (INDL), `disburse-shg-quick.sh` (SHG); `make -C scripts jlg|indl|shg|lock-clean`
- Status expectations validated by suite:
  - JLG (MFT/ACCTWB): terminal COMPLETED / DTFC_SUCCESS
  - INDL (NEFT v1): local minimal often `NEFT_STAGE_1_PENDING` after NEF SUCCESS (WARN PASS until NEI); Kafka/full matrix may drive further
  - SHG (`member_details[]`): parent + child; S6 child CRR WARNs may appear without failing minimal smoke
- CRR pass criteria:
  - JLG/INDL default run: `DISB_GL_CBS_INTEGRATION:SUCCESS` and `DISBURSEMENT_NEFT_NEF:SUCCESS`.
  - SHG default run: `DISB_GL_CBS_INTEGRATION:SUCCESS`, `DISBURSEMENT_MFT:SUCCESS`, and subsequent replay inquiry/NEI rows as scenario requires.
- Report locations:
  - JSON summary: `/tmp/*_v2_full_report.json`
  - Text/PDF artifacts: `docs/disbursement-sanity/disburse_loan_suite_<ts>.txt|pdf`
