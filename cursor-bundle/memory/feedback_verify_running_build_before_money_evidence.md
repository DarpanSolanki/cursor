---
name: feedback_verify_running_build_before_money_evidence
description: >-
  "probe OK — no restart" is not proof the running JVM contains HEAD. Verify the
  process start time against compiled classes before trusting any money-path
  evidence. 2026-08-03.
---

# Verify the running build before trusting money evidence (STANDING)

## Incident

A whole session of interest-accrual evidence — including a filed gap (GAP-082) —
was produced against an accounting JVM that did **not** contain the fix under test.

```
JVM started       15:52
git HEAD moved    16:01
classes compiled  16:02
ad399c5f2 commit  16:03   ← "fix(shg-int): child accrual rows must mirror parent
                             segments and own installment" — the fix being tested
```

`agent-ops before-test` printed `accounting: probe OK — no restart` and every run
proceeded. Three independent reproductions (including a `force_async=FALSE`
control) agreed with each other — because they all shared the same stale bytecode.
**Reproducibility across runs is not provenance.**

## Root cause of the bad provenance

`aops_java_newer_than_boot` compared `src/**/*.java` mtime against the service's
**boot log**. The running service appends to that log, so its mtime is always
~now and `find -newer` can never match. The staleness check was structurally
incapable of firing.

Fixed 2026-08-03: it now anchors on `/proc/<pid>` (process start time) and also
checks compiled classes newer than the JVM. New fail-closed gate:
`scripts/bin/assert-build-current.sh <service>`.

## Rule

Before citing any money-path DB evidence:

1. `bash scripts/bin/assert-build-current.sh accounting` must pass — it compares
   JVM start vs newest `.class`, newest `.java`, and HEAD commit time.
2. A green probe means "listening", never "running HEAD". Restart is the only way
   to guarantee bytecode identity after a checkout or build.
3. When the task is *verifying a specific commit*, name it and prove the running
   JVM contains it (`git log -1 --format=%ct <sha>` < JVM start time).
4. If provenance is broken, mark prior findings **UNVERIFIED** in the SoT rather
   than quietly re-running — the wrong claim may already have been read.

## Related fixture-hygiene hazards found the same session

- `quarantine_billing_portfolio` closes every other ACTIVE loan and restores from a
  backup table. An **interrupted** run never restores, and the next run will not
  re-back-up an already-CLOSED row — so the loan stays CLOSED permanently and later
  runs fail with `loan_status=CLOSED; accrual reader selects ACTIVE only`. Quarantine
  needs to be crash-safe (restore on entry if a stale backup exists).
- Canonical group payloads reuse fixed member external refs, so each local run adds a
  CLMT row with the same `filler_2`; `findOneByFiller2` is a single-result lookup and
  throws `IncorrectResultSizeDataAccessException` from the second run on. Cleanup:
  `scripts/sql/reset/local_dedupe_child_queue_rows.sql`, run **after** disbursement
  (the run itself creates the colliding row).

Pairs with [[feedback_fresh_loan_first_cycle_coverage]].
