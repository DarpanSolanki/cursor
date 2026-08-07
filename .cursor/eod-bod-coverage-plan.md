# EOD/BOD coverage plan — accounting (LMS)

Scope set by `data/Trustt- HDFC EOD BOD.xlsx`, sheet `All Autosys Jobs` — the schedule
production actually runs, not what the code implies. **110 jobs; all 110 resolve in
`.cursor/platform-api-map.md`**, which is the useful cross-check in both directions: the map
is missing nothing production runs, and the sheet names nothing the platform cannot serve.

Accounting owns **26**. Penal is out of scope by request (`penalInterestAccrualCalculation`,
`penalInterestAccrualBooking`), leaving **24**.

Regenerate the scope: `python3 scripts/testing/autosys_jobs.py --repo accounting`

## The finding that shapes this plan

Four EOD/BOD jobs were run for real locally — `loanAccountDpdCalcJob`,
`interestAccrualCalculation`, `interestAccrualPosting`, `loanAccountBillingJob`, all reaching
`COMPLETED` — and the database was diffed before and after.

| | Tables |
|---|---|
| Static map claimed | `interest_accrual_details`, `loan_account`, `loan_account_billing_details` |
| Actually written | `transaction_details` (+304), `transaction_partition_details` (+304), `transaction_master` (+83), `loan_account_billing_details` (+69 new / 4050 updated), `interest_accrual_details` (+20), `account` (2154 updated) |

**The map misses every posting table.** The KG's footprint is `request → processor → table`,
and a batch job's real writes happen in a Spring Batch `ItemWriter` under `batchnew/**`, past
the orchestration processor the edge stops at. `loanAccountBillingJob` shows one written table
and writes six.

This is not a batch-only concern. Any flow that delegates to a writer is under-reported, which
means **a money change can look contained and not be.**

Two method notes worth keeping, because both produced a wrong answer first:

- A row-count diff sees `INSERT` only. `account` moved 2154 rows with **no** count change.
  Detecting it needs `updated_on`, and `interest_accrual_details` has no such column at all.
- The first update query returned zero and looked like a clean result. It was `order by 2` on
  a single-column select, with the error swallowed by `2>/dev/null`. A silent empty result is
  not evidence.

## Tasks

### 1 — Make batch writers visible in the map  ·  blocks honest coverage for all 24

The static footprint is wrong for every batch job, so every claim built on it is soft.

- Extend the KG (or a companion scan) from the orchestration processor into the Spring Batch
  chain: `*BatchConfigService` → `ItemReader` / `ItemProcessor` / `ItemWriter` → repository →
  table. `LoanAccountBillingItemWriter` is the worked example.
- Add `tables_written_runtime` to the API map, populated by an observed before/after diff, and
  keep it beside the static set rather than replacing it — where they disagree is the signal.
- Encode the diff harness properly: count-diff for inserts, `updated_on` for updates, and an
  explicit `no audit column` marker where neither works.

### 2 — Establish the real EOD → BOD sequence as a runnable chain

