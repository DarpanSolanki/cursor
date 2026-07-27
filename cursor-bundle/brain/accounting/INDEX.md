# Accounting / LMS Module — Inside-Out Reference

> **Scope:** This bundle lives entirely under `/home/darpan/Documents/sliProd/claude/accounting/`. Nothing outside `/home/darpan/Documents/sliProd/` is touched.
> **Subject service:** `novopay-platform-accounting-v2` (the **Loan Management System** for SHG/JLG MFI lending)
> **Sibling under study:** `novopay-platform-batch`
> **Branch:** `mfi_integration_v3.2.8.4.1` (all 17 darpan repos on the same branch — see [../workspace-state.md](../workspace-state.md))
> **Authoritative code paths:** `/home/darpan/Documents/sliProd/novopay-platform-accounting-v2/` and `/home/darpan/Documents/sliProd/novopay-platform-batch/`

The accounting module is the **Loan Management System (LMS)** of the Trustt Digital Lending Platform. It owns the loan account ledger, GL, interest, repayment, foreclosure, NPA, and dozens of EOD/BOD batch jobs. It does **not** own the scheduling registry — that lives in the batch service, which calls back into accounting via the internal API client. The MFI business is dominated by **SHG (Self-Help Group)** and **JLG (Joint Liability Group)** loans, modelled as one parent loan account + N child loan accounts dispatched via an async event queue.

## Read order — strategic to tactical

| # | File | Read it before you… |
|---|------|---------------------|
| 1 | [01-overview.md](01-overview.md) | …grep through any package, file, or error code |
| 2 | [02-architecture.md](02-architecture.md) | …trust *any* mental model of how a Request reaches a processor (3 paths: CRUD, batch, Kafka) |
| 3 | [03-batch-dependency.md](03-batch-dependency.md) | …rename, add, or schedule a job; or wonder where a "missing" job lives |
| 4 | [04-cross-module-deps.md](04-cross-module-deps.md) | …make any outbound call or assess blast radius |
| 5 | [05-flows.md](05-flows.md) | …debug or extend the 5 money-state flows: disburse / repay / accrue / EOD / NPA |
| 6 | [06-shg-jlg-group-loans.md](06-shg-jlg-group-loans.md) | **…touch anything in `group_mfi_orc.xml` or `loan/grouploan/*`** — the parent/child model and `loan_account_events_queue` are non-obvious |
| 7 | [07-loan-account-lifecycle.md](07-loan-account-lifecycle.md) | …read or write `loan_status`; or investigate "loan stuck in X state". Covers the 16-value `LoanStatus` enum + the `disburseLoan` `function_sub_code` 9-stage state machine |
| 8 | [08-gl-posting-engine.md](08-gl-posting-engine.md) | …debug a wrong GL hit, add a new transaction-catalogue, or change `accountingrules`/`placeholder` masters. Names the 5 masters + 2 engine phases |
| 9 | [09-data-model.md](09-data-model.md) | …write SQL or migrations against `mfi_accounting`. Table-by-table map grouped by responsibility |
| 10 | [10-debugging-runbook.md](10-debugging-runbook.md) | …investigate a production-style issue. 10 scenarios with first-SQL + decision tree + code anchors |

## ★ Loan-servicing flows (every operation, end-to-end)

For inside-out coverage of every loan-servicing API/flow — disbursement, repayment, foreclosure, part-prepayment, death-foreclosure, transaction-reversal, restructuring, rebooking, reopening, waiver, excess-amount-refund, disbursement-cancellation, write-off, advance-repayment — see the dedicated bundle:

📂 **[`../flows/loan-servicing/`](../flows/loan-servicing/)** — 11 servicing flow docs + master index

Each flow doc covers: trigger Request, validators, maker/checker chains, every DB write in order, every GL hit, SHG/JLG fan-out, status transitions, idempotency, failure modes, code anchors.

> Everything cited inside these files is anchored to `file_path:line_number`. If a citation no longer matches, the code drifted — update the doc, don't trust the line numbers blindly.

## ★ Live database ↔ code cross-reference

For the table-by-table mapping (which API/processor writes/reads each `mfi_accounting` table) — including a tool that pulls live schema for any table — see the **dedicated bundle**:

📂 **[`db-code-map/`](db-code-map/)** — 28 per-table docs + 6 by-flow docs + the `inspect-table.sh` tool

- Start at [`db-code-map/00-INDEX.md`](db-code-map/00-INDEX.md) for full table coverage status
- Use [`db-code-map/by-flow/`](db-code-map/by-flow/) when tracing a specific flow's DB writes
- Use [`db-code-map/tools/inspect-table.sh <name>`](db-code-map/tools/inspect-table.sh) for any table not yet curated

## Quick mental model (one paragraph)

`novopay-platform-batch` is a **scheduler + bulk-upload service**. It stores `BatchJob`/`BatchGroup`/`BatchSchedule` rows and, when a job fires, its `DirectJobExecutor` makes an internal HTTP call to whatever orchestration `<Request name="…">` matches `BatchJob.name` — typically a Request defined in `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml` or `mfi_orc.xml` (e.g. `interestAccrualCalculation`, `loanAccountBillingJob`, `runEODJobs`). The actual Spring Batch `Job`/`Step`/`ItemReader`/`ItemProcessor`/`ItemWriter` lives in `in.novopay.accounting.batchnew.*` (and a smaller `in.novopay.accounting.batch.*` for disbursement). LOS publishes async `disburseLoan` events to Kafka, which `LmsMessageBrokerConsumer` in accounting picks up; everything else (master CRUD, transaction posting, reversal) is synchronous orchestration over the gateway, gated by a maker-checker `submitApplication` call to the approval service when `maker_checker_enabled=1`. **For SHG/JLG** the parent loan flow runs synchronously, and per-child fan-out is queued in `loan_account_events_queue` and replayed by `childLoanEventProcessingBatchJob`. **All money movements** funnel through `postTransaction`, whose engine (`ExecuteTransactionRulesProcessor`) resolves placeholder → internal account → GL via the product's `transaction_accounting_rule` rows.

## Sources consulted (read-only)

- **Authoritative (use this for new work):** `/home/darpan/Documents/sliProd/novopay-platform-accounting-v2/` and `/home/darpan/Documents/sliProd/novopay-platform-batch/` — branch `mfi_integration_v3.2.8.4.1`, working tree clean. 9 orchestration XMLs total **23 270 lines**, 27 `batchnew/*` sub-packages, `LmsMessageBrokerConsumer.java` present.
- The service-shipped `trustt-platform-accounting/CLAUDE.md` — provides the high-level scope, table-cluster list, and known complexity gotchas. Treat as authoritative for *what the module is supposed to do*; treat the deep-dive docs here as authoritative for *how it actually does it*.

No writes were performed outside `/home/darpan/Documents/sliProd/`.
