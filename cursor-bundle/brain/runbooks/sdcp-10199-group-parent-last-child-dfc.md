# SDCP-10199 — SHG/JLG parent last-child death foreclosure

**Canonical branch (closure series):** `mfi_integration_v3.7.1` @ merge `f45dbe3bd`  
**A2+B statement/labd (2026-07-15):** `mfi_integration_v3.4.2.4` @ `5b1b928ed`  
**TDPQA-72 QA acceptance (2026-07-17):** dedicated force-bill labd (no EMI hijack) + lapd principal=EXTRA-net — train `mfi_integration_v3.4.2.4` (see GAP-075)  
**Product 2026-07-22 (`9b6454df6`):** parent force-bill + parent RSCH `excess_amount=0` (A2 still nets principal); double-INT clear before RSCH  
**CRN uniqueness 2026-07-22 (`935c52743`):** `buildForceBillClientReference` = `accountId + valueDateMs + deathForeclosureDetailsId` — sequential same-`dateOfReporting` parent FBs no longer **134497** (GAP-078; **not** INT-180)  
**Writer:** `DeathForeclosureInsuranceWriter.doParentPartPrePayment` + `forceBillPartialCycleInterest` (child+parent) + last-child RSCH  
**Local proof:** `DCF_SEED_EMI_LABD=1 ACCEPTANCE_STRICT=1 SEED_EXTRA=0|1 ntest run dcf.group_parent_last_child_e2e` (fixture `PARENT_LAN=6000137433`)

## TDPQA-72 acceptance contract (fail-closed)

| Obs | QA fail mode | Permanent write-path fix | Assert |
|-----|--------------|--------------------------|--------|
| **Obs1** | EMI labd `txn_ref` overwritten while amounts stay EMI | INSERT dedicated force-bill labd; leave EMI row untouched | `assert_force_bill_labd` + EMI_LABD_FIXTURE preserved + **statement** shows force-bill `client_ref` |
| **Obs1b** | Parent missing force-bill in billing table | Parent `forceBillPartialCycleInterest` via `computeParentForceBillSlice` (max Accrued−Original, reportingAccrual) | dedicated parent FB labd prin=0 + GL BILLING legs + statement |
| **Obs2** | `tm.original_amount` ≠ `lapd.principal_amount` | Before save: principal=A2-netted POS; **Product:** `excess_amount=0`, interest=0 | amount==principal; excess=0 under `ACCEPTANCE_STRICT` |
| **Obs3** | Parent Accrued > Original on summary | `reconcileAccruedInterestToBilledOriginal` | SQL + webapp summary `interest_details` |
| Overview excess | Parent overview shows leftover excess | Parent RSCH zero EXCESS_* upserts + lapd.excess=0 | overview `amount_details.excess_amount=0` |

**Webapp (mandatory on UI-impacting ships):** `assert_webapp_bound_apis` fires `getLoanAccountSummaryDetails`, `getLoanAccountOverviewDetails` (`account_number_list`), `getLoanAccountStatement`. See `feedback_webapp_verify_mandatory_ui_ships.md`.

**Prevention checklist (agents):** never print `OK A2 netting` and Pass; never claim webapp verified without `acceptance.ui_fields` webapp markers; never mark GAP RESOLVED while registry note encodes weaker acceptance. Workspace gate: `scripts/lib/acceptance_coverage.py`.

## Fixture method (Vikram QA4 shape)

| Approach | Status |
|----------|--------|
| Full QA→local clone of 6011375325 / 5655 / 5656 | **Blocked** — no multi-table QA LAN import pack for this ticket |
| **Equivalent local product-70 SHG** auto-discover + non-last DFC (parent RSCH) + last DFC + `DCF_SEED_EMI_LABD=1` + EXTRA | **Used** — same Accrued orphan / EMI dirty / EXTRA acceptance class |

## DFC scenario matrix (code-backed)

| Scenario | Entry | Writer/path | Expected | Verify mode | Suite |
|----------|-------|-------------|----------|-------------|-------|
| SHG non-last child DFC | `deathForeclosureInsuranceJob` | child DFC + parent RSCH/reschedule | child CLOSED; parent ACTIVE; child force-bill labd | RUNTIME (same e2e child1) | `dcf.group_parent_last_child_e2e` |
| SHG last-child DFC + EXTRA>0 | same | last-child A2 net + parent FB + excess=0 | parent CLOSED; amount==principal; excess=0; child+parent FB labd | RUNTIME_VERIFIED | `SEED_EXTRA=1 DCF_SEED_EMI_LABD=1` |
| Dirty EMI labd pre-exists | same | `persistForceBillBillingDetails` INSERT | EMI fixture ref preserved + dedicated FB labd | RUNTIME_VERIFIED | `DCF_SEED_EMI_LABD=1` |
| EXTRA=0 last child | same | A2 path with 0 overpayment + parent FB | principal=POS; excess=0; Accrued≤Original; webapp | RUNTIME_VERIFIED | `SEED_EXTRA=0` |
| Webapp summary/overview/statement | same | — | Accrued≤Original; parent+child FB on statement; overview excess=0 | RUNTIME_VERIFIED | `assert_webapp_bound_apis` |
| Standalone individual DFC | `loanDeathForeclosure` | no parent RSCH | child force-bill labd only | PROCESSOR_MIRROR / extend later | `dcf.principal_split_sim` adjacent |
| GL principal split | writer model | BLD/UNBLD | sim matrix | PROCESSOR_MIRROR_SIM | `dcf.principal_split_sim` |
| Replay force-bill labd | writer | same `accountId\|\|valueDateMs\|\|deathForeclosureDetailsId` client_ref + `isForceBillLabdShape` | no duplicate / no EMI hijack; distinct claims get distinct CRNs | N/A evidence in writer + registry `acceptance.na` | GAP-078 @ `935c52743` |
| Parent force-bill labd | last-child RSCH path | `forceBillPartialCycleInterest` | dedicated prin=0 labd + BILLING GL | RUNTIME_VERIFIED | Obs1b assert |

