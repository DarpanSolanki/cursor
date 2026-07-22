# Death Foreclosure — Complete Feature Walkthrough

> **Canonical train (2026-07-10):** `mfi_integration_v3.7.1` — see runbook
> [`../../runbooks/sdcp-10199-group-parent-last-child-dfc.md`](../../runbooks/sdcp-10199-group-parent-last-child-dfc.md)
> and JIRA graph [`../../jira/JIRA-INDEX.md`](../../jira/JIRA-INDEX.md).
> This walkthrough’s file refs still cite historical `sdcp-9301-hotfix-3.3.1.0`
> (SDCP-9301 era); verify behaviour on **3.7.1** before shipping fixes.
>
> A narrated, end-to-end explanation of the death-foreclosure (DFC) flow — every
> transaction, every accounting rule, every non-money step — using **one real
> loan, LAN 6007220926 (QA4)**.
>
> Read it like a video voiceover. Every amount is traced to a code line and to a
> GL ledger entry. Historical file refs: `sdcp-9301-hotfix-3.3.1.0` (verify on 3.7.1).
>
> Structure:
> - **PART A** — the loan's life *before* death (disbursement → billings →
>   repayments → accruals → NPA movements).
> - **PART B** — the DFC job itself, every step, and all 20 accounting-rule legs.
> - **PART C** — the partial-cycle interest enhancement (SDCP-9301), in depth.
> - **PART D** — the full GL proof, the bug we fixed, and why it is generic.

---

## Cast — the one loan we follow

| Fact | Value |
|---|---|
| LAN | **6007220926** |
| `loan_account.account_id` | 9987161 |
| Loan amount / disbursed | 10041 / 9600 |
| Disbursement date | 2026-03-23 |
| Schedule | 12 monthly installments, due 5th of each month, 2026-05-05 → 2027-04-05 |
| **Date of death** | **2026-11-03** |
| **Date of reporting** | **2026-11-04** (the day the DFC job ran) |
| `death_foreclosure_details.id` | 25613 |
| `death_foreclosure_details.outstanding_loan_balance` | **5263** ← the number the insurer must pay |
| Loan status after job | CLOSED |

The borrower paid installments **#1–#6** in full, then died. At death, installment
**#7** (due 2026-11-05) was the live, *unbilled* cycle. The loan also crossed into
and out of NPA twice during its life — all of that is in PART A.

---

## SCENE 0 — Two words you must hold in your head: ACCRUED vs BILLED

Everything in this document depends on this distinction. They are different
events and hit **different GL accounts**.

- **ACCRUED interest** — interest the EOD job calculates **daily** and parks in
  `INTEREST_RECEIVABLE` (GL **13578**). Economically owed, not yet demanded.
- **BILLED interest** — when an installment's due date arrives, the billing job
  *bills* it: moves the amount `INTEREST_RECEIVABLE` → `BILLED_INTEREST`
  (GL **13336**). Now formally demanded from the customer.

A repayment can only settle **billed** dues. Accrued-but-unbilled interest must
be **billed first** before anything can clear it. Hold that thought — it is the
whole reason PART C exists.

The GL accounts you will see throughout:

| GL | Name | Role |
|---|---|---|
| 13334 | `LOAN_ACCOUNT` | Principal still on the loan (not yet billed) |
| 13335 | `BILLED_PRINCIPAL` | Principal that has been billed |
| 13336 | `BILLED_INTEREST` | Interest that has been billed |
| 13578 | `INTEREST_RECEIVABLE` | Interest accrued, awaiting billing |
| 47631 | `INT_INCOME` | Interest income (P&L) |
| 23479 | `INT_SUSPENSE` | NPA interest suspense |
| 23480 | `INT_SUSPENSE_AIR` | NPA accrued-interest-receivable suspense |
| 24511 / `DUE_TO_FC_B` | "Due To Foreclosure Bank" | Receivable from the insurer |
| 26663 | `DISB_SUSPENSE` | Disbursement suspense |
| `BILLED_INT_WAIVE` | Billed-interest waiver | Where waived interest is written off |

---

# PART A — The loan's life before death

Before the DFC job ever runs, this loan already had **31 transactions** posted
over 8 months. The DFC job adds the 32nd, 33rd, 34th. To understand the
foreclosure you must understand the state it inherited.

## SCENE A1 — Disbursement (txn 1411485, 2026-03-23)

`LOAN_DISBURSEMENT / CASA`. The loan amount 10041 is disbursed, but the customer
only receives 9600 — the difference (441) is insurance + fees + stamp duty held
back. The interesting legs:

```
  DR LOAN_ACCOUNT      13334   10041   <- principal goes onto the loan
  CR DISB_SUSPENSE     26663   10041
  DR DISB_SUSPENSE     26663      41   } insurance premium
  CR INSURANCE_PAYABLE 25009      41   }
  DR INSURANCE_PAYABLE 25009      41   } insurance routed to FC bank
  CR DUE_TO_FC_B       24511      41   }
  DR DISB_SUSPENSE     26663     123   processing fee
  ... PROC_FEE_GST / SGST / CGST / STAMP_DUTY ...
  DR DISB_SUSPENSE     26663    9600   } net amount actually paid out
  CR DUE_TO_FC_B       24511    9600   }
```

