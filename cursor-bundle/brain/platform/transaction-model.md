# SOF transaction model — how `<Transaction>` blocks, `explicitTxnMgmt`, and Spring `@Transactional` interact

> Single source of truth for "when does a database write commit, and what can other threads see?" inside a Novopay/Trustt service. Everything written here is anchored to actual file:line.

## TL;DR

- A Request marked `explicitTxnMgmt="true"` has **no auto-managed transaction wrapper** for its individual processors. Only XML `<Transaction>` blocks open a transaction, and each block opens a **fresh `REQUIRES_NEW`** transaction that commits at the end of the block.
- A Request **without** `explicitTxnMgmt` (the default) wraps the **entire processor list** in a single `REQUIRES_NEW` transaction via Spring `@Transactional` on `ProcessorOrchestrator.executeProcessorsWithImplictTransactionCommitBoundary` — meaning every DB write across all processors is uncommitted until the Request finishes.
- All DB writes inside a transaction are invisible to other transactions under READ COMMITTED **until the transaction commits**. Async callbacks / Kafka consumers / reactor threads each have their own transactions and cannot see the orchestration's uncommitted writes.
- DAO methods explicitly annotated `@Transactional(propagation = REQUIRES_NEW)` (e.g. `ClientRequestResponseLogDAOService.save`) commit immediately regardless of the caller's transaction.

## The two execution paths

