# Death Foreclosure — Partial-Cycle Fix Simulation Pack

> Hand-simulation of the SDCP-9301 fix (`72ed389a3`) against **real QA4 loan data**.
> For each loan: real principal + real `interest_accrual_details` rows + a chosen
> death/reporting date → the **expected** force-bill / recover / waive amounts the
> fixed code should produce.
>
> Purpose: give QA pre-computed expected values to verify a real DFC run against,
> across different death→reporting gap shapes (1-day, multi-day, cross-cycle).
>
> **These are simulated expected values, not results of a real run.** They are
> derived from the fixed algorithm + QA4 ground truth. A DFC run on a build
> containing `72ed389a3` should reproduce them.

---

## How the simulation works

The fixed algorithm (`DeathForeclosureInsuranceWriter.java` lines 332-343):

```
forceBillSlice = calculateInterestTillDateUsingReducingBalanceForDeathForeclosure(reportingDate)
recovered      = preDeathBpi                       (= dcf_bpi_amount, interest up to death-1)
waived         = forceBillSlice - recovered
```

`calculateInterestTillDate...(date)` returns the interest accrued in the **current
installment cycle**, from the cycle start up to `date`. The EOD job already stored
exactly this, segmented at month-ends, in `interest_accrual_details`. So:

- **forceBillSlice** = Σ (current-cycle accrual rows) up to the reporting date.
- **preDeathBpi**    = Σ (current-cycle accrual rows) up to death − 1.
- For a date that falls inside a month-segment, that segment is prorated by day
  count on the **30/360** basis the engine uses.

The DFC posting then:
- `BLD_INT_AMT`  = `INT_AMT (pre-existing billed-unpaid int)` + `recovered`
- `BLD_INT_WAIVED_AMT` = `LOSSES_INT_WAIVED` + `waived`
- `UNBLD_PRIN_AMT` = `POS` (unbilled principal)
- DFC total `= UNBLD_PRIN_AMT + BLD_INT_AMT + ...` must equal `outstanding_loan_balance`.
- GL 13336 `BILLED_INTEREST` must net to zero: DR `forceBillSlice` (force-bill)
  = CR `recovered` + CR `waived`.

For all five loans below `INT_AMT` and `LOSSES_INT_WAIVED` are 0 (current cycle
unbilled, no overdue billed interest), so `BLD_INT_AMT = recovered` and
`BLD_INT_WAIVED_AMT = waived`.

---

## CASE A — LAN 6000010645 — multi-day gap, single cycle

Account_id 353360. Current cycle = installment #13, due **2026-11-05**, cycle
period **2026-10-05 → 2026-11-05**, principal **167731**, rate 24%.

`interest_accrual_details` for this cycle:

| Segment | Days | Accrued |
|---|---|---|
| 2026-10-05 → 2026-10-31 | 26 | 2907 |
| 2026-10-31 → 2026-11-05 | 5 | 448 |
| **Full cycle to 11-05** | 31 | **3355** |

Daily rate in the 2nd segment = `448 / 5 = 89.6`.

**Chosen scenario: death = 2026-11-02, reporting = 2026-11-05.**

- `preDeathBpi` = accrued up to death−1 (**2026-11-01**).
  = full 1st segment (2907) + segment-2 prorated 10-31→11-01 = 1 day = `1 × 89.6 = 89.6`
  → `2907 + 89.6 = 2996.6` → **2997** (rounded).
- `forceBillSlice` = accrued up to reporting (11-05) = `2907 + 448` = **3355**.
- `waived` = `forceBillSlice − recovered` = `3355 − 2997` = **358**.

| Posting | Amount |
|---|---|
| Force-bill `DFC_PRTL_BILL` (DR 13336 / CR 13578) | **3355** |
| DFC `BLD_INT_AMT` (DR 24511 / CR 13336) | **2997** |
| DFC `BLD_INT_WAIVED_AMT` (DR BILLED_INT_WAIVE / CR 13336) | **358** |
| GL 13336 check | DR 3355 = CR 2997 + CR 358 ✓ |

**Old (buggy) code would have produced:** force-bill `2997 + [3355−accrued(deathDate
11-02)]`. `accrued(11-02)` = `2907 + 2×89.6 = 3086`. partialCycleAccrual =
`3355 − 3086 = 269`. force-bill = `2997 + 269 = 3266` — **89 short** (the death-day
2nd-Nov interest). Fixed code: 3355. **Gap closed: 89.**

---

## CASE B — LAN 6001738126 — small loan, multi-day gap

Account_id 6781360. Current cycle = installment #13, due **2026-11-05**, cycle
period **2026-10-05 → 2026-11-05**, principal **9899**, rate 24%.

| Segment | Days | Accrued |
|---|---|---|
| 2026-10-05 → 2026-10-31 | 26 | 172 |
| 2026-10-31 → 2026-11-05 | 5 | 26 |
| **Full cycle to 11-05** | 31 | **198** |

