# `novopay-platform-accounting-v2` — LMS Core (Loan Management System)

> The center of gravity. This service owns the ledger, the GL, the loan account, every accrual, every NPA classification, every EOD/BOD batch, every transaction posting. Disbursement *posting* lands here (LOS publishes the trigger; accounting executes the GL hit, books the loan account, fans out child events for SHG/JLG).
>
> **This page is a one-screen index.** The full inside-out reference is in [`../accounting/`](../accounting/) — 10 numbered files plus an INDEX. **Read [`../accounting/INDEX.md`](../accounting/INDEX.md) first**, then the doc that matches the question you're answering.

## Identity

| Field | Value |
|---|---|
| Java root package | `in.novopay.accounting` |
| DB schema | `mfi_accounting` |
| Error-code prefix | `NOT-` |
| Repo | [`novopay-platform-accounting-v2/`](../../novopay-platform-accounting-v2/) |
| Service CLAUDE.md | [`novopay-platform-accounting-v2/CLAUDE.md`](../../novopay-platform-accounting-v2/CLAUDE.md) |

## API surface — orchestration XMLs

9 XMLs totalling **~23 270 lines**, ~340 Requests:

| XML | Lines | Domain |
|-----|------:|--------|
| `ServiceOrchestrationXML.xml` | 9 715 | GL, internal accounts, tax, interest setup, base interest, asset criteria, holiday, working day, savings, server clock, mandates |
| `loans_orc.xml` | 6 490 | Loan account CRUD, disbursement, repayment, prepayment, foreclosure, accrual, billing, restructuring, write-off, advance repayment |
| `mfi_orc.xml` | 2 875 | EOD/BOD, trial balance, foreclosure-charge bulk, manual JE bulk, NOC, dispatch, sec-NPA, derived fields, CASA extracts, NEFT callback |
| `product_transaction_accounting_definition_orc.xml` | 1 829 | Transaction catalogue, placeholder masters, accounting rules, asset classification |
| `insurance_orc.xml` | 779 | Insurance product master + premium calculation matrix |
| `group_mfi_orc.xml` | 687 | **SHG/JLG flows**: child loan booking, repayment, restructuring, foreclosure, transaction reversal, part prepayment, disbursement-cancellation |
| `product_transaction_orc.xml` | 641 | `postTransaction`, `getAccountBalances`, account statement, manual JE post/reverse, GL transfer, GL zeroisation, portfolio transfer |
| `loans_insurance_orc.xml` | 240 | Inbound/outbound disbursement & death-foreclosure insurance jobs (HDFC Life, HDFC Ergo, Bajaj Ergo) |
| `loans_notification.xml` | 14 | Loan notification stubs |

Every Request → see [`../accounting/01-overview.md`](../accounting/01-overview.md) §"Orchestration XMLs". Full Request inventory across all services is queryable via the system KG (`claude/kg/bin/kg flow <request>`).

## Three execution paths

| Path | Trigger | Examples |
|---|---|---|
| **A — Sync CRUD** (gateway) | webapp / android / actor | `createOrUpdateGeneralLedger`, `getLoanAccountDetails`, master-CRUDs (gated by maker-checker) |
| **B — Spring Batch** (sync entry, async execution) | batch service `DirectJobExecutor` HTTP call | `interestAccrualCalculation`, `loanAccountBillingJob`, `runEODJobs`, all `bulk*Job` |
| **C — Kafka consumer** (async) | LOS publishes `disburse_loan_api_<tenant>` | `disburseLoan` consumed by `LmsMessageBrokerConsumer` |

Full Path A/B/C wiring: [`../accounting/02-architecture.md`](../accounting/02-architecture.md).

## Where to start for any question

