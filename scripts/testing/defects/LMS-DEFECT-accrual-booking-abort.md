# LMS-DEFECT — interestAccrualPosting batch abort vs online skip

**Class:** LMS-DEFECT (batch booking walk semantics)  
**Status:** code pushed; awaiting QA retest  
**Fix sha:** `af52abe3d` (+ L2 skip-count log follow-up, this formalize round) on `origin/mfi_integration_v3.4.2.4`  
**Verdict:** DEFECT — batch `return false` aborted account walk; online path already skipped.

## Symptom

`interestAccrualPosting` COMPLETED with `Booking processDtos is empty for account id …` while the account still had **unposted IAD rows whose `end_date` is ME or due**, because an earlier (by `start_date ASC`) **mid-month unposted** row stopped the walk.

## Shape table

| Shape | Mid-month unposted ahead of ME/due unposted? | Old batch (`return false`) | Online booking | After `af52abe3d` |
|-------|-----------------------------------------------|----------------------------|----------------|-------------------|
| Healthy one-tip (prod EOD) | No — single open tip `end_date=today` | Mid-month: empty DTOs (correct no-book). ME/due tip: books | skip mid-month, continue | same outcome |
| Poison / reopen dirt | **Yes** | Aborts before ME/due → **never books** | would still reach ME/due | **books ME/due**; mid-month still skipped |

## Code trace

Batch (bug + fix):

```104:172:trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/interest/interestaccrualbooking/InterestAccrualBookingBatchService.java
doNormalAccrualBooking — for each IAD (ORDER BY start_date ASC):
  processAccrualDetails:
    accrued==posted → continue
    !isAccrualPostingDate(end_date) → return true  // AFTER fix (was return false → abort walk)
    else add booking VO
isAccrualPostingDate: ME or due on end_date (not job_time)
```

Online counter-example (never aborted):

```115:129:trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/interest/interestaccrualbooking/InterestAccrualBookingService.java
for (entity : findAllByAccountId) {
  processAccrualDetails(...);  // mid-month → return; loop CONTINUES
}
```

Loader order: `InterestAccrualDetailsRepository.findAllByAccountId` — `ORDER BY start_date ASC`.

## Why prod looked fine

Normal `interestAccrualCalculation` **extends one open tip** until ME/due forces a new row. Steady-state: older rows fully posted; one unposted tip. Old abort then equals “nothing to book today.” Defect surfaces when IAD has **multiple unposted mid-month rows before ME/due** (harness reopen / dirt / catch-up population).

**Not** solely caused by SHG child Accrued distribute (`ffa882cdf`) — that is a separate child tip issue (see `LMS-DEFECT-child-iad-stuck-tip.md`).

## CATCH-UP semantics (intended post-deploy)

After deploy, on the **first** `interestAccrualPosting` EOD that visits an account:

- Mid-month-ended unposted rows remain **skipped** (no over-post).
- Any **stuck ME/due-ended unposted** rows that were previously unreachable behind mid-month aborts **will book** (recovery).

Sized below for QA/accounting sign-off.

## Deploy note — blast radius (READ-ONLY)

**QA3/QA envs:** user-declared **DOWN** this session → **UNKNOWN on QA**. Exact query for when QA is up:

```sql
-- Catch-up population: unposted ME/due IAD preceded by mid-month unposted (same account)
WITH dues AS (
  SELECT loan_account_id AS account_id, due_date::date AS d
  FROM mfi_accounting.loan_due_details WHERE COALESCE(is_deleted,false)=false
),
iad AS (
  SELECT i.account_id, i.id, i.start_date::date AS sd, i.end_date::date AS ed,
         COALESCE(i.total_accrued_amount,0) AS accrued,
         COALESCE(i.total_accrual_posted_amount,0) AS posted,
         (COALESCE(i.total_accrued_amount,0) > COALESCE(i.total_accrual_posted_amount,0)
          OR i.total_accrual_posted_amount IS NULL) AS unposted,
         (EXTRACT(day FROM i.end_date)::int =
            EXTRACT(day FROM (date_trunc('month', i.end_date) + interval '1 month - 1 day'))
          OR EXISTS (SELECT 1 FROM dues d WHERE d.account_id=i.account_id AND d.d=i.end_date::date)
         ) AS booking_end
  FROM mfi_accounting.interest_accrual_details i
),
catch AS (
  SELECT m.account_id, SUM(GREATEST(b.accrued - b.posted, 0)) AS catchup_amt
  FROM iad m
  JOIN iad b ON b.account_id=m.account_id AND b.unposted AND b.booking_end
            AND b.sd >= m.sd AND b.id <> m.id
  WHERE m.unposted AND NOT m.booking_end
  GROUP BY m.account_id
)
SELECT COUNT(*) AS n_accounts, ROUND(SUM(catchup_amt)::numeric,2) AS total_amt FROM catch;
-- samples: JOIN account/loan_account ORDER BY catchup_amt DESC LIMIT 5;
```