2nd-segment daily = `26 / 5 = 5.2`.

**Chosen scenario: death = 2026-11-03, reporting = 2026-11-05.**

- `preDeathBpi` = accrued up to **2026-11-02** = `172 + (2 days × 5.2)` = `172 + 10.4`
  = `182.4` → **182**.
- `forceBillSlice` = accrued up to 11-05 = **198**.
- `waived` = `198 − 182` = **16**.

| Posting | Amount |
|---|---|
| Force-bill `DFC_PRTL_BILL` | **198** |
| DFC `BLD_INT_AMT` | **182** |
| DFC `BLD_INT_WAIVED_AMT` | **16** |
| GL 13336 check | DR 198 = CR 182 + CR 16 ✓ |

**Old code:** force-bill = `182 + [198 − accrued(11-03)]` = `182 + [198 − (172+15.6)]`
= `182 + 10` = `192` — **6 short**. Fixed: 198. **Gap closed: 6.**

---

## CASE C — LAN 6001736727 — death late in cycle, gap inside the cycle

Account_id 6780566. Current cycle = installment #12, due **2026-11-09**, cycle
period **2026-10-09 → 2026-11-09**, principal **17845**, rate 20%.

| Segment | Days | Accrued |
|---|---|---|
| 2026-10-09 → 2026-10-31 | 22 | 218 |
| 2026-10-31 → 2026-11-05 | 5 | 40 |
| **Full cycle to 11-05** | 27 | **258** |

2nd-segment daily = `40 / 5 = 8`.

**Chosen scenario: death = 2026-11-04, reporting = 2026-11-05.** (1-day gap — the
shape that *hid* the bug on the first reported case.)

- `preDeathBpi` = accrued up to **2026-11-03** = `218 + (3 days × 8)` = `218 + 24`
  = **242**.
- `forceBillSlice` = accrued up to 11-05 = **258**.
- `waived` = `258 − 242` = **16**.

| Posting | Amount |
|---|---|
| Force-bill `DFC_PRTL_BILL` | **258** |
| DFC `BLD_INT_AMT` | **242** |
| DFC `BLD_INT_WAIVED_AMT` | **16** |
| GL 13336 check | DR 258 = CR 242 + CR 16 ✓ |

**Old code:** force-bill = `242 + [258 − accrued(11-04)]` = `242 + [258 − (218+32)]`
= `242 + 8` = `250` — **8 short** (the 1-day death-day interest). Fixed: 258.
**Gap closed: 8.**

---

## CASE D — LAN 6000065103 — CROSS-CYCLE edge case

Account_id 1368365. The accrual rows show the installment changes **mid-period**:

| Segment | Installment | Days | Accrued |
|---|---|---|---|
| 2026-10-01 → 2026-10-31 | #20 (due 2026-11-02) | 30 | 1778 |
| 2026-10-31 → 2026-11-02 | #20 | 2 | 0 |
| 2026-11-02 → 2026-11-05 | #21 (due 2026-12-01) | 3 | 143 |

Installment #20's due date is **2026-11-02** — a new cycle (#21) starts then.

**Chosen scenario: death = 2026-10-30, reporting = 2026-11-05.** Death is in
cycle #20, but the job runs after #20's due date (11-02) — reporting falls in
cycle #21.

- The cycle containing the **reporting date** (11-05) is #21 (11-02 → 12-01).
  `calculateInterestTillDateUsingReducingBalanceForDeathForeclosure(11-05)` anchors
  to cycle #21 → returns the #21 accrual to 11-05 = **143**.
- `preDeathBpi` (`dcf_bpi_amount`, anchored at death−1 = 10-29) is from cycle #20.
  For cycle #20, accrued to 10-29 = prorate `1778 over 30 days × 28 days` ≈ **1660**.
- Raw `forceBillSlice` from the single call = **143**, but `preDeathBpi` = 1660.
  `143 < 1660` → the **`.max(preDeathBpi)` floor** in the fix kicks in:
  `forceBillSlice = max(143, 1660)` = **1660**.
- `recovered = preDeathBpi.min(forceBillSlice)` = `min(1660, 1660)` = **1660**.
- `waived = forceBillSlice − recovered` = `1660 − 1660` = **0**.

| Posting | Amount |
|---|---|
| Force-bill `DFC_PRTL_BILL` | **1660** |
| DFC `BLD_INT_AMT` | **1660** |
| DFC `BLD_INT_WAIVED_AMT` | **0** |
| GL 13336 check | DR 1660 = CR 1660 + CR 0 ✓ |

**What the floor guarantees:** in this cross-cycle case the fix does **not**
produce a negative `waived` and does **not** under-bill below `preDeathBpi`. It is
strictly safe and GL-balanced. (Limitation — see note at the end: in this rare
late-running cross-cycle case the post-death cycle-#21 tail is not separately
waived; this is acceptable for the hotfix and flagged as a known follow-up.)

