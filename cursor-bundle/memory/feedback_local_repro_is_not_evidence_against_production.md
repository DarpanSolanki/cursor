---
name: feedback_local_repro_is_not_evidence_against_production
description: "Production runs these jobs successfully, including year-end ones. A local reproduction that contradicts that is a claim about the harness until proven otherwise."
metadata:
  node_type: memory
  type: feedback
---

**The user has said this twice, and I filed a wrong gap between the two.** Production runs the
EOD/BOD jobs at ~99% with no business-logic failures, and the year-end jobs work too. Treat that
as evidence, not as background.

**The rule.** When a local run contradicts production, the burden is on the local run. Before
filing anything, name the difference between the two environments and show it is *not* the cause.
A local failure is a finding about the fixture until that is done.

## What it cost — GAP-099, filed and withdrawn the same day

I claimed `trialBalanceZeroisationJob` could never pass its own gate: `tb_last_run_date` is a
`DATE` (always midnight), `getLastDayOfPreviousFinancialYear` never clears `H:M:S`, so
`.before()` is true for any non-midnight run — and the cron is `0 0 18 * * ?`. I ran it both ways
and watched 18:00 write nothing and midnight post two balanced GL legs.

Every one of those facts is true. The conclusion was still wrong, because I conflated the
**trigger time** with the **business date parameter**:

```
platform business date (current.business.date)  2025-12-04 00:00:00 IST   <- what production passes
harness JOB_TIME correlator                     2026-06-27 18:00:00 IST   <- what I passed
```

The cron controls when the job is *triggered*. `job_time` is a separate parameter, and the
platform supplies the midnight-stamped business date. The gate passes in production by
construction.

**The 18:00 correlator exists because someone reasoned "18:00 IST matches the existing cron".**
That reasoning is the bug, and I inherited it without checking. I had already read
`current.business.date` twice that day for an unrelated reason and never compared the two values.

## Checks that would have caught it

- **Does the harness feed this job the same inputs production does?** For anything date-gated,
  compare `JOB_TIME` against `current.business.date` before concluding anything.
- **Would this defect be visible in production?** If the answer is "it would silently no-op", ask
  why nobody has noticed in the years it has been running. Usually because it does not happen.
- **Name the environment delta.** Stale Redis config, absent `/apps` mount, a fixture that
  accumulated across two years of aborted runs — all three produced "defects" today that were
  environment.

## What this does not mean

Do not swing to dismissing every local failure. Two real code weaknesses were found the same day
and survive this correction — a missing null guard, and a partitioner/reader predicate stated
twice in dialects that disagree. Both are **latent**: real code, no production impact, fix on next
touch. The distinction to hold is between *the code is wrong* and *the code fails here*.

## Pairs with

`.cursor/rules/40-knowledge-upkeep.mdc` § Code is the source of truth; the local DB is not ·
`feedback_batch_assert_timing_and_coverage_lookup.md`
