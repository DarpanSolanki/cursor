# Async patterns — threads, transactions, and the races between them

> Companion to [`transaction-model.md`](transaction-model.md). Maps the actual thread types in a running accounting service, how each one carries (or doesn't carry) a database transaction, and where they race with the SOF orchestration's transaction.

## The four thread families

| Thread family | Where it runs | Owns a transaction? | Typical work |
|---|---|---|---|
| **Tomcat HTTP worker** (`https-jsse-nio-8002-exec-N`) | API gateway entry point | Yes — Spring opens a transaction per request handler | Receives external API calls (LOS → accounting, bank → accounting webhook callbacks) |
| **SOF orchestration executor** (`NP-Executor-N`) | Async Kafka-consumer-driven orchestrations like `disburseLoan` | Yes — driven by Request's `explicitTxnMgmt` setting | Runs long-form orchestrations where the API caller already returned |
| **Batch job thread** (`NP-Batch-N` / Spring Batch job-launcher) | Scheduled batch jobs and on-demand `DirectJobExecutor` runs | Yes — typically per-step Spring `@Transactional` | EOD/BOD jobs, retry jobs, periodic recovery jobs |
| **Reactor Netty worker** (`reactor-http-epoll-N`) | WebClient response post-handlers | **No** — runs entirely outside any caller transaction | Bank-call response post-processors (PostNEFTChildLoanBankDisbursementProcessor etc.) |

## Where each thread can write what

| Thread | Reads | Writes | Notes |
|---|---|---|---|
| Tomcat worker (callback receive) | CRR (committed via `REQUIRES_NEW`), queue rows (only if committed by orchestration) | CRR (REQUIRES_NEW), queue rows (own short txn) | Cannot see orchestration's uncommitted queue writes — this was the cause of the CLMT visibility race |
| SOF orchestration | Anything its transaction touched (read-your-writes), plus committed rows from other txns | Everything — but only commits at end-of-Request (implicit) or end-of-`<Transaction>`-block (explicit) | Long-running; commit can be 10+ seconds from first write |
| Batch job thread | Whatever the step query returns (committed only) | Through DAOs | Step-scoped transactions |
| Reactor worker | Entity reference passed via EC (no DB query needed); CRR (committed `REQUIRES_NEW`) | Updates queue row using the entity reference | When the entity's `@Version` is stale relative to DB → `OptimisticLockingFailureException` |

## The Kafka-consumer entry path (disburseLoan)

[`LmsMessageBrokerConsumer`](../../trustt-platform-accounting/src/main/java/in/novopay/accounting/consumers/LmsMessageBrokerConsumer.java) consumes `disburse_loan_api_<tenant>` topic, deduplicates via Redis key `dl<productId>_<extRef>`, then calls:

```java
getServiceOrchestrator().executeProcessors(
    executionContext,
    orcRequest.getProcessorAPIList(),
    orcRequest.isExplicitTransactionManagment(),  // → true for disburseLoan
    orcRequest.getHttpMethodType(),
    controlStatusMap,
    orcRequest.getUndoProcessorList());
```

Critical points:
- The Kafka consumer does NOT wrap the orchestration in its own transaction.
- `orcRequest.isExplicitTransactionManagment() == true` for disburseLoan → uses the explicit boundary path (only `<Transaction>` blocks open transactions).
- Redis dedup at consumer entry prevents re-processing the same Kafka message.

## The WebClient + reactor post-handler path

`neftServicePartnerDiscoveryService.neftNEFTransactionWithWebClient(executionContext, postProcessor)` and `miscFundTransferWithWebClient(...)` (MFT):

1. SOF orchestration thread builds the request, fires WebClient call, returns `Mono`.
2. WebClient sends HTTP request to bank.
3. Bank's response arrives on a `reactor-http-epoll-N` thread.
4. Spring's `WebClientServiceExecutorDecorator` parses the response and **invokes the post-processor on the reactor thread** with `apiResponse` as a `Map<String, Object>`.
5. Post-processor (`PostNEFTChildLoanBankDisbursementProcessor.execute` / `PostMFTChildLoanBankDisbursementProcessor.execute`) updates DB.

The reactor thread:
- Has NO inherited transaction from the orchestration thread (different thread, different ThreadLocal).
- Uses the entity reference passed via `executionContext.getValue("loan_account_events_queue_entity", ...)` — this is a JPA-detached entity (Hibernate session of orchestration thread isn't accessible here).
- Calls `loanAccountEventsQueueDAOService.save(entity)` which goes through `JpaRepository.save` (`@Transactional(REQUIRED)`) — opens its own transaction since none is inherited.
- `OptimisticLockingFailureException` fires when the entity's `@Version` doesn't match the DB's current version (e.g. another writer updated the row).

This is where the OLE-escape pattern lived: an unhandled OLE on a reactor thread escapes to `Operators.onErrorDropped` and is silently swallowed. Fixed in `c2583dca9` (NEFT) and `5bb49d7a4` (MFT) with targeted catches in `execute()`.

## The bank async callback path

Bank receives a NEFT_NEF / NEFT_NEI request from accounting and later POSTs the outcome back to accounting's webhook (`doGenericSyncSTPBankNEFNeftCallBack` API). This arrives on a Tomcat worker thread:

1. API gateway routes to the configured Request.
2. SOF executes `DoGenericSyncSTPBankNeftCallBackProcessor`.
3. The processor parses the bank's payment list, looks up CRR rows (via `client_reference_number`) and queue rows (via `filler_2`), updates state.

The race we fixed: the queue lookup `findOneByFiller2` could not see CLMT rows that the disburseLoan orchestration (running on a different thread, different transaction) had INSERTed but not yet committed. Fixed structurally in `a6fdc1c88` by splitting the orchestration's `<Transaction>` block so CLMT rows commit before bank calls fire. Defense-in-depth retry-with-backoff also added in `8abd48f49`.

## The race matrix (post-fix state)

| Race | Mechanism | Status |
|---|---|---|
| Orchestration thread vs callback thread on queue row visibility | Orchestration's `<Transaction>` block holds CLMT INSERTs uncommitted while bank calls fire | **Fixed** by `a6fdc1c88` (CLMT prep block commits first) |
| Orchestration thread vs callback thread on CRR visibility | None — CRR `save` is `REQUIRES_NEW` so writes commit immediately | Already safe |
| Two reactor threads writing the same queue row (concurrent siblings) | Only one updater per child row in normal flow; child queue rows are 1:1 with bank legs | Not racy |
| Orchestration thread vs reactor thread on stale CLMT row state | EC entity shared across thread boundary; outer Hibernate persistence context can auto-flush a reactor-thread mutation back to DB with stale `updated_on` | **Fixed** by atomic CAS redesign (PR #260, `e3d84a53b` … `f6e83c9fe`) + post-CAS in-memory mutation removal (`4c339282f`, `09295c377`). State changes go through `ChildClmtStateMachineService.transition`; advisory writes through `patchJsonFields`. Reactor handlers no longer call setters on the shared entity. See `engines/disbursement-engine.md` §4.8. |
| Cross-pod duplicate child bank-leg execution | Pre-fix: JVM-local set; cross-pod was unprotected | **Fixed** by atomic Redis SETNX (`ede4aa325` + `4cb437b28`) |
| Late callback after row already terminal | Row at COMPLETED; callback tries to demote | Guard at [`DoGenericSyncSTPBankNeftCallBackProcessor.java:367`](../../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/disbursement/processor/DoGenericSyncSTPBankNeftCallBackProcessor.java#L367) drops the FAIL with a log line. Intentional asymmetry. |

## Things that still don't have automatic recovery

- **Orphan PENDING CLMT rows**: if the disburseLoan orchestration aborts after CLMT rows commit (via the `a6fdc1c88` prep block) but before any bank call fires, those rows persist. **No scheduled job recovers them.** Recovery requires re-invoking disburseLoan for that parent — at which point [`PerformChildLoanBankDisbursementProcessor.java:74-78`](../../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/disbursement/processor/PerformChildLoanBankDisbursementProcessor.java#L74) reuses the existing rows.
- **Bank never sends an async callback** for a fired NEFT call: queue stays at `NEFT_STAGE_1_PENDING`. Recovery is the `NEFT_TRANSACTION_INQUIRY` path inside `ChildDisbursementNeftV2BankCall`, but it requires the loan to be re-touched by a disburseLoan call.

These are documented operationally; no scheduled poller exists. Tests should run real bank scenarios; mocks miss this entirely.

## Cross-links

- Transaction boundary semantics: [`transaction-model.md`](transaction-model.md).
- Batch-job ↔ orchestration table coverage: [`../accounting/03-batch-dependency.md`](../accounting/03-batch-dependency.md).
- Disbursement-specific application: [`../engines/disbursement-engine.md`](../engines/disbursement-engine.md).
- Recent concurrency fixes (2026-05-04 onwards): see [`../changelog/CHANGELOG.md`](../changelog/CHANGELOG.md). NEFT v2 race-class closeout is the 2026-05-07 entry (`4c339282f` + `09295c377`).