## A2 + B (RESOLVED 2026-07-15 — Vikram/Srikant obs; acceptance hardened 2026-07-17)

| Issue | Symptom | Fix | Retest |
|-------|---------|-----|--------|
| **A2** | Parent last-child RSCH used **full POS** | EXTRA-net TRANSACTION_AMOUNT / UNBLD | Seed EXTRA>0; `assert_a2_extra_parent_rsch` |
| **B** | Force-bill without labd link | Persist labd after post | `assert_force_bill_labd` |
| **Obs1** | EMI hijack | INSERT dedicated FB labd | `DCF_SEED_EMI_LABD=1` |
| **Obs2** | amount≠principal | lapd principal=netted; **excess=0** (Product) | `ACCEPTANCE_STRICT=1` |
| **Obs1b** | parent FB missing | parent `forceBillPartialCycleInterest` | dedicated parent FB labd |

SoT: `.cursor/gaps-and-risks.md` **GAP-075**. Registry: `dcf.group_parent_last_child_e2e`. SHA `9b6454df6`.

## GAP-074 / INT-180 (open — deferred ship)

Parent can CLOSE after last-child DFC with residual pending INT (DPI on 3.7.1) when appropriation uses child `INT_AMT`. Fix commit `61278d5f8` is parked on `fix/sdcp-10199-parent-int-dpi-last-child-dfc` — **not** on `mfi_integration_v3.7.1@f45dbe3bd`. User decision 2026-07-10: wait for QA/prod case; discuss before merge. Do not claim RESOLVED in production. Tracker: ASK-057 **DEFERRED**. SoT: `.cursor/gaps-and-risks.md` **GAP-074**. **Not the same as A2/B** (statement EXTRA-net vs residual INT pending).

**Harness scope:** `ACCEPTANCE_SCOPE=obs123` (default) documents parent INT/DPI pending as **Out-of-scope** (explicit print, never WARN-and-pass). `ACCEPTANCE_SCOPE=full` **FAIL**s on INT/DPI pending. Obs1–3 pin: `PARENT_LAN=6000137433` `DEATH_DATE=2025-08-02`. Last-child amount assert = Obs2 (`amount==principal`, `excess=0`), **not** child==parent.

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
6. **Before `saveLoanAccountPaymentsDetails` on last child** — `net_amount = "0"`; set `principal_amount` to **A2-netted POS** and `excess_amount` to claim overpayment (do not leave principal at full POS — TDPQA-72 Obs2).
7. **`finalizeParentClosureOnLastChildDfc`** — asset classification **while still open**, then `loan_status=CLOSED` **and** `account.status=CLOSED` + closing dates.
8. **Overview next EMI** — `GetLoanAccountInstallmentDetailsProcessor` treats CLOSED if `loan_status` **or** `account_status` is CLOSED.
9. **A2 EXTRA-net** — when child claim has EXTRA / EXCESS_INCOME_INT (overpayment), parent last-child RSCH amounts must **net** that down (not book full POS as TRANSACTION_AMOUNT).
10. **B / Obs1 force-bill labd** — dedicated labd for force-bill (principal=0, interest=force-bill slice); `client_reference_number` = `accountId\|\|valueDateMs\|\|deathForeclosureDetailsId` (GAP-078 @ `935c52743`). **Never** overwrite an existing EMI labd `txn_ref`. Multi-row per installment is schema-valid; finder uses `ORDER BY id DESC LIMIT 1`; update prior FB via `isForceBillLabdShape` (prin=0).

## Local acceptance matrix (2026-07-22 @ accounting `935c527430`)

| Row | Env | Result | Notes |
|-----|-----|--------|-------|
| S1 | `ACCEPTANCE_SCOPE=obs123 SEED_EXTRA=0` pin `6000137433` / `2025-08-02` | **PASS** | Obs1–3 + RSTCRE + CRN uniqueness |
| S2 | `obs123 SEED_EXTRA=1 DCF_SEED_EMI_LABD=1` same pin | **PASS** | EXTRA + dirty EMI labd |
| S_full | `ACCEPTANCE_SCOPE=full DEATH_DATE=2025-09-15` | **PASS** (gate) | `int_pending=0` on this fixture — **does not close GAP-074**; INT-180 still parked `@61278d5f8` |
| Fresh | `DCF_FRESH_GROUP=1 SEED_EXTRA=0` | **PASS** | Real disburse→billing→DFC (e.g. parent `6004092625`). EXTRA seed on fresh can `134253` — use pin S2 for EXTRA |
| Fresh+EXTRA | `DCF_FRESH_GROUP=1 SEED_EXTRA=1` | **FAIL** (seed) | loanRepayment EXTRA seed `134253` — harness/next action; not a Writer regression |

**GAP-074:** still **OPEN**. Full-scope fail-closed assert is live; do **not** claim QA Pass for INT residual until INT-180 merges or a residual-exposing fixture FAILS `dcf.group_parent_last_child_e2e_full`.

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