[`ServiceOrchestrator.executeProcessors`](../../novopay-platform-lib/infra-navigation/src/main/java/in/novopay/infra/navigation/orchestrator/ServiceOrchestrator.java#L89-L108) chooses one of two paths based on `explicitTransactionManagment`:

| Path | When it runs | What it does |
|---|---|---|
| **Implicit boundary** | `explicitTxnMgmt` is `false` (default) **OR** `httpMethodType == "get"` | Calls `processorOrchestrator.executeProcessorsWithImplictTransactionCommitBoundary` — wraps the entire processor list in `@Transactional(propagation = REQUIRES_NEW, isolation = READ_COMMITTED, noRollbackFor = NovopayNonFatalException.class)`. One transaction for the whole Request. |
| **Explicit boundary** | `explicitTxnMgmt="true"` **AND** non-GET | Calls `processorOrchestrator.executeProcessorsWithExplicitTransactionCommitBoundary` — iterates processors with NO outer transaction. Only XML `<Transaction>` blocks open transactions. |

### Implicit path — `ProcessorOrchestrator.executeProcessorsWithImplictTransactionCommitBoundary`

[Code reference, line 58-69](../../novopay-platform-lib/infra-navigation/src/main/java/in/novopay/infra/navigation/orchestrator/ProcessorOrchestrator.java#L58-L69):

```java
@Transactional(propagation = Propagation.REQUIRES_NEW, isolation = Isolation.READ_COMMITTED,
               noRollbackFor = NovopayNonFatalException.class, rollbackFor = Exception.class)
public void executeProcessorsWithImplictTransactionCommitBoundary(...) {
    for (ExecutionUnit exeUnit : processorAPIList) {
        executionContext.clearLocalMap();
        if (exeUnit instanceof Processor) processProcessor(...);
        else if (exeUnit instanceof API) processInternalAPI(...);
    }
}
```

Implications:
- One commit at the end of the Request. All DB writes within the Request are atomic.
- A failure (any `Exception`) rolls back everything; `NovopayNonFatalException` does not.
- Other threads see nothing until commit.

### Explicit path — `ProcessorOrchestrator.executeProcessorsWithExplicitTransactionCommitBoundary`

[Code reference, line 99-129](../../novopay-platform-lib/infra-navigation/src/main/java/in/novopay/infra/navigation/orchestrator/ProcessorOrchestrator.java#L99-L129):

```java
public void executeProcessorsWithExplicitTransactionCommitBoundary(...) {
    for (ExecutionUnit exeUnit : processorAPIList) {
        executionContext.clearLocalMap();
        if (exeUnit instanceof Processor) processProcessor(...);                  // NO TRANSACTION
        else if (exeUnit instanceof API) processInternalAPI(...);                 // NO TRANSACTION
        else if (exeUnit instanceof Transaction) {
            DefaultTransactionDefinition txnDef = new DefaultTransactionDefinition();
            setTransactionIsolationLevel(txnDef, (Transaction) exeUnit);
            txnDef.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
            TransactionStatus txnStatus = transactionManager.getTransaction(txnDef);
            try {
                executeProcessorsWithExplicitTransactionCommitBoundary(executionContext, ((Transaction) exeUnit).getExecutionUnitList(), controlStatusMap);
            } catch (Throwable t) {
                transactionManager.rollback(txnStatus);
                ... undo processors ...
                throw t;
            }
            transactionManager.commit(txnStatus);
        }
    }
}
```

Implications:
- Processors / APIs **outside** a `<Transaction>` block run with NO managed transaction (DAO methods that are themselves `@Transactional` open their own; otherwise auto-commit per JDBC operation).
- Each `<Transaction>` block opens a **NEW** transaction (`REQUIRES_NEW`) and commits at the end of the block — independent of any other block.
- A failure inside a `<Transaction>` block rolls only that block back, runs `executeTxnUndoProcessors`, then propagates.
- Multiple `<Transaction>` blocks within one Request commit at different times — earlier blocks are visible to other transactions before later blocks finish.

## Where this matters in practice — disburseLoan

[`mfi_orc.xml:4`](../../novopay-platform-accounting-v2/deploy/application/orchestration/mfi_orc.xml#L4) declares:

```xml
<Request name="disburseLoan" isAsync="true" explicitTxnMgmt="true">
```

So disburseLoan uses the **explicit** path. The Request body has multiple `<Transaction>` blocks visible at lines 235, 248, 477, 514, 525 (new from `a6fdc1c88`), 532, 585. Each block commits independently. Processors outside blocks run un-managed (relying on DAO-level `@Transactional` if any).

This is what enabled the disburseLoan visibility-race fix (`a6fdc1c88`): adding a new `<Transaction>` block before the bank-call block makes the CLMT row inserts commit before any bank call fires, so async callbacks can see them.

## Spring `@Transactional` on DAO methods

Several DAO methods carry their own `@Transactional` annotations and **commit independently of the caller's transaction**:

| DAO method | Propagation | Effect |
|---|---|---|
| `ClientRequestResponseLogDAOService.save` ([line 39](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/client/repository/ClientRequestResponseLogDAOService.java#L39)) | `REQUIRES_NEW` | CRR rows commit IMMEDIATELY regardless of orchestration's outer transaction. This is why CRR audit always lands cleanly even when queue updates fail. |
| `ClientRequestResponseLogDAOService.saveAll` ([line 46](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/client/repository/ClientRequestResponseLogDAOService.java#L46)) | `REQUIRES_NEW` | Same. |
| `LoanAccountEventsQueueDAOService.save` / `saveAll` | (none — joins caller) | Queue rows commit only when the caller's transaction commits. This was the source of the CLMT visibility race in disburseLoan. |
| Spring Data JPA `JpaRepository.save` / `saveAll` (default) | `REQUIRED` | Joins caller's transaction; if no caller txn, opens its own short transaction. |

**Decision rule for DAO transaction policy:**

- **Audit-trail tables** (CRR, audit_log) → `REQUIRES_NEW` so the audit row survives even if the business operation rolls back.
- **State-machine tables** (queue rows, loan_account state transitions) → join caller's transaction so success/failure is atomic with the orchestration step.
- **Cross-thread-visible state** (rows that callbacks/jobs need to see during the orchestration) → either `REQUIRES_NEW` per write, or split orchestration into multiple `<Transaction>` blocks so each block commits before downstream writes start. The `a6fdc1c88` disburseLoan fix uses the second approach.

## Visibility under READ COMMITTED

Default isolation is READ COMMITTED ([`ProcessorOrchestrator.java:58, 71`](../../novopay-platform-lib/infra-navigation/src/main/java/in/novopay/infra/navigation/orchestrator/ProcessorOrchestrator.java#L58)). Implications:

- A reader (different thread / different transaction) sees only **committed** rows. Writes from other in-flight transactions are invisible until they commit.
- Within the same transaction, a reader sees its own uncommitted writes (read-your-writes).
- Phantom reads can occur (REPEATABLE READ would prevent them). Not a problem in practice for the patterns we use.

**The classical race**: orchestration thread A writes row R inside its transaction at time t0. Reader thread B (callback / Kafka consumer / batch job / reactor post-handler) queries for R at time t1 > t0. If A has not committed by t1, B sees no row → bails / errors. If A is a long-running orchestration, t1 - t0 can be 5–10+ seconds. This is exactly the CLMT visibility race.

## Cross-links

- Async patterns and how Kafka / WebClient / async callbacks interact with this transaction model: [`async-patterns.md`](async-patterns.md).
- platform-lib module index: [`platform-lib.md`](platform-lib.md).
- Disbursement-specific application of these primitives: [`../engines/disbursement-engine.md`](../engines/disbursement-engine.md).
- Transaction-related concurrency fixes shipped on `mfi_integration_v3.2.8.4.1`: see entries dated 2026-05-04 onwards in [`../changelog/CHANGELOG.md`](../changelog/CHANGELOG.md).

## Things to NOT do

- **Do not assume** all processors in a Request run in one transaction. Check `explicitTxnMgmt` first — if true, only `<Transaction>` blocks are atomic.
- **Do not annotate processors** with `@Transactional` directly. The framework manages boundaries; adding annotations creates nested-transaction confusion.
- **Do not add cross-thread reads** of rows that were written in the current orchestration's transaction without verifying the visibility timing. If the row must be visible to a callback, either commit it via `<Transaction>` block / `REQUIRES_NEW` DAO method, OR pass the entity reference through the execution context.
- **Do not rely on `accountingBankServiceRetryJob` to recover orphan queue rows** — it scans `client_request_response_log`, not `loan_account_events_queue`. See [`../accounting/03-batch-dependency.md`](../accounting/03-batch-dependency.md) for which jobs scan which tables.