Take-away: from day one, `DUE_TO_FC_B` (24511) is the account that money flows
through to/from the insurance partner. The DFC posting in PART B will use the
**same** account to claim the death benefit.

## SCENE A2 — Daily accrual (txn 1413585 and many more)

Every EOD, `interestAccrualCalculation` runs. Example, the first accrual
(2026-03-23 → 2026-03-31):

```
  DR INTEREST_RECEIVABLE 13578   33   <- interest accrued
  CR INT_INCOME          47631   33
```

Interest is **earned** (accrued) here, not billed. Over the loan's life there are
~15 accrual rows; the relevant ones for cycle #7 are:

| Accrual row | Period | Accrued |
|---|---|---|
| id 241784 | 2026-10-05 → 2026-10-31 | 56 |
| id 241785 | 2026-10-31 → 2026-11-04 | 7 |

So **63** accrued for cycle #7 by the reporting date — but the cycle's due date
(2026-11-05) had not arrived, so **none was billed**. That unbilled stub is the
subject of PART C.

## SCENE A3 — Billing (txn 1426933 and 5 more)

When installment #1's due date (2026-05-05) arrives, `loanAccountBillingJob`
bills it:

```
  DR BILLED_INTEREST   13336   176   <- interest moves receivable -> billed
  CR INTEREST_RECEIVABLE 13578 176
  DR BILLED_PRINCIPAL  13335   781   <- principal moves loan_account -> billed
  CR LOAN_ACCOUNT      13334   781
```