---

## CASE E — LAN 6000164183 — CROSS-CYCLE, larger loan

Account_id 3075360. Same shape as Case D — installment changes at 11-02.

| Segment | Installment | Days | Accrued |
|---|---|---|---|
| 2026-10-02 → 2026-10-31 | #18 (due 2026-11-02) | 29 | 3223 |
| 2026-10-31 → 2026-11-02 | #18 | 2 | 112 |
| 2026-11-02 → 2026-11-05 | #19 (due 2026-12-02) | 3 | 288 |

**Chosen scenario: death = 2026-11-01, reporting = 2026-11-05.** Death in cycle
#18; reporting in cycle #19.

- `forceBillSlice` raw = `...ForDeathForeclosure(11-05)` anchored to cycle #19
  = **288**.
- `preDeathBpi` = `dcf_bpi_amount` at death−1 (10-31) = cycle #18 accrued to 10-31
  = **3223**.
- `288 < 3223` → floor: `forceBillSlice = max(288, 3223)` = **3223**.
- `recovered = min(3223, 3223)` = **3223**. `waived = 0`.

| Posting | Amount |
|---|---|
| Force-bill `DFC_PRTL_BILL` | **3223** |
| DFC `BLD_INT_AMT` | **3223** |
| DFC `BLD_INT_WAIVED_AMT` | **0** |
| GL 13336 check | DR 3223 = CR 3223 + CR 0 ✓ |

---

## Summary table

| Case | LAN | Scenario (death → reporting) | Force-bill | BLD_INT_AMT (recover) | BLD_INT_WAIVED | Old-code force-bill | Gap closed |
|---|---|---|---|---|---|---|---|
| A | 6000010645 | 11-02 → 11-05 (3-day) | 3355 | 2997 | 358 | 3266 | 89 |
| B | 6001738126 | 11-03 → 11-05 (2-day) | 198 | 182 | 16 | 192 | 6 |
| C | 6001736727 | 11-04 → 11-05 (1-day) | 258 | 242 | 16 | 250 | 8 |
| D | 6000065103 | 10-30 → 11-05 (cross-cycle) | 1660 | 1660 | 0 | (n/a) | floored, GL-safe |
| E | 6000164183 | 11-01 → 11-05 (cross-cycle) | 3223 | 3223 | 0 | (n/a) | floored, GL-safe |

Plus the two already-analysed real cases:

| — | 6007220926 | 11-03 → 11-04 (1-day) | 61 | 59 | 2 | (already correct by coincidence) | — |
| — | 6007569035 | 11-03 → 11-05 (2-day) | 389 | 347 | 42 | 375 | 14 |

In every case: **force-bill = recover + waive**, and **GL 13336 nets to zero**.
The "gap closed" column is the day-of-death interest the old code dropped.

---

## How QA should use this pack

1. Pick any loan from Cases A–E (all ACTIVE, standalone on QA4).
2. Trigger a death-foreclosure with the exact death date and reporting date in the
   "Scenario" column, on a build containing commit `72ed389a3`.
3. After the run, check:
   - `transaction_master` for the `BILLING/NORMAL_BILLING` row with CRN
     `DFC_PRTL_BILL_<loanAccountId>_*` → its `original_amount` must equal the
     **Force-bill** column.
   - The `DEATH_FORECLOSURE/DEFAULT` posting's `transaction_partition_details`:
     `BLD_INT_AMT` leg = **BLD_INT_AMT** column, `BLD_INT_WAIVED_AMT` leg =
     **BLD_INT_WAIVED** column.
   - Sum of `DR DUE_TO_FC_B` legs = `death_foreclosure_details.outstanding_loan_balance`.
   - GL 13336 `BILLED_INTEREST` for the loan nets to zero.

Note: the exact rupee values may shift by ±1-2 if the accrual on the actual run
date differs from the QA4 snapshot used here (interest keeps accruing daily). The
**invariants** are what must hold exactly: `force-bill = recover + waive`, DFC
total = `outstanding_loan_balance`, GL 13336 nets to zero.

---

## Known limitation (flagged, not a blocker)

Cases D and E show the **cross-cycle** behaviour: when the DFC job runs after the
next installment's due date, the single `calculateInterestTillDate...(reportingDate)`
call anchors to the *new* cycle. The `.max(preDeathBpi)` floor keeps the result
GL-correct (`force-bill = recover`, `waived = 0`, balance holds) but the new
cycle's small post-death tail is not separately waived. This is **strictly better
than the old code** (which dropped the death day in *every* case) and is safe for
the hotfix. Full cross-cycle precision would need a `prevDueDate`-equality check —
recommended as a separate follow-up ticket, together with the parent/group-loan
path gap.
