# Force-bill must subtract what billing already billed (TDPQA-240)

**Defect class:** foreclosure force-bill bills interest a second time when the foreclosure date
coincides with an EMI due date, because the resolver reads accrual without asking whether that
accrual was already swept into a billing row.

## Where

`PartialCycleForceBillAmountResolver.latestPeriodAccruedAmount()` returned the newest
`interest_accrual_details.total_accrued_amount` outright. `RegularForeclosureForceBillService`
then posts a BILLING for it and writes a **dedicated interest-only labd** on the same
installment the EMI labd already covers.

## Evidence

**QA4** (`6011430325`, INDL, FC 05-Sep-2026): accrual periods 131 + 1962 + **262** = 2355 on
installment `12439936`; the 05-Sep EMI billing (`labd 162504`) billed **2355** — the whole
cycle. Foreclosure approve then wrote `labd 162702` for **262** again. Quote charged billed
interest 355; settlement legs credited Billed Interest **617**; legs summed 104,977 against a
104,715 collection, leaving **₹262 stuck in Termination Suspense**.

**Local red** (fresh INDL `6004175525`, EMI today): accrued 1229 == billed 1229 on installment
`7874036`, then force-bill added a second labd of **62**. `labd rows 1 -> 2`.

## The assert that catches it

**Count the labd rows on the foreclosure installment across the FC approve.** On the local run
the termination-suspense GL still netted 0.00 — the suspense residue is the QA4 *downstream*
consequence, not a reliable local signal. Amount-only or GL-only asserts miss this entirely.

## Fix shape

Bill only the accrual on the foreclosure installment that billing has **not** already taken:
sum `total_accrued_amount` over every IAD row for that installment, subtract the non-reversed
`loan_account_billing_details.interest_amount` for it, floor at zero. Summing per-installment
(not per-IAD-period) matters — several accrual periods share one installment, so comparing the
newest period's accrual against the installment's total billed under-bills a genuine mid-cycle
foreclosure.

## Related

The 27-Jul force-bill series (`3295f560f`, `e4b0d01c9`, `43b39aa10`) introduced this path and is
on origin **and** upstream `mfi_integration_v3.4.2.4`. `d725297f3` touches the same method but
only reorders precedence (charged BPI before newest-accrued); with `bpi = 0` it still falls
through, so it does **not** fix this.

Fixture recipe: [[feedback_foreclosure_local_fixture_gates]] ·
[[feedback_local_disburse_gst_simulator_block]]
