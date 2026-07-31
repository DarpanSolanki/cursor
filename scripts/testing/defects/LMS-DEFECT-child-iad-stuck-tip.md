# LMS-DEFECT — SHG child IAD tip stuck mid-month (distribute)

**Class:** LMS-DEFECT (follow-up to booking-abort formalize / DEFECT-#5 probe)  
**Status:** RESOLVED — 2026-07-31  
**Train:** accounting `mfi_integration_v3.4.2.4`  
**Commit:** `60e2c0ab9`  
**Fix:** `InterestGroupLoanAccrualDistributionService.applyWindowShareToChild` — when tip
`endDate.before(asOf)`: if `lastAccrualPostedDate != null` freeze Accrued=Posted + create
new tip to asOf; else `setTotalAccruedAmount` + `setEndDate(asOf)`.

## Probe (pre-fix)

**DEFECT_STUCK_TIP** — child tip `end_date` did not advance while parent tip advanced;
booking gate `isAccrualPostingDate(end_date)` blocked child tip booking.

## Verification (post-fix)

- `ntest run flowtest.shg_int_accrual_stitch` **PASS** (exit 0)
- Parent asOf / child tip end: **2027-11-05** for children `6000012036/37/38` on parent `6000012030`
- Window Accrued parity: parent=311 children=311 **PASS**
- Tip `start_date=2027-10-31` (ME) → freeze+new after posted tip (adversarial posted path)
- Tip carry=0; rate=aide 24%; Accrued≥Posted; LID non-null; unfrozen posted behind tip=0
- Full physical IAD column audit (11/11) FAIL-closed in stitch re-run after tip fix
- Batch reader still excludes children: `parent_loan_account_id IS NULL`
- Carry: intentional distribute 0 on new tips (not independent rounding carry) — see
  `feedback_money_behavior_parity_no_amount_only_ship.md`

## Not confused with

`LMS-DEFECT-accrual-booking-abort.md` — parent/batch walk abort.
