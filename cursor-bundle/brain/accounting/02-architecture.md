# 02 · Accounting — Architecture

## Three execution paths

The accounting service answers requests through **three** distinct execution paths. Knowing which path a Request uses is the first thing to check when debugging.

```
        ┌──────────────────────────────────────────────────────────────┐
        │                  novopay-platform-api-gateway                │
        └──────────────────┬─────────────────────────────────┬─────────┘
                           │ HTTP (sync)                     │ HTTP (sync)
                           ▼                                 ▼
                    ServiceOrchestrator                ServiceOrchestrator
              (interactive CRUD / postTransaction)  (`runEODJobs`, `runBODJobs`,
                                                     bulk-upload submitters)
                           │                                 │
                           │                                 │ kicks Spring Batch
                           ▼                                 ▼
                  domain processors                  batchnew/* Job + Step
                  (DAO writes, GL hit)               (ItemReader → Processor → Writer)

   ┌──────────────────┐   Kafka            ┌────────────────────────────────────────┐
   │  novopay-mfi-los │ ──────────────────▶│ LmsMessageBrokerConsumer (accounting) │
   │ (disburseLoan)   │  los_lms_disb...   │  → ServiceOrchestrator (disburseLoan) │
   └──────────────────┘                    └────────────────────────────────────────┘
                                                         │
                                                         └─▶ result event back to LOS
                                                            on `los_lms_disbursement_sync`

   ┌────────────────────────┐ HTTP    ┌──────────────────────────────────────────┐
   │ novopay-platform-batch │────────▶│ Accounting orchestration `<Request>` by  │
   │ (DirectJobExecutor)    │ internal│  name = BatchJob.name                    │
   └────────────────────────┘  API    └──────────────────────────────────────────┘
```

## Path A — Interactive CRUD (sync, gateway)

Used by every `createOrUpdate*`, `get*`, `delete*` Request. Two flavours, gated by `${maker_checker_enabled}`:

**maker_checker_enabled = 1** (default for masters)
1. `accounting_getUserDetails` — actor service
2. `getUserDetailsPostProcessor`
3. `accounting_getUseCaseDetails` — actor service (use-case master, e.g. `GENL-LEDG-UC001`)
4. `getUseCaseDetailsPostProcessor`
5. `checkDataFor*` — domain validation
6. `fetchBulkUniqueMasterData` — populate friendly labels
7. `sendForApproval*PreProcessor` — emits `AuditData{entity_type=SEND_FOR_APPROVAL_*, new_data=…}`
8. `accounting_submitApplication` — **calls approval service**, persists draft + workflow row
9. `deleteDraftProcessor` — clears local draft cache
10. `accounting_getNotificationMessage` — notifications service for response copy
11. `setUserStoryForResponseProcessor`
12. `dummyProcessor` — sets `responseCode=30003` (sent for approval)

When the approval cycle completes the same Request fires again with `function_code=APPROVE`, which skips the approval branch and runs the actual domain `*Processor` (e.g. `createGeneralLedgerProcessor`) → `responseCode=30000`.

**maker_checker_enabled = 0**
1. `populateCurrentDateProcessor`
2. `dummyProcessor` — maps `user_id`→`created_by`/`updated_by`, `current_date`→`created_on`/`updated_on`
3. Domain `*Processor` — DAO write + audit emit
4. `accounting_getNotificationMessage`
5. `setUserStoryForResponseProcessor`
6. `dummyProcessor` — `responseCode=30000`

`function_code=RESUBMIT` exists as a third branch for re-sending a previously rejected draft; it goes to `submitApplication` again with the prior `application_id`.

## Path B — Spring Batch (sync entry, async execution)

These Requests are listed in `loans_orc.xml` / `mfi_orc.xml` but their orchestration body delegates to a Spring Batch `Job`. Examples:

| Request | Job package |
|---------|-------------|
| `interestAccrualCalculation` | `batchnew.interest.interestaccrualcalculation` |
| `interestAccrualPosting` | `batchnew.interest.interestaccrualbooking` |
| `loanAccountBillingJob` | `batchnew.loanaccountbilling` |
| `penalInterestAccrualCalculation` / `penalInterestAccrualBooking` | `batchnew.penal` |
| `loanAccountDpdCalcJob` / `loanAccountAssetCriteriaJob` / `loanAccountAssetClassificationJob` | `batchnew.npa.primary` / `secondary`, `batchnew.derivedfields` |
| `runEODJobs` / `runBODJobs` | aggregator that fans out to the above |
| `trialBalanceCalculation` / `trialBalanceZeroisationJob` | `batchnew.trialbalance` |
| `bulkSGToManualJournalEntriesJob` | `batchnew.bulkmanualjournalentry` |
| `bulkSGToFinsallRepaymentJob` | `batchnew.bulkrepayment.bulksgtofinsallrepaymentjob` |
| `accountingBankServiceRetryJob` | `batchnew.bankservicecallretry` |
| `childLoanEventProcessingBatchJob` | `batchnew.childloaneventprocessingbatchjob` |
| `loanRecurringPaymentBatchApi` | `batchnew.loanrecurringpaymentbatchapi` |

