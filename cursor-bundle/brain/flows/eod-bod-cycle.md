# Flow — EOD / BOD daily cycle

## Mental model

A single 24-hour cycle has two pivots:
- **BOD ~04:00 IST** — open the books, advance the clock, prep mandates
- **EOD ~21:00 IST** — bill, accrue, bucket, classify, snapshot, report

Both are aggregator Requests in accounting (`runBODJobs`, `runEODJobs`) scheduled by the batch service. Each fans out into per-step Requests sequentially.

## Services involved

- batch (scheduler)
- accounting (every step is a Request here)
- reporting (downstream of `generatePostEODReports`)
- DMS / ES (where reports land)

## BOD pipeline (mfi_orc.xml::runBODJobs)

```
runBODJobs (typically 04:00 IST)
  ├ server clock advance               (clock package — bumps business_date)
  ├ holiday roll-forward               (holiday package — apply today's calendar)
  ├ generateEnachPresentationFile       (build outbound presentation file for today's mandates)
  ├ expirePendingMandatesBatchJob       (mandate state transitions)
  └ reset day-level counters
```

## EOD pipeline (mfi_orc.xml::runEODJobs)

Sequential — each step is a separate Request fired in order:

```
runEODJobs (typically 21:00 IST)
  ├ loanAccountBillingJob               (build today's due records → loan_account_billing_details)
  ├ interestAccrualCalculation          (compute today's accrual per loan)
  ├ interestAccrualPosting              (post DR INT_RECEIVABLE / CR INT_INCOME)
  ├ penalInterestAccrualCalculation     (DPD × penal slabs)
  ├ penalInterestAccrualBooking
  ├ loanAccountDpdCalcJob               (refresh DPD)
  ├ loanAccountAssetCriteriaJob         (apply criteria slabs)
  ├ loanAccountAssetClassificationJob   (final NPA bucket)
  ├ updateLoanAccountDerivedFieldsJob   (denorm for reporting)
  ├ trialBalanceCalculation             (per-GL daily snapshot)
  ├ trialBalanceZeroisationJob          (closing → next-day open)
  ├ generateTBZeroisationReport
  ├ extractCasaBalanceFor180ProductCode + extractCasaBalanceFor182ProductCode
  └ generatePostEODReports              (kick reporting service)
```

`generatePostEODReports` cascades into the reporting service's many `generate*Job` Requests (RBI ADF extracts, MIS, Posidex extracts, performance metrics, etc. — see [`../services/trustt-platform-reporting.md`](../services/trustt-platform-reporting.md)).

## Why the order matters

- **Billing before accrual** — accrual reads today's billed dues.
- **Accrual before DPD** — DPD calc considers any newly-due interest.
- **DPD before asset criteria** — slab choice driven by DPD.
- **Asset criteria before classification** — classification needs slab.
- **All of above before derived fields refresh** — denorm reads finalised values.
- **All of above before trial balance** — TB snapshots final GL state for the day.
- **Zeroisation last** — closes the day, sets next-day opening.

## Spring Batch implementation pattern

Each step is a partitioned Spring Batch job (`GRID_SIZE=10` typical). `*BatchConfigService` extends `infra.batch.builder.CustomCommonStepBuilder` and wires `*ItemReader` (`SynchronizedItemStreamReader<Object[]>`), `*ItemProcessor`, `*ItemWriter`. Per-row failures go to `*FailureEntityMapper` → `batch_failure_audit`.

## SHG/JLG specifics

`childLoanEventProcessingBatchJob` runs **independently** of EOD (every few minutes). EOD itself doesn't drain the child queue — it operates on whatever children exist at run time.

If a parent disbursed today but children haven't been created yet (CLB still `'P'`), the parent will appear in EOD calculations but the children won't.

## Failure modes → runbook

See [`../runbooks/eod-failed.md`](../runbooks/eod-failed.md). Most common:

| Symptom | Likely cause |
|---|---|
| Today's `interest_accrual_details` empty | `runEODJobs` never fired (batch scheduler) or `interestAccrualCalculation` failed mid-batch |
| `loan_account_derived_fields.business_date` stale | `updateLoanAccountDerivedFieldsJob` skipped or failed |
| Trial balance imbalanced | A leg in some `postTransaction` call failed; see [`../runbooks/trial-balance-imbalance.md`](../runbooks/trial-balance-imbalance.md) |
| Reports missing in DMS | `generatePostEODReports` ran but reporting service failed; check report processor logs |

## Code anchors

- BOD Request: `mfi_orc.xml::runBODJobs`
- EOD Request: `mfi_orc.xml::runEODJobs`
- Each per-step Request: `loans_orc.xml` or `mfi_orc.xml` with matching name
- Spring Batch jobs: `batchnew/*` packages in accounting
- Schedule registry: `mfi_batch.batch_schedule`

## Where to dig deeper

- Batch service internals: [`../services/novopay-platform-batch.md`](../services/novopay-platform-batch.md)
- Per-job inventory: [`../system/07-batch-atlas.md`](../system/07-batch-atlas.md)
- Accounting batch dependency: [`../accounting/03-batch-dependency.md`](../accounting/03-batch-dependency.md)
- Money flow through EOD: [`../system/04-money-flow-rupee-journey.md`](../system/04-money-flow-rupee-journey.md) §"Stage 2"