Production order, from the sheet (sequence numbers are Autosys's, not mine):

| Phase | Seq | Job |
|---|---:|---|
| EOD | 2 | `loanAccountDpdCalcJob` |
| EOD | 3 | `loanAccountAssetCriteriaJob` |
| EOD | 4 | `loanAccountAssetClassificationJob` |
| EOD | 7 | `loanAccountClosure` |
| BOD | 9 | `trialBalanceCalculation` |
| BOD | 10 | `trialBalanceZeroisationJob` |
| BOD | 11 | `updateLoanAccountDerivedFieldsJob` |
| BOD | 12 | `updateLoanAccountDerivedFieldsMonthlyJob` |
| BOD | 13 | `interestAccrualCalculation` |
| BOD | 14 | `interestAccrualPosting` |
| BOD | 15 | `loanAccountBillingJob` |
| BOD | 16 | `loanAdvanceRepayment` |
| BOD | 17 | `generateSIPresentationFiles` |
| BOD | 18 | `generateEnachPresentationFile` |
| Post EOD-BOD | 19 | `loanRecurringPaymentBatchApi` |
| Post EOD-BOD | 34 | `loanInstallmentDueNotificationJob` |
| Post EOD-BOD | 35 | `loanInstallmentBounceNotificationJob` |
| Post EOD-BOD | 36 | `proactiveExcessAmountRefundStaging` |
| Post EOD-BOD | 37 | `proactiveExcessAmountRefund` |
| Post EOD-BOD | 38 | `extractCasaBalanceFor182ProductCode` |
| Post EOD-BOD | 39 | `extractCasaBalanceFor180ProductCode` |
| Report | 19 | `generatePostEODReports` |
| Report | 20 | `generateTBZeroisationReport` |
| Report | 44 | `generateNocFileJob` |

- Run the chain in this order against one seeded fixture, capturing the footprint per job.
  Running a job alone hides ordering defects — accrual before posting is a different outcome
  from posting before accrual, and only the sequence shows it.
- Compare against `runEODJobs` / `runBODJobs`, which call only a subset. Where the
  orchestration entry point and the Autosys schedule disagree, **Autosys is production**.

### 3 — Value-level asserts for the money jobs  ·  demonstrated, not predicted

`batch.dpd_calc`, `batch.interest_accrual_calc`, `batch.interest_accrual_posting`,
`batch.loan_account_billing` currently assert HTTP 200, `SUCCESS`, and `COMPLETED`.

This was written as a prediction. It is now a measurement. The same four cases were run twice
through `scripts/testing/job_footprint.py`:

| Run | Rows inserted | Cases |
|---|---|---|
| First | 780 across 5 tables | all COMPLETED, all pass |
| Second, same business date | **0** | all COMPLETED, **all pass** |

The jobs are idempotent for a business date, so the second run did no work — and nothing in
the current asserts could tell the difference. **A silently skipped EOD passes today.** That
is the failure mode this task exists to close, and it is reproducible on demand.

It also means fixture state decides what a footprint measurement shows. Measure on a fresh
business date, or the answer is "nothing happened" and that is not the job's fault.

### Task 0 — measure a job's work from batch metadata, not from row counts

An earlier draft of this section claimed `loanAccountDpdCalcJob` writes zero rows and does no
work. **That was wrong**, and the way it was wrong is the useful part.

The evidence for it was `loan_account.updated_on`: zero rows changed in a 3-minute window
either side of the run. The evidence against it is `mfi_batch.batch_step_execution`, which
records what the job actually did:

```
loanAccountDpdCalcJobmStep1              read 2154   write 2154   COMPLETED
loanAccountDpdCalcJobsStep1:partition0-9 read  216   write  216   COMPLETED  (each)
```

The job reads and writes all 2154 active loans. `write_count` counts items handed to the
writer; Hibernate dirty-checking then issues **no SQL UPDATE** for an entity whose fields are
unchanged, so `updated_on` never moves. Absence of a row change is not absence of work.

Two further corrections in the same direction:

- The `minId=1 / maxId=1000` job parameters looked like a smoking gun — real `account_id`
  values run 119 to 8,243,861. They are not: `updateGrideSize` recomputes the bounds at
  runtime, which the partition read counts confirm.
- "1979 of 2057 active loans carry a stale `past_due_days`" was **my recompute disagreeing
  with the implementation**, not proof of staleness. A formula written from the data model
  rather than from the code is a guess, and it was.

**What is actually true:** the job does its work and is idempotent — the stored values are
already correct for that `job_time`, so a correct re-run changes nothing. That is healthy.

**What still holds:** no assert here can distinguish "ran and had nothing to change" from
"did not run", because batch postings carry no per-run correlator the harness can see. The
right instrument is `batch_step_execution.read_count` / `write_count` joined on the execution
the harness just triggered — the harness already captures `exec_id`. That is a harness
enhancement, not an SQL one, and it is what would make these asserts prove work.

*(Scoping note for the invariant: 8 accounts carry a positive `past_due_days` with no open due.
All are `CLOSED` or `FORECLOSURE_FREEZE` — residual history on a non-active account, which is
legitimate, so the invariant is scoped to `ACTIVE`.)*

Per `run-the-real-thing-locally.md`, each needs exact column values on the tables the run
actually touched — the six above, not the three the map claimed. Add the assert, watch it fail
on the broken path, then fix.

### 4 — Cover the 17 jobs with no case at all

Ten BOD, seven Post EOD-BOD. `trialBalanceCalculation` and `trialBalanceZeroisationJob` first:
they are the GL integrity jobs, and `accounting.gl_balance_zeroisation` is the one registry
case whose last run failed.

### 5 — Reconcile the report/extract jobs

`generatePostEODReports`, `generateTBZeroisationReport`, `generateNocFileJob` produce files
operations depend on. `Master-Sheet` in the same workbook carries `is_critical`,
`should available in sftp` and a shift owner per job — that is the acceptance contract, and it
is not currently encoded anywhere in the harness.

## Out of scope

Penal (`penalInterestAccrualCalculation`, `penalInterestAccrualBooking`) — excluded by request.
The other 84 Autosys jobs belong to reporting (56), payments (17), LOS (8), task (2) and
masterdata (1).

## Production calibration — read this before trusting anything below

**Production runs every one of these jobs successfully, year-end jobs included.** That is the most
important fact in this document and it arrived late. Everything measured here was measured on a
local fixture that differs from production in at least four known ways:

| Environment delta | What it broke locally |
|---|---|
| `JOB_TIME` correlator is **18:00 IST**; the platform passes the **midnight** business date | Produced a false defect report — GAP-099, withdrawn same day |
| Redis `current.business.date` is **eight months stale**, no TTL, survives restarts | `loanAdvanceRepayment` reported COMPLETED and moved no money |
| `/apps` **does not exist** | Every outbound file job; `generateNocFileJob` returns an opaque `333` |
| Fixture accumulated across **two years** of aborted runs | 62 orphan eNACH mandates killed the whole presentation file |

**A fifth delta runs the other way — code that is live *here* and dead *there*.** **PINT (penal
interest) is not configured in production**, so `penalInterestAccrualCalculation` and
`penalInterestAccrualBooking` never run there despite sitting in the Autosys schedule. Their two
registry cases are deliberately left status-only: value-level asserts on a path that carries no
production money is effort spent in the wrong place. Presence in the schedule is not proof a job is
live. This is the same fact `.cursor/rules/40-knowledge-upkeep.mdc` § Precedent discipline already
states from the other direction — penal/LPP must not be mirrored as a precedent for a new flow.

**The rule that follows:** a local failure is a claim about this machine until the environment
delta is named and ruled out. The burden is on the reproduction, not on production. Two gaps were
filed and withdrawn today for skipping that step; three more turned out to be data and were fixed
by repairing rows rather than blaming code.

**What survives the calibration**, because the distinction is *the code is wrong* versus *the code
fails here*:

- **GAP-095** (MEDIUM) — `loanInstallmentDueNotificationJob`'s partitioner selects installments N
  days in the past while its reader searches N days ahead. Real code asymmetry, verified by reading
  both queries. A dense production population spans the id range and hides it; a sparse one does
  not. The kind of bug a low-volume tenant exposes years later.
- **GAP-093 / GAP-094** (LATENT) — a skip listener that turns one failed item into a failed job
  with no audit row, and a per-mandate dereference with no null guard. Both real, both dormant:
  the first only fires after an item has already failed, the second only on a row production does
  not carry.
- **GAP-097 / GAP-098** — phantom columns and the KG's Kafka-consumer blindspot. Neither is a
  runtime defect; both are accuracy problems in what the workspace *knows*.

**Withdrawn:** GAP-099 (zeroisation gate) and GAP-100 (zeroisation readback). Both were artefacts
of the 18:00 correlator and the stale business date.

## Read the counts in this document as observations, not contracts

The local Yugabyte is a long-lived dev fixture that accumulates state across aborted runs and
older builds. **It can be wrong, and several counts below almost certainly are.** They are
recorded because they are what a run actually produced, not because they are the product's
contract.

The distinction that matters, applied throughout:

- **A missing null guard is a code defect** whether or not the 72 null rows that triggered it are
  legitimate. GAP-094 stands on `PopulateEnachPresentationStepTasklet:90`, not on the row count.
- **3472 `CLOSED` loans carrying unpaid dues** is a fixture reading, so it was used as a reason
  *not* to ship an assert — never as evidence of a defect.
- **Zero candidates** for a job means this fixture cannot exercise it today. It does not mean the
  job is dead, and a case built on it would be measuring the fixture.

Standing rule: `40-knowledge-upkeep.md` § *Code is the source of truth; the local DB is not*.

## Coverage landed, and the harness defect that invalidated the earlier greens

**Every batch DB assert was measuring the previous run.** A batch trigger returns 200 the moment
the job is accepted; `db_eq` was evaluated right there, before `wait_batch` had confirmed
`COMPLETED`. The four money cases passed anyway because their jobs are idempotent and the state
left behind already satisfied the assert — which is exactly why the defect survived. DB and file
rules now defer until after the job completes, and all six batch cases were re-run green under the
corrected ordering.

| Job | Assert | Red before | Green after |
|---|---|---|---|
| `proactiveExcessAmountRefundStaging` | reader's own WHERE clause must drain | 4 unstaged | 4 staged, each 250.00 / OUTBOUND_SUCCESS |
| `proactiveExcessAmountRefund` | drain + every completed row has a reference number **and** a matching refund-details row | 4 readable | 3 refunded, 1 bank fail — both leave the reader's set |
| `trialBalanceCalculation` | non-empty, every date nets zero, each date reconciles against `transaction_details` | table empty | 266,135 rows over 2026-06-10..26 |
| `loanAccountAssetClassificationJob` | day-0 branch contract, taken verbatim from the repository query | **890 violating loans** | 0 |
| `loanAccountClosure` | liveness only — see below | — | read 2057 / write 2057 |

Three method points, each of which changed an answer:

- **`batch_wrote` does not belong on a drain job.** Both refund jobs exclude what they already
  processed, so a correct re-run writes nothing: `read=0 write=0` is health, not failure. It stays
  on jobs that work every run (dpd, accrual, billing, classification).
- **`loanAccountClosure` ships as a liveness check, and says so.** Two state asserts were tried and
  rejected rather than weakened. An eligibility assert cannot be trusted — the run closed **zero**
  of the 11 accounts that matched a tolerance-only reading of the rule, because
  `checkInterestAccrualAndBookingUptoDate` gates on accrual currency no SQL here reproduces. A
  safety assert (no `CLOSED` loan may carry unpaid dues) is violated by **3472 existing rows**, so
  shipping it would encode the fixture as a contract before establishing which side is wrong.
  Those 3472 rows are the open question, not the assert.
- **`loanAccountAssetClassificationJob`'s other branch is unassertable and that is a finding.**
  When `npa_ageing_start_date` is set, the service computes ageing against `new Date()`, not the
  `job_time` business date — so a BOD job's output depends on when it is run rather than the day it
  is run for. Only the day-0 branch is encoded.

## Where the 24 accounting jobs stand

**13 have a registry case added here**, plus `loanInstallmentDueNotificationJob` which already had one. Five carry a value-level `db_eq` proven red before the run that made
it green; four are liveness-only for a stated reason; two are red by design against an open gap;
three no-op correctly on this fixture.

| State | Jobs |
|---|---|
| **Value-level assert, red→green** | `interestAccrualCalculation`, `interestAccrualPosting`, `loanAccountBillingJob`, `loanAccountDpdCalcJob`, `loanAccountAssetClassificationJob`, `loanAccountAssetCriteriaJob`, `trialBalanceCalculation`, `proactiveExcessAmountRefundStaging`, `proactiveExcessAmountRefund`, `updateLoanAccountDerivedFieldsJob` |
| **Liveness only, reason recorded** | `loanAccountClosure`, `loanAdvanceRepayment`, `generateSIPresentationFiles` |
| **Red by design, open gap** | `generateEnachPresentationFile` + `generateNocFileJob` (GAP-094) |
| **Blocked, recipe needed** | `trialBalanceZeroisationJob` (needs an FY-start date + seed), `updateLoanAccountDerivedFieldsMonthlyJob` (needs a 1st-of-month date), `loanRecurringPaymentBatchApi` (writes nothing in accounting; persistence is downstream in payments) |
| **Structural no-op here** | `extractCasaBalanceFor180ProductCode`, `extractCasaBalanceFor182ProductCode` — both gate their entire DB write on an inbound CSV whose configured path does not exist on this machine |
| **No DB row to assert** | `loanInstallmentBounceNotificationJob` — Kafka only, and zero candidates besides |
| **Out of scope** | `penalInterestAccrualCalculation`, `penalInterestAccrualBooking` |
| **Reports** | `generatePostEODReports`, `generateTBZeroisationReport` — both no-op on this business date because `trial_balance_run_history` does not satisfy their gates; a `file_exists` case would fail forever for upstream reasons, not a bug |

### The pattern worth carrying forward

Two of the three defects found are the **same shape reached by different routes**: a per-item
problem escalating into a whole-job failure that writes nothing and records nothing.

- **GAP-093** — a writer-side item failure reaches a skip listener that cannot handle the async
  item, so the listener throws and takes the job with it. The audit table meant to name the failing
  accounts stays empty.
- **GAP-094** — an unguarded dereference sits inside the per-mandate loop with no per-item try, so
  one malformed row suppresses a bank-facing file for every well-formed mandate that day.

Both are worth fixing as a class rather than as incidents, which is why the blast radius was
measured (4 exposed mappers, all backing `force_async` jobs) rather than estimated.

**Third pattern, quieter and more dangerous:** `loanAdvanceRepayment` reported `COMPLETED` having
read and written its one candidate, and the money did not move — no CRR row, no audit row, no
error anywhere. A money job that reports success while doing nothing is worse than one that fails.

### One correction to this plan's own premise

`loanInstallmentDueNotificationJob` was listed as uncovered and a case was written for it. It was
already covered, under the id `batch.loan_installment_due_notification`. The duplicate has been
removed and its one useful finding folded into the existing case.

The "uncovered" list came from matching job names against case **ids**, not against each case's
`api` field, so any job whose case is named differently reads as uncovered. Three more of the
jobs covered here matched that way — but those three existing cases are `type: flow`,
`verify_mode: WORKSPACE_ONLY` KG-presence placeholders that assert nothing about behaviour, so the
new `type: batch` cases with value-level asserts are genuine upgrades rather than duplicates.
**Check the `api` field, not the id, before calling a job uncovered.**

### The adversarial audit of these cases found two defects in them

Nine cases were handed to an audit asked to prove them wrong — every citation re-read, every
`db_eq` re-run, every column resolved through `kg schema`. Two real defects came back:

- **`batch.loan_account_closure` was tagged `service` and drives a money write path.** The
  tolerance branch posts a real GL transaction: `LoanAccountClosureService:289` calls
  `postTransaction` over the internal API, reached from `:177` and from
  `LoanAccountAutoClosureItemWriter:128`. Retagged `money`.
- **A count in a `why` field did not reproduce.** It said the reader found 39 candidates against a
  run that read 0. The 39 was computed for business date 2026-06-27 while the run used 2026-08-07
  — two different days compared as one. The run's own persisted `batch_record_count` is **112**,
  and reconstructing the reader's clause for the right date gives 112 too. The job counted 112
  candidates for partitioning and then read none of them, which is a sharper open question than
  the wrong number described.

Also corrected: the day-0 branch was described as updating "unconditionally". It is guarded by
`calcAssetClassificationSlabId != null`. The assert was already right — its `CROSS JOIN LATERAL`
models the same condition — but the narrative overstated the code.

No phantom columns were found: every column across all nine `db_eq` blocks resolved through
`kg schema` to a real column of the right type on the right table. No assert was vacuous — every
scoped-to-today clause is backstopped by a live-state clause, and every scoped set was non-empty
when checked.

## Findings from the parallel audits

### The 56 reporting jobs are not testable today, and the reason is one missing primitive

They are file producers. `expect` supports `status`, `code`, `paths`, `path_eq`, `path_gt`,
`any_path_gt` and `db_eq` — every path rule reads the **HTTP response body**, and these jobs
return only `response_status`, no filename and no record count. Only 2 of the 56 write a DB row
worth asserting (`generateUAMPopulationExtractJob`, `generateUAMLoginLogoutExtractJob`, into
`scheduled_reports_audit_data`); `assetBaseFileSyncJob` is DB-only and the static map reports
`tables_written: []` for it, which is the same under-count the batch scan exists to fix.

**29 of the 56 are marked critical** in `Master-Sheet`, with SFTP deadlines — ten RBI ADF
extracts at 05:00, eight base-file jobs at 05:30, Posidex daily at 01:00. Until a
`file_exists` / `file_row_count` assert exists, "testing" these means "returned 2xx", which
says nothing about whether the file was produced, sized right, or landed before the deadline.
That primitive is the single highest-value harness addition for this block.

### Porting the batch scanner: one hardcoded path and one glob

Reader/writer/DAO/entity tracing, `callInternalAPI` arg-2 keying and `queryFromClause` parsing
all transfer unchanged. Two things do not: the repo root is hardcoded to accounting, and
**no other repo uses `batchnew/`** — they all use `batch/`. Worse, each service invented its own
config-class suffix, so a literal port of the `*BatchConfigService.java` glob silently drops
60% of LOS jobs, 40% of task, 26% of reporting, 3% of payments. Widen the glob per repo before
trusting a count from it.

### `postTransaction`'s own map entry over-claims `account_balance`

Every job that unions `postTransaction` through `callInternalAPI` inherits it. The processors
that would write `account_balance` — `populateAndValidateActorAccountBalanceProcessor` and
`validateAndUpdateInternalAccountBalanceProcessor` — are **commented out** in
`product_transaction_orc.xml:36-37`, the only place they are wired. This is upstream of the
overlay: the KG's `postTransaction` entry is stale, so correcting it in the overlay alone would
paper over it. Left as a finding rather than patched.