Each job is configured by a `*BatchConfigService` extending `infra.batch.builder.CustomCommonStepBuilder`, partitioned via `Partitioner` (`GRID_SIZE` typically 10 threads), and wraps an `ItemReader` (`SynchronizedItemStreamReader<Object[]>`), an `ItemProcessor`, and an `ItemWriter`. Failure rows go to `*FailureEntityMapper` → `batch_failure_audit` table.

Concrete excerpt — `InterestAccrualCalculationBatchConfigService`:

```java
public static final String JOB_NAME ="interestAccrualCalculation";
public static final int GRID_SIZE = 10;
@Autowired InterestAccrualCalculationItemWriter   ...itemWriter;
@Autowired SynchronizedItemStreamReader<Object[]> ...itemReader;
@Autowired InterestAccrualCalculationItemProcessor ...itemProcessor;
```

## Path C — Kafka consumer (async, LOS → accounting)

`in.novopay.accounting.consumers.LmsMessageBrokerConsumer` implements `NovopayMessageBrokerConsumer`. Message format is `apiName|requestBody|cacheKey`, where `cacheKey = "disburseLoan{productId}_{externalRefNumber}"`.

```
ConsumerRecord
   │
   ▼
processConsumerRecord
   │
   ├── parse productId + externalRefNumber from cacheKey
   │
   ├── getDisburseSkipReason(...)
   │     ├── DAO lookup: loanAccountDAOService
   │     │     .findLoanByExternalRefNumberAndProductId(...)
   │     ├── ALREADY_ACTIVE  →  loan in ACTIVE + disbursement_status=COMPLETED
   │     │                       → push SUCCESS to los_lms_disbursement_sync, return
   │     ├── LOCK_LOAN_STATUS → loan in LOCK status → just return
   │     ├── LOCK_CACHE_IN_PROGRESS → key exists in Redis ACCOUNTING db → return
   │     └── NONE → continue
   │
   ├── novopayCacheClient.set(tenant, "dl"+cacheKey, "true")     ← Redis dedup
   │
   ├── executeServiceOrchestration(record)
   │     ├── parse api + body
   │     ├── DefaultExecutionContextPopulator.populateExecutionContext("disburseLoan", "v1", …)
   │     ├── orcXMLParser.getRequestFromOrcXML(tenant, "disburseLoan")
   │     └── ServiceOrchestrator.executeProcessors(...)          ← runs disburseLoan Request
   │
   └── finally {
         sendResultMessageToKafka(externRefNumber, isSuccess, exception)
                          → topic: los_lms_disbursement_sync
         cleanupCacheKeys(tenant, original, dl-prefixed)
       }
```

Key invariants:
- The cache key is `disburseLoan{productId}_{externalRefNumber}`; the in-progress key is the same with a `dl` prefix.
- `productId` defaults to `0` if missing/non-numeric.
- Result payload includes `external_ref_number`, `status`, `error_code` (`UNKNOWN_ERROR` fallback), `error_message` (resolved via `notificationUtil.getResponseMessage`), `tenant_code`, `timestamp`.
- The dedup is **per-tenant** — `novopayCacheClient` is tenant-scoped and writes to `RedisDBConfig.ACCOUNTING.getDbIndex()`.

## Async producer (`AccountingKafkaProducer`)

`in.novopay.accounting.service.AccountingKafkaProducer` — used by:
- `LmsMessageBrokerConsumer` to push `los_lms_disbursement_sync` events.
- Other accounting flows that need to fan-out events back into LOS or into other accounting jobs (e.g. `enach`, `loanaccountservicingdocumentevents`).

## Configuration entry points

| File | Purpose |
|------|---------|
| `deploy/application/orchestration/*.xml` | Request → processor pipeline definitions |
| `src/main/resources/application*.properties` | DataSource, Kafka brokers, Redis, retry timeouts |
| `src/main/java/in/novopay/accounting/config/*` | Spring `@Configuration` classes for Kafka, Redis, scheduler, web, cache |
| `infra` library (shared) | `CustomCommonStepBuilder`, `ParallelBatchJob`, `ParallelCommonBatchJob`, `GenericListenerV3`, `OrchestrationXMLParser`, `ServiceOrchestrator`, `NovopayInternalAPIClient`, `NovopayCacheClient`, `NovopayMessageBrokerConsumer` |

## Transaction management

A Request with `explicitTxnMgmt="true"` (e.g. `postTransaction`, `loanRepayment`, `disburseLoan`) opts out of the framework's per-Request transaction wrapper and lets the inner processors manage transactions themselves — important for batch and Kafka paths so a single failure doesn't roll back the whole batch step.
