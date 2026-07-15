# SDCP-10199 — SHG/JLG parent last-child death foreclosure

**Canonical branch (closure series):** `mfi_integration_v3.7.1` @ merge `f45dbe3bd`  
**A2+B statement/labd (2026-07-15):** `mfi_integration_v3.4.2.4` @ `5b1b928ed` (`DeathForeclosureInsuranceWriter`)  
**Also present on:** `mfi_integration_v3.4.2.1` / `.2` / `.3` (tips are ancestors of 3.7.1 for closure series)  
**Writer:** `DeathForeclosureInsuranceWriter.doParentPartPrePayment` + force-bill + last-child RSCH amount bridge  
**Local proof:** `ntest run dcf.group_parent_last_child_e2e` (must assert **A2 EXTRA + B labd**)

## A2 + B (RESOLVED 2026-07-15 — Vikram/Srikant obs)

| Issue | Symptom | Fix @ `5b1b928ed` | Retest |
|-------|---------|-------------------|--------|
| **A2** | Parent last-child RSCH / statement used **full POS** (TRANSACTION_AMOUNT / UNBLD_PRIN / net) instead of **EXTRA-net** (claim overpayment EXCESS_* + overpaid penal/fee) → parent/child amount mismatch on statement | Last-child parent POS/net/gross/TRANSACTION_AMOUNT/UNBLD_PRIN net **EXTRA + overpaid penal/fee** to match child claim | Seed EXTRA>0 via child `loanRepayment` before DFC; `assert_a2_extra_parent_rsch` |
| **B** | Force-bill partial-cycle interest posted but **labd** missing or **txn_ref** not linked to `DFC_PRTL_BILL_*` | `forceBillPartialCycleInterest` persists/links labd after `postTransaction` | `assert_force_bill_labd` on death children |

SoT gap row: `.cursor/gaps-and-risks.md` **GAP-075 RESOLVED**. Registry: `dcf.group_parent_last_child_e2e`.

## GAP-074 / INT-180 (open — deferred ship)

Parent can CLOSE after last-child DFC with residual pending INT (DPI on 3.7.1) when appropriation uses child `INT_AMT`. Fix commit `61278d5f8` is parked on `fix/sdcp-10199-parent-int-dpi-last-child-dfc` — **not** on `mfi_integration_v3.7.1@f45dbe3bd`. User decision 2026-07-10: wait for QA/prod case; discuss before merge. Do not claim RESOLVED in production. Tracker: ASK-057 **DEFERRED**. SoT: `.cursor/gaps-and-risks.md` **GAP-074**. **Not the same as A2/B** (statement EXTRA-net vs residual INT pending).

## Forward-merge status

| Source tip | In 3.7.1? |
|------------|-----------|
| `upstream/mfi_integration_v3.4.2.1` | YES (ancestor) |
| `upstream/mfi_integration_v3.4.2.2` | YES |
| `upstream/mfi_integration_v3.4.2.3` | YES |
| `upstream/mfi_release_v3.6.1` | YES (merged `f45dbe3bd`) |
| Key SHAs `e919e3b33` `66e830670` `425472cab` | YES |

3.7.1 **adds** DPI legs (`DPI_AMT`, `waiveFutureDpiPastReporting`, billed DPI GL codes) on top of the 3.4.2.x parent-closure fixes.

## Correct last-child behaviour (do not regress)

1. **Parent PRIN is paid, not waived** — `principalForAppropriation = getPrincipalOutStandingAmount(parent)`; INT/DPI past reporting waived (`waiveFutureInterestPastReporting` + `waiveFutureDpiPastReporting`).
2. **Last-child overdue INT/DPI** — **intended** appropriation uses **parent** pending rows (`sumPendingComponentOnOrBefore` via `getDueDetails` + Java), **not** child `INT_AMT`. Released / `mfi_integration_v3.7.1` tip still uses child `INT_AMT` (**GAP-074**); parked fix `fix/sdcp-10199-parent-int-dpi-last-child-dfc` @ `61278d5f8` — do not merge until QA/prod discuss.
3. **Schedule reduction (non-last / shared formula inputs)** — `futurePrincipal − getUnpaidFutureBilledPrincipalForDeathForeClosure` (not all billed).
4. **EC shadowing** — `putLocal(LOAN_ACCOUNT_ENTITY, parent)` before parent appropriation / due updates.
5. **`upsertAdditionalAmount`** — replace UNBLD/BLD PRIN (+ BLD_INT / billed DPI) legs; do not append duplicates.
6. **Before `saveLoanAccountPaymentsDetails` on last child** — `net_amount = "0"` (that saver does `net + principal`; both were full POS → 2× statement principal).
7. **`finalizeParentClosureOnLastChildDfc`** — asset classification **while still open**, then `loan_status=CLOSED` **and** `account.status=CLOSED` + closing dates.
8. **Overview next EMI** — `GetLoanAccountInstallmentDetailsProcessor` treats CLOSED if `loan_status` **or** `account_status` is CLOSED.
9. **A2 EXTRA-net** — when child claim has EXTRA / EXCESS_INCOME_INT (overpayment), parent last-child RSCH amounts must **net** that down (not book full POS as TRANSACTION_AMOUNT).
10. **B force-bill labd** — partial-cycle force-bill must leave `loan_account_billing_details` with `transaction_reference_number` tied to the billing txn (`DFC_PRTL_BILL_*`).

## Anti-patterns (stale / wrong)

| Wrong idea | Why it hurts |
|------------|--------------|
| Waive all future parent dues on last child | Leaves PRIN unpaid / wrong GL; old unused helper `waiveFutureParentPendingDuesOnLastChildDfc` **removed** on 3.7.1 |
| Use child `INT_AMT` for last-child parent appropriation | Under-settles parent overdue INT left by prior sibling DFC → CLOSED parent with INT pending |
| Close only `loan_status`, leave `account.status=ACTIVE` | Loan 360 banner still ACTIVE; next EMI can still show |
| Trust batch `COMPLETED` alone | Local `glCBSIntegration` may fail; e2e waits for child `loan_status=CLOSED` |
| Analyze DFC on wrong train | Use 3.7.1 (or named QA tag); do not assume 3.4.2.1-only checkout |

## First SQL (symptom check)

```sql
-- parent + children status + account.status
SELECT la.la_account_number, la.loan_status, a.status AS account_status,
       la.la_closing_date IS NOT NULL AS la_closed, a.closing_date IS NOT NULL AS acct_closed
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.account a ON a.id = la.account_id
WHERE la.la_account_number IN ('PARENT','CHILD1','CHILD2');

-- parent PRIN buckets (pending must be 0; waived PRIN should be 0 on last-child happy path)
SELECT SUM(CASE WHEN component_type='PRIN' THEN paid_amount ELSE 0 END) paid,
       SUM(CASE WHEN component_type='PRIN' THEN waived_amount ELSE 0 END) waived,
       SUM(CASE WHEN component_type='PRIN'
           THEN due_amount-paid_amount-waived_amount ELSE 0 END) pending
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id = ldd.loan_account_id
WHERE la.la_account_number = 'PARENT' AND ldd.is_deleted = false;
```

## Related

- Local stack: [`dcf-local-stack.md`](dcf-local-stack.md)
- Scenario matrix: `scripts/dcf_sanity/scenarios.json` → `S08_shg_parent_last_child`
- Child foreclosure (different path): [`child-foreclosure-with-waiver.md`](child-foreclosure-with-waiver.md)
