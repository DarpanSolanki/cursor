# LMS-DEFECT — interestAccrualPosting SkipListener ClassCastException

**Date:** 2026-07-30  
**Class:** LMS-DEFECT (platform-lib batch SkipListener) — not harness assert, not missing GL from happy path  
**Harness cases:** `batch.interest_accrual_posting` fail @ 13:19:25Z (exec 3829453) + 13:25:56Z (exec 3838653)

## Symptom
Standalone `ntest run batch.interest_accrual_posting` → HTTP 200/000 fire OK → job **FAILED** in ~18–21s.  
`flowtest.shg_int_accrual_stitch` same day still **COMPLETED** posting + `PASS posting parent Posted …` (fixture-quarantined path).

## Evidence
| Source | Detail |
|--------|--------|
| Telemetry | `ntest-telemetry.log` `13:19:25Z fail 19.27s`, `13:25:56Z fail 21.06s` |
| Ship log | `post-commit-ship-test.log` L328–336 FAILED exec=3838653; L338–342 `id is mandatory` is **nps_probe getEmployeeDetails** noise, not batch root |
| DB | `mfi_batch.batch_step_execution` step `interestAccrualPostingsStep1:partition*` status=FAILED |
| Root | `Caused by: java.lang.ClassCastException: class java.util.concurrent.FutureTask cannot be cast to class java.util.List` inside SkipListener path |
| Code | `trustt-platform-lib/.../GenericListenerV3.java:135-143` `onSkipInWrite(O item, …)` assumes writer item; partitioned async path can surface `FutureTask` |

Earlier same-day fail also showed `ERROR: value too long for type character varying(64)` (`post-commit-ship-test.log` L116) — separate poison/client_ref shape; **not** the 13:19/13:25 Caused-by.

## Repro
```bash
bash scripts/bin/ntest.sh run batch.interest_accrual_posting
# Then: SELECT step_name, status, left(exit_message,400) FROM mfi_batch.batch_step_execution
#        WHERE job_execution_id=<failed_exec> AND status='FAILED';
```

## Counter-evidence (not “posting never works”)
Stitch L294–306: `interestAccrualPosting COMPLETED` + Posted delta assert PASS on fixture LANs.

## Stop
No LMS/platform-lib code change in this triage round. Harness stays RED with this defect attached.