| You're investigating | Read |
|---|---|
| What this module is and what it owns | [`../accounting/01-overview.md`](../accounting/01-overview.md) |
| How a Request reaches a processor | [`../accounting/02-architecture.md`](../accounting/02-architecture.md) |
| Who triggers a batch job | [`../accounting/03-batch-dependency.md`](../accounting/03-batch-dependency.md) |
| Outbound HTTP / Kafka / inbound | [`../accounting/04-cross-module-deps.md`](../accounting/04-cross-module-deps.md) |
| The five money flows (disburse / repay / accrue / EOD / NPA) | [`../accounting/05-flows.md`](../accounting/05-flows.md) |
| **SHG / JLG parent + child model** | [`../accounting/06-shg-jlg-group-loans.md`](../accounting/06-shg-jlg-group-loans.md) |
| `LoanStatus` state machine + `disburseLoan` 9-stage `function_sub_code` | [`../accounting/07-loan-account-lifecycle.md`](../accounting/07-loan-account-lifecycle.md) |
| How `accountingrules` × placeholder × `internal_account` derive a DR/CR | [`../accounting/08-gl-posting-engine.md`](../accounting/08-gl-posting-engine.md) |
| `mfi_accounting` table-by-table map | [`../accounting/09-data-model.md`](../accounting/09-data-model.md) |
| Production debugging | [`../accounting/10-debugging-runbook.md`](../accounting/10-debugging-runbook.md) and [`../runbooks/`](../runbooks/) |

## Key invariants you must internalise

- **`account.status` (5 values)** is *not* the same as **`loan_account.loan_status` (16 values)** — always read `loan_status` for loan state.
- **`loan_status`** is *not* the same as **`disbursement_status`** — they progress in lock-step but mean different things (see [`../accounting/07-loan-account-lifecycle.md`](../accounting/07-loan-account-lifecycle.md) §3).
- **`disburseLoan` is a 9-stage state machine** driven by `function_sub_code`: `DEFAULT → LAN_CREATED → LOAN_BOOKED → DTFC_SUCCESS → NEFT_STAGE_1_PENDING → NEFT_STAGE_1_SUCCESS → NEFT_STAGE_2_PENDING → REINITIATE_BANK → PARENT_SUCCESS` (or `REJECT`).
- **SHG/JLG = parent loan + N child loans** — children are *not* created inline. They're queued in `loan_account_events_queue` and replayed by `childLoanEventProcessingBatchJob`. If children are missing, the queue is the first thing to inspect.
- **Every GL hit funnels through `postTransaction`** — see [`../accounting/08-gl-posting-engine.md`](../accounting/08-gl-posting-engine.md). Engine bug is rare; calling-flow bug is common.
- **EOD/BOD jobs are scheduled by the batch service**, not by accounting itself. Job names = orchestration Request names. A renamed Request that doesn't update `mfi_batch.batch_job` will silently 404.

## Cross-service callers (inbound)

- `novopay-mfi-los` (Kafka `disburse_loan_api_<tenant>`)
- `novopay-platform-batch` (HTTP via `DirectJobExecutor.startNormalJob()`)
- `novopay-platform-payments` (HTTP `loanRepayment`, `loanRepaymentInquiry`, `postTransaction`, etc. — see `payments/deploy/.../product_accounting.xml`)
- `novopay-platform-webapp` (gateway → all interactive CRUDs + servicing actions)
- `novopay-platform-bpmn` (Camunda service tasks)

## Cross-service callees (outbound)

actor, approval, task, notifications, dms, masterdata, audit (framework-emitted), plus external bank NEFT, insurance providers (HDFC Life / HDFC Ergo / Bajaj Ergo), and Finsall (repayment vendor). Full table in [`../accounting/04-cross-module-deps.md`](../accounting/04-cross-module-deps.md).

## When you'll touch this service

Almost every LMS feature or production issue ends here. The short rule: if money moved or a loan-account state changed, accounting wrote it. Start in [`../accounting/INDEX.md`](../accounting/INDEX.md).

## Local testing / regression suite

For changes to disbursement (the most-tested path), the workspace ships a regression harness at [`/home/darpan/darpan/scripts/`](../../scripts/) — start at [`scripts/START_HERE.md`](../../scripts/START_HERE.md). Provides `make all` to run JLG/INDL/SHG flows against a local Yugabyte + accounting service and emits an HTML report with value-level DB validators (loan_account, schedule, mode_details, mandate, event queue, GL postings). Run before shipping any disburseLoan change.