Six cycles were billed (#1–#6). Total billed over the six: **principal 4837,
interest 655**.

| Installment | Due date | Principal billed | Interest billed |
|---|---|---|---|
| #1 | 2026-05-05 | 781 | 176 |
| #2 | 2026-06-05 | 791 | 116 |
| #3 | 2026-07-06 | 801 | 106 |
| #4 | 2026-08-05 | 811 | 96 |
| #5 | 2026-09-05 | 821 | 86 |
| #6 | 2026-10-05 | 832 | 75 |
| **Total** | | **4837** | **655** |

## SCENE A4 — Repayments (txn 1458484 and 1483084)

Two `LOAN_REPAYMENT / CASH` transactions cleared the billed dues. They settle
billed buckets and route the cash through `DUE_TO_FC_B`:

```
Repayment 1 (5492):
  DR DUE_TO_FC_B 24511 3898  / CR BILLED_PRINCIPAL 13335 3898
  DR DUE_TO_FC_B 24511  494  / CR BILLED_INTEREST  13336  494
  DR DUE_TO_FC_B 24511  800  / CR PENAL            2208   800
  DR DUE_TO_FC_B 24511  300  / CR CBC_CHARGE  434763500  300
Repayment 2 (1500):
  DR DUE_TO_FC_B 24511  939  / CR BILLED_PRINCIPAL 13335  939
  DR DUE_TO_FC_B 24511  161  / CR BILLED_INTEREST  13336  161
  DR DUE_TO_FC_B 24511  400  / CR PENAL            2208   400
```

Billed principal cleared: 3898 + 939 = **4837** (all of it).
Billed interest cleared: 494 + 161 = **655** (all of it).

So as of just before death, the customer owed **nothing on billed buckets** —
installments #1–#6 are fully paid. What remains is the **future, unbilled**
principal of #7–#12, plus the interest stub on cycle #7.

## SCENE A5 — NPA in and out (txn 1437046, 1440265, 1449517, 1450781)

The loan went overdue, was tagged NPA, recovered, went NPA again, recovered
again. Each crossing produces an `INT_INCOME`-type movement that shifts interest
between income and suspense accounts:

```
REGULAR_TO_NPA / INT_INCOME (txn 1449517):
  DR INT_INCOME 47631 655  / CR INT_SUSPENSE     23479 655   <- income reversed into suspense
  DR INT_INCOME 47631  56  / CR INT_SUSPENSE_AIR 23480  56
NPA_TO_REGULAR / INT_INCOME (txn 1450781):
  DR INT_SUSPENSE     23479 176  / CR INT_INCOME 47631 176   <- suspense released back to income
  DR INT_SUSPENSE_AIR 23480 535  / CR INT_INCOME 47631 535
```

You do **not** need to follow the NPA arithmetic to understand the DFC. The key
point: the DFC job, right after its main posting, **re-runs DPD / asset
classification** (PART B Scene B9) — which fires one final `REGULAR_TO_NPA` /
`NPA_TO_REGULAR` pair so the suspense accounts are correct at closure.

## SCENE A6 — State at the moment of death (2026-11-03)

| Bucket | Amount | Status |
|---|---|---|
| Billed principal (#1–#6) | 4837 | fully paid |
| Billed interest (#1–#6) | 655 | fully paid |
| **Unbilled principal (#7–#12)** | **5204** | live — never billed |
| **Cycle-7 interest accrued, unbilled** | **~63** | accrued, never billed |
| Penal / fee | 0 | paid / waived |

The DFC job must now settle the **5204 unbilled principal** and the **cycle-7
interest stub**, close the loan, and claim it all from the insurer.

---

# PART B — The DFC job, step by step

Entry point: `DeathForeclosureInsuranceWriter.writeDeathForeclosure(...)`
(`DeathForeclosureInsuranceWriter.java`, method starts ~line 290). It runs inside
a Spring Batch writer, triggered after a business user approves the DFC task.

The ordered steps (line numbers on `sdcp-9301-hotfix-3.3.1.0`):

```
 B1  line 301  syncBillingTillDate                  bill anything billable up to DOR
 B2  line 303  fetchOutStandingLoanBalanceAsPerDate  compute outstanding_loan_balance (5263)
 B3  line 333  calculateLossInterestWaived           which billed interest gets waived
 B4  line 336  computeUnbilledPartialCycleAccrual    the post-death accrual stub
 B5  line 338  forceBillSlice = preDeathBpi + partialCycleAccrual
     line 340  store dcf_recovered_partial_cycle / dcf_waived_partial_cycle   <-- SDCP-9301
     line 346  BPI_AMOUNT = "0"
 B6  line 391+ populateAdditionalAmountDetails       map each amount -> reference_code
 B7  line 433  calculateTotalTransactionAmount       sum the DFC posting amount
 B8  line 472  checkLoanAccountInterestAccrualBookingProcessor   book daily accrual
     line 477  forceBillPartialCycleInterest         bill the stub (separate BILLING txn)
 B9  line 493+ postTransaction "DEATH_FORECLOSURE"   the main DFC GL posting
 B10 line 525+ DPD / asset criteria / asset classification
 B11 line 533+ loan_status -> CLOSED
 B12 line 544+ DFC status APPROVED, insurance staging APPROVED
 B13 line 552+ loan_account_closure_details audit row
 B14 line 565+ push closure to LOS; mark insurance CLAIMED
 B15 line 582+ child loan status; doParentPartPrePayment (group loans only)
 B16 line 588+ cancel collections; GL-CBS integration; deleteTask
```

Steps **B8** and **B9** move money. Everything else prepares numbers or updates
state. We walk each.

## SCENE B1 — `syncBillingTillDate` (line 301)

Before computing anything, the writer makes sure billing is caught up to the
reporting date. If an installment's due date had passed but the billing job had
not yet run, this bills it now. For LAN 6007220926 cycles #1–#6 were already
billed, and #7's due date (11-05) is still in the future — so this is a no-op
here. (It matters for loans where death lands after a missed billing run.)

## SCENE B2 — Building the 5263: `fetchOutStandingLoanBalanceAsPerDate` (line 303)

File: `loan/deathforeclosure/service/GetAmountDetailsForDeathForeclosureService.java`,
method `fetchOutStandingLoanBalanceAsPerDate` (~line 89). It sums, in order:

```java
outStandingLoanBalance = outStandingLoanBalance.add(totalOverDueAmount);  // billed-but-unpaid
outStandingLoanBalance = outStandingLoanBalance.add(netPosAmount);        // future principal (POS)
outStandingLoanBalance = outStandingLoanBalance.add(bpiAmount);           // pre-death interest stub
outStandingLoanBalance = outStandingLoanBalance.add(currentLPP);          // penal
outStandingLoanBalance = outStandingLoanBalance.add(feeDueAmount);        // fees
outStandingLoanBalance = outStandingLoanBalance.add(accruedAmount);       // accrued penal
...
roundedOutStandingLoanBalance = RoundingUtil.roundAmount(outStandingLoanBalance, HALF_UP, 0);
executionContext.put("dcf_outstanding_loan_balance", roundedOutStandingLoanBalance);
```

For LAN 6007220926 only two terms are non-zero:

| Component | EC key | Value | Meaning |
|---|---|---|---|
| `netPosAmount` | `dcf_pos_amount` | **5204** | Unbilled future principal (#7–#12) |
| `bpiAmount` | `dcf_bpi_amount` | **~59** | Pre-death interest stub, up to **death−1 = 2026-11-02** |

`5204 + 59` → rounded → **5263** = `outstanding_loan_balance`.

The **5204** is literally the principal balance — it equals the `base_amount` of
the cycle-7 EOD accrual row. The **~59** is computed by
`interestCalculationUtil.calculateInterestTillDateUsingReducingBalanceForDeathForeclosure(...)`
called with `deathDateMinusOne` (2026-11-02), and it is *rounded*
(`InterestCalculationUtil.java:454`). For this loan it rounds to **59**.

> The business rule "bill up to 2nd Nov" is not a constant — 2nd Nov is
> `death − 1`, and this method *is* "interest up to 2nd Nov."

## SCENE B3 — `calculateLossInterestWaived` (line 333)

`DeathForeclosureInsuranceWriter.java:660`. This scans billed interest due rows
between death date and reporting date and decides how much is **waived**. For
LAN 6007220926 the cycle-7 interest due row has due_date 2026-11-05 — *after* the
reporting date 11-04, so it is outside the scan window → nothing found →
`LOSSES_INT_WAIVED` = 0. (For loans with overdue billed interest at death, this
is where it gets waived.)

## SCENE B4–B5 — The interest stub, split into recover vs waive (lines 336–346)

This is the SDCP-9301 enhancement. The *same stub of interest* is computed three
ways over three windows:

| # | Name | Window | Value | Used for |
|---|---|---|---|---|
| 1 | `dcf_bpi_amount` (`preDeathBpi`) | up to **death−1** (11-02) | **59** | inside `outstanding_loan_balance` |
| 2 | `partialCycleAccrual` | **death → reporting** (11-03 → 11-04) | **2** | accrual after death |
| 3 | `forceBillSlice` = #1 + #2 | up to reporting date | **61** | what we force-bill |

`partialCycleAccrual` comes from `computeUnbilledPartialCycleAccrual`
(`DeathForeclosureInsuranceWriter.java:1147`):

```java
private BigDecimal computeUnbilledPartialCycleAccrual(LoanAccountEntity loanAccountEntity,
        Date deathDate, Date asOfDate) throws NovopayFatalException {
    Date lastBilledInstallmentDate = loanInstallmentDetailsDAOService.getLoanInstallmentFromDate(
            loanAccountEntity.getId(), asOfDate);
    Date sliceStart = (lastBilledInstallmentDate != null && lastBilledInstallmentDate.after(deathDate))
            ? lastBilledInstallmentDate : deathDate;
    if (!sliceStart.before(asOfDate)) { return BigDecimal.ZERO; }
    ...
    BigDecimal accruedTillAsOf       = ...calculateInterestTillDateUsingReducingBalance(..., asOfDate, ...);
    BigDecimal accruedTillSliceStart = ...calculateInterestTillDateUsingReducingBalance(..., sliceStart, ...);
    return accruedTillAsOf.subtract(accruedTillSliceStart).max(BigDecimal.ZERO);
}
```

It is `accrued(reporting) − accrued(death)` — interest that accrued **after the
borrower died** but before the job ran. For this LAN, **2**.

And the split, `DeathForeclosureInsuranceWriter.java:336-341`:

```java
BigDecimal partialCycleAccrual = computeUnbilledPartialCycleAccrual(loanAccountEntity, dateofDeath, dateOfReporting);
BigDecimal preDeathBpi = bpiAmount != null ? bpiAmount : BigDecimal.ZERO;
BigDecimal forceBillSlice = preDeathBpi.add(partialCycleAccrual);
executionContext.put("dcf_partial_cycle_accrual", forceBillSlice.toPlainString());
executionContext.put("dcf_recovered_partial_cycle", preDeathBpi.toPlainString());        // 59 -> recover
executionContext.put("dcf_waived_partial_cycle", partialCycleAccrual.toPlainString());   // 2  -> waive
```

The rule: **bill up to death−1 and recover that from the insurer; the interest
that accrued *after* death is waived** — the borrower was already dead, so the
lender writes it off rather than claiming it.

Line 346 — `executionContext.put(BPI_AMOUNT, "0")` — zeroes the legacy channel
that used to carry the stub, so it cannot be double-counted. The stub now travels
only through `dcf_recovered_partial_cycle` / `dcf_waived_partial_cycle`.

## SCENE B6 — Mapping amounts to `reference_code`: the 20-leg rule catalogue (line 391+)

The writer maps each amount to a **`reference_code`** that the
`DEATH_FORECLOSURE / DEFAULT` accounting ruleset understands. The ruleset has
**20 legs**. Here is the complete catalogue, and for each: what fires for
LAN 6007220926.

| seq | reference_code | DR account | CR account | Purpose | LAN 6007220926 |
|---|---|---|---|---|---|
| 1 | `ADV_BLD_INT_AMT` | EXCESS_ACCT | BILLED_INTEREST | Settle billed interest from customer advance/excess | 0 — no excess |
| 2 | `ADV_UNBLD_PRIN_AMT` | EXCESS_ACCT | LOAN_ACCOUNT | Settle unbilled principal from excess | 0 |
| 3 | `ADV_PINT_AMT` | EXCESS_ACCT | PENAL | Settle penal from excess | 0 |
| 4 | `ADV_CBC_FEE_AMT` | EXCESS_ACCT | CBC_CHARGE | Settle fee from excess | 0 |
| **5** | **`BLD_INT_AMT`** | **DUE_TO_FC_B** | **BILLED_INTEREST** | **Recover billed interest from insurer** | **59** ✓ |
| 6 | `BLD_PRIN_AMT` | DUE_TO_FC_B | BILLED_PRINCIPAL | Recover billed principal from insurer | 0 — all billed prin paid |
| **7** | **`UNBLD_PRIN_AMT`** | **DUE_TO_FC_B** | **LOAN_ACCOUNT** | **Recover unbilled principal from insurer** | **5204** ✓ |
| 8 | `PINT_AMT` | DUE_TO_FC_B | PENAL | Recover penal from insurer | 0 |
| 9 | `CBC_FEE_AMT` | DUE_TO_FC_B | CBC_CHARGE | Recover fee from insurer | 0 |
| 10 | `ROUND_UP_AMT` | DUE_TO_FC_B | ROUND_OFF | Rounding adjustment (up) | 0 |
| 11 | `EXCESS_INCOME_INT_AMT` | INT_INC | EXCESS_ACCT | Reverse extra interest income | 0 |
| 12 | `EXCESS_ACCOUNT_INC_AMT` | EXCESS_ACCT | LOAN_ACCOUNT | Apply excess to loan | 0 |
| **13** | **`BLD_INT_WAIVED_AMT`** | **BILLED_INT_WAIVE** | **BILLED_INTEREST** | **Waive billed interest (lender absorbs)** | **2** ✓ |
| 14 | `STD_BLD_PRIN_WAIVED_AMT` | PRIN_WAIVE_STD | BILLED_PRINCIPAL | Waive billed principal (standard asset) | 0 |
| 15 | `NPA_BLD_PRIN_WAIVED_AMT` | PRIN_WAIVE_NPA | BILLED_PRINCIPAL | Waive billed principal (NPA asset) | 0 |
| 16 | `STD_UNBLD_PRIN_WAIVED_AMT` | PRIN_WAIVE_STD | LOAN_ACCOUNT | Waive unbilled principal (standard) | 0 |
| 17 | `NPA_UNBLD_PRIN_WAIVED_AMT` | PRIN_WAIVE_NPA | LOAN_ACCOUNT | Waive unbilled principal (NPA) | 0 |
| 18 | `PINT_AMT_WAIVED` | LOSSES_LPP_WAIVED | PENAL | Waive penal | 0 |
| 19 | `CBC_FEE_AMT_WAIVED` | FEE_WAIVED | CBC_CHARGE | Waive fee | 0 |
| 20 | `ROUND_DOWN_AMT` | ROUND_OFF | DUE_TO_FC_B | Rounding adjustment (down) | 0 |

Reading the catalogue:
- **seq 1–4** (`ADV_*`) fire only when the customer had **excess/advance money**
  on the loan. Then the foreclosure settles dues from that excess before touching
  the insurer.
- **seq 5–9** are the **recovery legs** — every one debits `DUE_TO_FC_B` (claim
  from insurer) and credits the bucket being cleared.
- **seq 10 / 20** are **rounding** legs against `ROUND_OFF`.
- **seq 11–12** handle extra interest income / excess application.
- **seq 13–19** are the **waiver legs** — the lender absorbs the loss; each debits
  a `*_WAIVE` loss account.

For this loan only **seq 5, 7, 13** carry money — the rest evaluate to 0 because
there is no excess, no unpaid billed principal, no penal/fee, and no principal
waiver. The ruleset is a superset; a given foreclosure lights up only the legs
its numbers require.

### The two NEW amount mappings (SDCP-9301)

**`BLD_INT_AMT`** — recovers the pre-death stub.
`DeathForeclosureInsuranceWriter.java:403-406`:

```java
BigDecimal billedInterestForRecovery = new BigDecimal(executionContext.getValue(INT_AMT, String.class))
        .add(LoanUtil.getBigDecimalValue(executionContext, "dcf_recovered_partial_cycle"));   // + 59
fetchTransactionalAndNonTransactionalChargesService.populateAdditionalAmountDetails(executionContext,
        "BLD_INT_AMT", billedInterestForRecovery.toPlainString());
```

`INT_AMT` (any pre-existing billed-unpaid interest) is 0 → `BLD_INT_AMT` = **59**.

**`BLD_INT_WAIVED_AMT`** — waives the post-death stub.
`DeathForeclosureInsuranceWriter.java:416-419`:

```java
BigDecimal billedInterestWaived = new BigDecimal(executionContext.getValue(LOSSES_INT_WAIVED, String.class))
        .add(LoanUtil.getBigDecimalValue(executionContext, "dcf_waived_partial_cycle"));      // + 2
fetchTransactionalAndNonTransactionalChargesService.populateAdditionalAmountDetails(executionContext,
        "BLD_INT_WAIVED_AMT", billedInterestWaived.toPlainString());
```

`LOSSES_INT_WAIVED` is 0 → `BLD_INT_WAIVED_AMT` = **2**.

**`UNBLD_PRIN_AMT`** — unchanged (`DeathForeclosureInsuranceWriter.java:409-410`):
fed from `POS` = **5204**.

## SCENE B7 — The DFC posting amount: `calculateTotalTransactionAmount` (line 433)

`DeathForeclosureInsuranceWriter.java:748-761`:

```java
private void calculateTotalTransactionAmount(ExecutionContext executionContext) {
    BigDecimal amount = new BigDecimal(0);
    amount = amount.add(new BigDecimal(executionContext.getValue(PRIN_AMT, String.class)));
    amount = amount.add(new BigDecimal(executionContext.getValue(INT_AMT, String.class)));
    amount = amount.add(new BigDecimal(executionContext.getValue(BPI_AMOUNT, String.class)));        // 0 (zeroed)
    amount = amount.add(new BigDecimal(executionContext.getValue(PENAL_AMT, String.class)));
    amount = amount.add(new BigDecimal(executionContext.getValue(FEE_AMT, String.class)));
    amount = amount.add(new BigDecimal(executionContext.getValue(POS, String.class)));               // 5204
    amount = amount.add(new BigDecimal(executionContext.getValue(BILLED_PRIN_AMT, String.class)));
    amount = amount.add(LoanUtil.getBigDecimalValue(executionContext, "dcf_recovered_partial_cycle")); // + 59 (NEW)
    roundedAmount = RoundingUtil.roundAmount(amount, RoundingMode.HALF_UP.name(), 0);
    executionContext.put(TRANSACTION_AMOUNT, String.valueOf(roundedAmount));
}
```

It adds **only the recovered 59**, not the waived 2 — because `TRANSACTION_AMOUNT`
is the amount **recovered from the insurer**, and waived money is recovered from
no one. Result: `5204 + 59 = 5263` = `outstanding_loan_balance`. ✓

## SCENE B8 — Booking the accrual + force-billing the stub (lines 472–477)

`checkLoanAccountInterestAccrualBookingProcessor` (line 472) books the daily
accrual so the receivable is current. Then `forceBillPartialCycleInterest`
(line 477, method at `DeathForeclosureInsuranceWriter.java:1166`) bills the stub:

```java
BigDecimal partialCycleAccrualToBill = LoanUtil.getBigDecimalValue(executionContext, "dcf_partial_cycle_accrual");
if (partialCycleAccrualToBill.compareTo(BigDecimal.ZERO) > 0) {
    forceBillPartialCycleInterest(executionContext, loanAccountEntity, partialCycleAccrualToBill, dateOfReporting);
}
```

It posts a `BILLING / NORMAL_BILLING` transaction for the **full 61**, with a
recognizable CRN `DFC_PRTL_BILL_<loanId>_<ts>`. GL effect (txn 1515285):

```
  DR BILLED_INTEREST     13336   61
  CR INTEREST_RECEIVABLE 13578   61
```

Why this is needed: `outstanding_loan_balance` includes the stub, but the stub
was **accrued, not billed** (Scene 0). A foreclosure recovers against billed
buckets. Force-billing moves the stub into `BILLED_INTEREST` so the DFC posting's
`BLD_INT_AMT` / `BLD_INT_WAIVED_AMT` legs can clear it.

## SCENE B9 — The main DFC posting (line 493+)

`DeathForeclosureInsuranceWriter.java:493`:

```java
executionContext.put("amount", executionContext.getValue(TRANSACTION_AMOUNT, String.class));   // 5263
...
novopayInternalAPIClient.callInternalAPI(executionContext, "postTransaction", "v1", POST_TRANSACTION_RESPONSE, ...);
```

This is the `DEATH_FORECLOSURE / DEFAULT` posting (txn 1515286). It fires legs
5, 7, 13:

```
  seq 7  UNBLD_PRIN_AMT       DR DUE_TO_FC_B   CR LOAN_ACCOUNT (13334)       5204
  seq 5  BLD_INT_AMT          DR DUE_TO_FC_B   CR BILLED_INTEREST (13336)      59
  seq 13 BLD_INT_WAIVED_AMT   DR BILLED_INT_WAIVE   CR BILLED_INTEREST (13336)  2
  --------------------------------------------------------------------------
  Total claimed from insurer (DR DUE_TO_FC_B): 5204 + 59 = 5263
```

## SCENE B10 — DPD / asset reclassification (line 525+)

After the posting, the writer re-runs `loanAccountDpdCalcProcessor`,
`loanAccountAssetCriteriaProcessor`, `loanAccountAssetClassificationProcessor`.
This produces the closing `REGULAR_TO_NPA` / `NPA_TO_REGULAR` pair (seen as
txn 1449517 / 1450781 in PART A Scene A5) so the NPA suspense accounts are
correct at the moment of closure.

## SCENE B11 — Close the loan (line 533+)

```java
executionContext.put("loan_status", "CLOSED");
executionContext.put("account_status", "CLOSED");
updateLoanAccountStatusProcessor.execute(executionContext);
```

`loan_account.loan_status` → **CLOSED**.

## SCENE B12 — Mark DFC + insurance staging APPROVED (line 544+)

```java
deathForeclosureDetailsEntity.setDeathForeclosureStatus(STATUS.APPROVED);
deathForeclosureDetailsEntity.setTaskStatus(TASK_STATUS.APPROVED);
deathForeclosureInsuranceStagingDetailsEntity.setClaimStatus("APPROVED");
```

The insurance-staging row is what later drives the **claim handoff file** to the
insurance partner (FTR/FTNR return-file processing happens in a separate flow).

## SCENE B13 — Closure audit row (line 552+)

`DeathForeclosureInsuranceWriter.java:553-563`:

```java
LoanAccountClosureDetailsEntity loanAccountClosureDetailsEntity = new LoanAccountClosureDetailsEntity();
loanAccountClosureDetailsEntity.setIdentifierType(Identifier.DEATH_FORECLOSURE);
loanAccountClosureDetailsEntity.setTransactionReferenceNumber((String) postTransactionResponse.get("transaction_reference_number"));
loanAccountClosureDetailsEntity.setPaidByCustomer(
        new BigDecimal(executionContext.getValue("transaction_amount", String.class)));   // 5263
loanAccountClosureDetailsEntity.setPaidByInsuranceCompany(deathForeclosureDetailsEntity.getOutstandingLoanBalance()); // 5263
```

This audit row is the **proof of correctness**: `paid_by_customer`
(= `TRANSACTION_AMOUNT`) and `paid_by_insurance_company`
(= `outstanding_loan_balance`) must be **equal**. Before the SDCP-9301 fix they
were 5204 vs 5263 — the mismatch that started this whole investigation. After the
fix they are both **5263**.

## SCENE B14 — Push to LOS, mark insurance CLAIMED (line 565+)

`pushLoanAccountClosureDetailsProcessor` syncs the closure to the LOS system.
Then every `LIFE_INSUR` insurance row on the loan is set to status **CLAIMED**
with the balance claim amount.

## SCENE B15 — Child loan / parent path (line 582+)

`doParentPartPrePayment` handles **group loans** (SHG/JLG): if this loan is a
child, the parent loan gets a `RSCH_DEATH_FORECLOSURE` reschedule posting. For
LAN 6007220926 `parent_loan_account_id` is NULL, so this returns early — the
whole parent path is skipped.

## SCENE B16 — Cancel collections, GL-CBS, deleteTask (line 588+)

- `updateCollectionForClosureProcessor` — cancels any pending collection records.
- `deathForeclosureGLCBSIntegrationProcessor` — pushes the GL movement to the CBS.
- `deleteTask` — removes the now-completed DFC task from the task service.
  (Per SDCP-9428, `deleteTask` is **non-fatal** and runs **before** the
  `postTransaction` so a task-service failure cannot leave the GL posted but the
  loan un-closed. See the changelog for `b8d60d5e1` / `ec1f3a2b8`.)

---

# PART C — The partial-cycle interest enhancement (SDCP-9301), in depth

PART B Scenes B4–B9 already introduced it. This part is the *why* and the
before/after, kept together so you can read the enhancement as one story.

## C1 — The problem the enhancement solves

Death lands mid-cycle. Interest has **accrued** on cycle #7 but was never
**billed**. `outstanding_loan_balance` correctly *includes* that interest (the
~59 `dcf_bpi_amount` term), so the insurer is invoiced for it. But a foreclosure
posting can only **settle billed buckets** — and the interest was not billed.

So two things must happen, in order:
1. **Force-bill** the stub → it lands in `BILLED_INTEREST`.
2. The DFC posting must have **legs that clear `BILLED_INTEREST`** by exactly the
   force-billed amount — otherwise `BILLED_INTEREST` is left with a standing,
   un-cleared debit and the trial balance is wrong.

## C2 — The split rule: recover pre-death, waive post-death

The force-billed stub (`forceBillSlice` = 61) is **not one homogeneous number**.
It is two economically different things:

- **Pre-death portion** (`preDeathBpi` = 59) — interest the borrower genuinely
  owed *while alive*, up to `death − 1`. This is a legitimate claim on the
  insurer → **recover** via `BLD_INT_AMT` (rule seq 5).
- **Post-death portion** (`partialCycleAccrual` = 2) — interest that accrued in
  the gap between death and the day the job ran. The borrower was already dead;
  the lender does not chase the estate and does not bill the insurer for it →
  **waive** via `BLD_INT_WAIVED_AMT` (rule seq 13).

This is the business rule you stated: *"upto 2nd Nov we will bill and recover;
remaining interest accrued will be waived."* In code it is the two EC keys set at
`DeathForeclosureInsuranceWriter.java:340-341`.

## C3 — Before the fix (what shipped originally on QA4)

The original SDCP-9301 code force-billed the stub but the DFC posting had **no
leg to settle it**: `BLD_INT_AMT` was fed only from `INT_AMT` (= 0), and the
waiver scan found nothing (cycle #7's interest due date is after the reporting
date). Result: the DFC posting posted only **5204**. The 61 force-billed into
GL 13336 was **debited and never credited back**:

```
  GL 13336 BILLED_INTEREST:  DR 716  vs  CR 655  ->  61 stuck on the debit side
```

A permanent ledger imbalance, and the insurer under-billed by ~59.

## C4 — The two commits

| Commit | What it did | Result |
|---|---|---|
| `274ba786b` | Added the **full** `forceBillSlice` (61) into `BLD_INT_AMT` and `calculateTotalTransactionAmount` | Fixed the GL imbalance, but recovered all 61 from the insurer → posting `5204 + 61 = 5265` — **2 over** `outstanding_loan_balance` |
| `f5315f7a0` (final) | **Split** the stub: 59 → `BLD_INT_AMT` (recover), 2 → `BLD_INT_WAIVED_AMT` (waive); `calculateTotalTransactionAmount` adds only 59 | Posting = 5263 = `outstanding_loan_balance`; GL 13336 nets to zero |

The final state is what PART B describes.

---

# PART D — The full GL proof and genericness

## D1 — Every GL leg of the DFC, proven to balance

Three transactions touch cycle #7's interest.

**Transaction A — force-bill (BILLING / NORMAL_BILLING), txn 1515285:**

```
  DR BILLED_INTEREST     13336   61
  CR INTEREST_RECEIVABLE 13578   61
```

**Transaction B — DFC posting (DEATH_FORECLOSURE / DEFAULT), txn 1515286:**

```
  seq 7  UNBLD_PRIN_AMT      DR DUE_TO_FC_B   CR LOAN_ACCOUNT 13334       5204
  seq 5  BLD_INT_AMT         DR DUE_TO_FC_B   CR BILLED_INTEREST 13336      59
  seq 13 BLD_INT_WAIVED_AMT  DR BILLED_INT_WAIVE  CR BILLED_INTEREST 13336   2
```

**BILLED_INTEREST (GL 13336) — does it net to zero?**

| Source | DR | CR |
|---|---|---|
| Transaction A (force-bill) | 61 | |
| Transaction B seq 5 (recover) | | 59 |
| Transaction B seq 13 (waive) | | 2 |
| **Net** | **61** | **61 → 0** ✓ |

The stub enters `BILLED_INTEREST` as a 61 debit and leaves as 59 (recovered) + 2
(waived). The account closes to zero. No drift.

**Who pays what:**

| Bucket | Amount | Settled by |
|---|---|---|
| Unbilled principal | 5204 | Insurer (`DR DUE_TO_FC_B`) |
| Pre-death interest stub (up to 2nd Nov) | 59 | Insurer (`DR DUE_TO_FC_B`) |
| Post-death interest stub (3rd–4th Nov) | 2 | Waived — lender writes off (`DR BILLED_INT_WAIVE`) |
| **Total recovered from insurer** | **5263** | = `outstanding_loan_balance` ✓ |

`loan_account_closure_details`: `paid_by_customer = 5263`,
`paid_by_insurance_company = 5263` — consistent.

## D2 — Is the fix generic? Yes.

Nothing in the fix hardcodes 59, 2, 5263, or any date. It works off two
per-loan-computed values:

- `preDeathBpi` = interest up to **`death − 1`** — adapts to any death date.
- `partialCycleAccrual` = interest **`death → reporting date`** — adapts to any
  reporting date.

| Case shape | Behaviour |
|---|---|
| Death on an installment due date | `partialCycleAccrual` = 0; whole stub recovered, nothing waived |
| Death = reporting date (same-day job) | `partialCycleAccrual` = 0; nothing waived |
| No partial-cycle interest at all | both NEW keys = 0 → `BLD_INT_AMT`, `BLD_INT_WAIVED_AMT`, `TRANSACTION_AMOUNT` byte-identical to pre-fix — **no regression** |
| Parent / group (SHG/JLG) loan | handled by `doParentPartPrePayment` — this fix does not touch it |

The invariant that always holds, for every loan:
**`forceBillSlice` (force-billed) = `preDeathBpi` (recovered) + `partialCycleAccrual` (waived)** —
so GL `BILLED_INTEREST` always nets to zero, and the DFC posting always equals
`outstanding_loan_balance`.

## D3 — Quick reference: amount → EC key → reference_code → GL

| Amount (LAN 6007220926) | EC key | `reference_code` | Rule seq | GL effect |
|---|---|---|---|---|
| 5204 | `POS` / `dcf_pos_amount` | `UNBLD_PRIN_AMT` | 7 | DR `DUE_TO_FC_B` / CR `LOAN_ACCOUNT` 13334 |
| 59 | `dcf_recovered_partial_cycle` (+`INT_AMT`) | `BLD_INT_AMT` | 5 | DR `DUE_TO_FC_B` / CR `BILLED_INTEREST` 13336 |
| 2 | `dcf_waived_partial_cycle` (+`LOSSES_INT_WAIVED`) | `BLD_INT_WAIVED_AMT` | 13 | DR `BILLED_INT_WAIVE` / CR `BILLED_INTEREST` 13336 |
| 61 (= 59+2) | `dcf_partial_cycle_accrual` | (force-bill BILLING txn) | — | DR `BILLED_INTEREST` 13336 / CR `INTEREST_RECEIVABLE` 13578 |
| 5263 (= 5204+59) | `transaction_amount` | (the DFC `postTransaction` `amount`) | — | total claimed from insurer |

## D4 — Files to open while reading

| What | Path | Key lines |
|---|---|---|
| DFC writer (orchestrator) | `loan/deathforeclosure/writer/DeathForeclosureInsuranceWriter.java` | 290 (entry), 301 (`syncBillingTillDate`), 336–346 (slice split), 391–432 (reference_code bridge), 403–419 (NEW recover/waive), 660 (`calculateLossInterestWaived`), 748–761 (`calculateTotalTransactionAmount`), 1147 (`computeUnbilledPartialCycleAccrual`), 1166 (`forceBillPartialCycleInterest`) |
| Outstanding-balance math | `loan/deathforeclosure/service/GetAmountDetailsForDeathForeclosureService.java` | 89 (`fetchOutStandingLoanBalanceAsPerDate`) |
| Interest calculation | `loan/interest/util/InterestCalculationUtil.java` | 425 (`...ForDeathForeclosure`), 454 (rounding) |
| Accounting rules (data) | `transaction_accounting_rule` where catalogue = `DEATH_FORECLOSURE/DEFAULT` | seq 1–20 |

---

## One-paragraph summary (the elevator version)

A death foreclosure settles every rupee a deceased borrower still owes and claims
it from the insurance partner. The DFC writer computes `outstanding_loan_balance`
(unbilled principal + pre-death interest + penal + fees − excess), force-bills any
mid-cycle interest stub so it sits in a billable bucket, then runs the
`DEATH_FORECLOSURE/DEFAULT` posting whose 20 rule legs each debit `DUE_TO_FC_B`
(claim from insurer) or a `*_WAIVE` loss account. The SDCP-9301 enhancement splits
the mid-cycle interest stub in two: the part accrued **before death** is recovered
from the insurer via `BLD_INT_AMT`, the part accrued **after death** is waived via
`BLD_INT_WAIVED_AMT`. The posting therefore recovers exactly
`outstanding_loan_balance`, the `BILLED_INTEREST` GL nets cleanly to zero, and the
loan closes. For LAN 6007220926: `5204 principal + 59 pre-death interest = 5263
recovered from insurer`, `2 post-death interest waived`.
