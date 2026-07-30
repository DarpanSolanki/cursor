# LMS-DEFECT — SHG child IAD tip stuck mid-month (distribute)

**Class:** LMS-DEFECT (follow-up to booking-abort formalize / DEFECT-#5 probe)  
**Status:** OPEN — probe only; **no product edit** this round  
**Related:** Accrued distribute `InterestGroupLoanAccrualDistributionService` (ffa882cdf era); booking gate `isAccrualPostingDate(end_date)`

## Probe verdict

**DEFECT_STUCK_TIP** — on fixture SHG parent `6000012030`, after calc distribute through mid-month then roll to month-end + `interestAccrualPosting`, child tip `end_date` **did not advance** and tip `total_accrual_posted_amount` stayed NULL.

Proof: `scripts/scratch/bone/proofs/child-tip-probe.txt`

```
AFTER_ME_POST child tip=2027-10-06|103.000000|NULL
child_end_after_mid=2027-10-06 child_end_after_ME=2027-10-06
end_date_advanced=False ended_on_me=False
VERDICT=DEFECT_STUCK_TIP
```

(ME day driven: 2027-11-30; child tip remained 2027-10-06.)

## Trace

1. **Create path** — empty window → one child row with `endDate = asOf` (parent latest IAD end, often mid-month):

```165:168:trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/grouploan/interest/service/InterestGroupLoanAccrualDistributionService.java
		if (windowRows.isEmpty()) {
			InterestAccrualDetailsEntity created = newChildRow(childAccountId, prevDueDate, asOf, ...);
```

```210:215:.../InterestGroupLoanAccrualDistributionService.java
	newChildRow(...):
		entity.setStartDate(startDate);
		entity.setEndDate(endDate);  // asOf — not advanced later
```

2. **Update path** — window rows exist → set Accrued only; **does not call `setEndDate`**:

```183:190:.../InterestGroupLoanAccrualDistributionService.java
		InterestAccrualDetailsEntity latest = windowRows.get(windowRows.size() - 1);
		...
		latest.setTotalAccruedAmount(latestTarget);
		toSave.add(latest);
		interestAccrualDetailsDaoService.save(toSave);
```

3. **Children skip independent calc** — parent SoT distribute; child does not run `createOrUpdateIADE` tip extend:

`InterestAccrualCalculationService` child branch → parent process + distribute (no child daily end_date advance).

4. **Booking** — `isAccrualPostingDate(end_date)` false while tip stuck mid-month → child never normal-books that tip (even after batch abort fix).

## STOP

No product edit in this formalize round (user instruction). Fix options for a later FIX-PLAN: advance child tip `end_date` to parent `asOf` on distribute update; or create new child row on ME/due boundaries like parent calc.

## Not confused with

`LMS-DEFECT-accrual-booking-abort.md` (`af52abe3d`) — parent/batch walk abort. This defect is **child tip end_date never reaches ME/due**.