**Local portfolio (this session):**

| Scope | N accounts | Catch-up amt sum | Samples |
|-------|------------|------------------|---------|
| All statuses | **44** | **₹10,484.00** | `6000016025` 2672 CLOSED; `0000002713` 2221 CLOSED; `0000002721` 2072 CLOSED; `0000002522` 1037 CLOSED; `6000000121` 1022 CLOSED |
| ACTIVE/FORECLOSURE_FREEZE | **33** | **₹0.00** (shape match; material ME/due unposted amt 0 on this local DB) | `6001754925`, `6002505525`, `6003951125`, `6003896527`, `6000025344` |

Proof files: `scripts/scratch/bone/proofs/blast-local-*.txt`

## Retro FIX-PLAN

| Field | Content |
|-------|---------|
| root_cause | Batch `processAccrualDetails` treated non-booking-day unposted as walk abort (`return false`); online already skipped |
| flow_spine | `interestAccrualPosting` → `InterestAccrualBookingBatchProcessor` → `doNormalAccrualBooking` → `isAccrualPostingDate(end_date)` |
| minimal_option | `return true` on non-booking-day (align batch with online) |
| rejected | Harness-only Posted assert weaken; SQL wipe mid-month unposted before every posting |
| diff_budget | 1 file / ~30 lines (fix + L2 log) |
| reuse_check | Online `InterestAccrualBookingService` already skip-continue |


## Counter-proof paste (2026-07-31)

### a) stitch / batch / invariants
```
=== PASS: flowtest.shg_int_accrual_stitch ===
  PASS posting parent Posted 81071.000000 -> 81123.000000
✓ PASS   # batch.interest_accrual_posting
PASS: flowtest.invariants_universal gate lans=['6000137433', '6000137440']
```
Logs: `scripts/scratch/bone/proofs/cp-stitch.log`, `cp-batch-posting.log`, `cp-invariants.log`

### b) NO-OVERPOST
```
LAN=6000000264 tip=2025-04-17 mid-month=YES before_posted=1371.000000
batch_status=COMPLETED
after_posted=1371.000000
NO_OVERPOST=PASS tip_still_unposted_rows=1
```
Log: `scripts/scratch/bone/proofs/no-overpost-run.txt`

### L2 skip log (ops)
```
interestAccrualPosting account_id=216460 skipped_unposted_non_booking_day_iad=1 booked_vos=0
```
`scripts/scratch/bone/proofs/l2-skip-log.txt`

## Counter-proofs (pasted paths)

| Proof | Result | Path |
|-------|--------|------|
| a stitch GREEN | see `cp-stitch.log` | `scripts/scratch/bone/proofs/cp-stitch.log` |
| a batch.interest_accrual_posting GREEN | see `cp-batch-posting.log` | `scripts/scratch/bone/proofs/cp-batch-posting.log` |
| a invariants PASS | see `cp-invariants.log` | `scripts/scratch/bone/proofs/cp-invariants.log` |
| b NO-OVERPOST mid-month one-tip | **PASS** posted 1371→1371 tip still unposted | `scripts/scratch/bone/proofs/no-overpost-run.txt` LAN `6000000264` tip `2025-04-17` |
| c catch-up | documented above | local blast; QA UNKNOWN |

## L2 (ops)

Log-only when skipping unposted non-booking-day IAD:  
`interestAccrualPosting account_id={} skipped_unposted_non_booking_day_iad={} booked_vos={}`
