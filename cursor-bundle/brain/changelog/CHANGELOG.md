## 2026-07-31 | acct `af52abe3d` | accounting | mfi_integration_v3.4.2.4 | kg-flow | interestAccrualPosting soft-skip mid-month IAD
- apiName: interestAccrualPosting; tables: interest_accrual_details
- Batch InterestAccrualBookingBatchService continues past non-booking-day unposted IAD (was return false abort); L2 skip log; defect LMS-DEFECT-accrual-booking-abort
| kg-flow | interestAccrualPosting

## 2026-07-30 | acct `ffa882cdf` | accounting | mfi_integration_v3.4.2.4 | kg-flow | SHG INT Accrued parent SoT installment-window distribute
- apiName: interestAccrualCalculation (online DEFAULT + BATCH); tables: interest_accrual_details
- InterestGroupLoanAccrualDistributionService: SET ACTIVE child window Accrued via GroupLoanUtility fractions; skip child calc; stop_interest_accrual still distributes; removed adjustChildLoanAccountsInterestAccrual
| kg-flow | interestAccrualCalculation

- **TDPQA-192** `a9bcc275a` accounting@mfi_integration_v3.7.1 — DIY/DIM dual-code hubs (`resolveDaysInYear`/`isDaysInYear360`): raw 360/ACTUAL + DIY_* for getDaywiseInterestRate + Days360; apiName fetchRestructuringRepaymentSchedule; tables product_scheme.interest_calculation_days_in_year

## 2026-07-28 | acct (WIP) | accounting-v2 | mfi_integration_v3.4.2.4 | kg-flow | TDPQA-72 parent FC force-post+bill slice + RSCH BLD_INT

SHG parent mirror: INTEREST post exact child force-bill amount then BILLING; IAD posted stamped after TM only.
Parent RSCH_LOAN_PREPAYMENT: remap inherited INT_AMT→BLD_INT_AMT (BI); TAR setup SQL for BLD_INT_AMT/ADV_BLD_INT_AMT.
| kg-flow | loanPrepayment / parentLoanAccountPartPrepayment

## 2026-07-27 | acct `f377e6c80` | accounting-v2 | mfi_integration_v3.4.2.4 | kg-flow | TDPQA-72 bpi_amount=0 after force-bill (all paths)
- apiName: loanPrepayment, loanDeathForeclosure, individualChildLoanForeclosure; tables: transaction_partition_details, loan_account_billing_details
- ForceBillBillingSupport.postPartialCycleBilling zeros bpi_amount after AIR→BI BILLING — INDL/JLG/SHG child FC + DFC child/parent
- Prevents LOAN_PREPAYMENT BPI_AMT double AIR credit (Vikram 392164); verify: dcf.vikram_fc_rstcre_dfc_e2e PASS

## 2026-07-24 | kb | CG prevention harden + local DFC zero-partition diag

## 2026-07-27 | acct `dc06ba9aa` | accounting-v2 | mfi_integration_v3.4.2.4 | kg-flow | TDPQA-72 FC force-bill INT_AMT parity
apiName: loanPrepayment; keep bpi_amount; force_bill_posted/amount; suppress BPI_AMT; INT_AMT+=force_bill_amount (DFC BLD_INT_AMT parity); parent mirror trackSettlementSlice=false

---

- Fail-closed harness under ACCEPTANCE_STRICT when TM has 0 partitions; jira scan `child_gl_renamed_to_parent_name`
- KG diag nodes: child CG* vs parent named GL; local DFC/RSCH empty partitions env gap

## 2026-07-24 | kb | Child CG* vs parent named GL display SoT (TDPQA-72)
- Never strip `CG` / join parent `general_ledger.name` for child force-bill legs; quote `tpd.gl_code` as stored
- Memory `feedback_child_cg_gl_vs_parent_named.md` + brain `08-gl-posting-engine.md` display rule; harness `assert_force_bill_gl_shape`
- Evidence: `ExecuteTransactionRulesProcessor` + `ChildGeneralLedgerEntity.CHILD_GL_CODE_PREFIX`; fresh Vikram FB child CG13336/CG13578 vs parent 13336/13578

## 2026-07-24 | kb | Job-owned tables — never hand-mutate Accrued/IAD
- Standing map: `.cursor/skills/accounting-knowledge/job-owned-tables.md` (+ critical-lessons / MEMORY)
- Rejected: writer `reconcileAccruedInterestToBilledOriginal` (IAD only via accrual jobs / forceful booking)

## 2026-07-24 | TDPQA-72 | SHG parent force-bill = child FB (FC+DFC)
- sha: trustt-platform-accounting `5f4661b038` on `mfi_integration_v3.4.2.4` (not 3.4.2.5)
- apiName: loanDeathForeclosure / loanPrepayment / individualChildLoanForeclosure; tables: loan_account_due_details (force-bill), interest_accrual_details sync
- Parent FB amount mirrors each child event (accumulate same installment); EXCESS_*=0 on SHG child; Accrued-cap/consume/parent-EMI harness removed
- Verify: Vikram matrix_20260724_012246 clean PASS; adversarial Obs3 Accrued>Original pending

# Changelog — `/home/darpan/Documents/sliProd/`

> Audit log of every fix & enhancement committed from this workspace. Newest first. Format in [`README.md`](README.md). For detail, run `git show <sha>`.

---
## 2026-07-21 | workspace | sliProd | main | kb-only | Fail-closed cross-branch reuse gate

## 2026-07-23 | acct `b3478a1a6` | accounting-v2 | mfi_integration_v3.4.2.5 | SP-329 nestloop/BNL off on EOD readers
NestloopDisabledJdbcCursorItemReader SET LOCAL enable_nestloop/yb_enable_batchednl/yb_prefer_bnl off + work_mem=4MB on cursor conn; wired interest/penal/billing/advance/closure/DPD readers | kg-flow | batch.reader

---


## 2026-07-22 | workspace | sliProd | main | kb-only | Upgrade 8 TASK E local-parity gate
local_parity_gate in ship-discipline; process_matrix conditional; db-local-write DDL log; GAP-076/077 class — local PASS predicts train envs only when migrations/seeds cover schema

---


## 2026-07-22 | workspace | sliProd | main | kb-only | Upgrade 8 process router + LEARN + SELF-REPORT
process_matrix 18x7 PLAN/TTL/money-cell ratchet; super-agent close LEARN lifecycle; weekly SELF-REPORT.md; autopilot honors SKIP/CACHED

---


## 2026-07-22 | acct `935c52743` | accounting-v2 | mfi_integration_v3.4.2.4 | kg-flow | DCF parent force-bill CRN unique per claim
deathForeclosureInsuranceJob buildForceBillClientReference appends deathForeclosureDetailsId — sequential child DFC same value_date no longer 134497 on parent BILLING; sibling harness evidence non-last CRN blocked last-child

---


## deathForeclosureInsuranceJob
## 2026-07-22 | acct `9b6454df6` | accounting-v2 | mfi_integration_v3.4.2.4 | kg-flow | TDPQA-72 parent FB + excess=0

---


## createOrUpdateLoanAccount
## 2026-07-22 | acct `ae8e98a70f` | accounting-v2 | fix/clb-child-parent-mandate-fallback | CLB child mandate via parent_account_id

---

`VERIFIED_FIXED_CLEAN` + `REUSE_ALLOWED` only after unique SHA + auto diverge; FILE_TOUCH_HINTS/DIVERGED/stale = REUSE_FORBIDDEN; watermark honesty + corroborate/smoke stitch.

## 2026-07-21 | workspace | sliProd | main | kb-only | Cross-branch verified-fix discovery
`kg fixed-elsewhere` + `scripts/bin/fwd-port.sh`: live upstream ancestry DAG, KG precedent SHA containment, candidate-only file overlap, divergence/path/missing/audit, and BUG/FIX autopilot preflight.

## 2026-07-21 | acct `ac8f185bbc` | accounting-v2 | mfi_integration_v3.7.1 | kg-flow | TDPFR-547 DPI amountMap no EC leak
loanRecurringPaymentBatchApi: dpi_due/dpi_overdue from per-LAN amountMap.getOrDefault(ZERO); Kafka bulk_collection_data_; collection.dpi_overdue; PROCESSOR_MIRROR_SIM collections.tdpfr547_dpi_amountmap_sim.

## 2026-07-20 | lib `9c5c82d2d8` · LOS `0e4a0be2bd` · acct `f9d803c4e` | platform-lib + LOS + accounting | mfi_integration_v3.4.2.5 | TDPQA-54 Redis in-flight locks
disburseLoan | kg-flow | Owner-token `SET NX` + default 600000 ms TTL on LOS producer and Accounting consumer locks; Lua compare-and-delete release; terminal/LOCK/explicit-continuation decision matrix prevents concurrent orchestration and blind intermediate `DEFAULT` restart. `ntest run disbursement.redis_inflight_lock_sim` PROCESSOR_MIRROR_SIM + LOCAL_REDIS_RUNTIME PASS.

## 2026-07-20 | acct `7e1642a57e` | accounting-v2 | mfi_integration_v3.4.2.4 | kg-flow | Parent disburse rejects multi member REP_ACCT (134126)

## childLoanBooking CLB REP
## 2026-07-20 | acct ac87585a2 | accounting-v2 | mfi_integration_v3.4.2.5 | CLB blank REP fail-closed

---

disburseLoan createOrUpdateLoanAccount loan_account_events_queue — CustomValidate.validateMemberRepAcctUniqueness throws 134126 when any member_details has >1 REP_ACCT before CLB enqueue; removed keepAtMostOneRepAcct trim; kept hasRepAcct skip-parent-append. ntest disbursement.clb_rep_acct_dedupe_sim PROCESSOR_MIRROR_SIM PASS.

## 2026-07-19 | acct `ca558ec186` | accounting-v2 | mfi_integration_v3.4.2.4 | CLB REP_ACCT dedupe + NEFT CRR exact audit
KG-FLOW: childLoanDisbursement createOrUpdateLoanAccount loan_account_events_queue — earlier write-path skip-append + trim (trim later removed in `7e1642a57e`).

## 2026-07-17 | workspace | initial-setup | mfi_integration_v3.7.1 | dependency-led local Flyway hardening
Added workspace-only `scripts/bin/initial-setup-local.sh` around the untouched Flyway 5.2.4 runner; verified accounting-core schema status, documented legacy `schema_version` fallback and safe reconciliation, and opened GAP-077 for upstream masterdata/notifications duplicate versions. Initial-setup remained clean at `e4ade8c3f8`; no repo commit/push.

## 2026-07-17 | acct `e2789d5f05` | accounting-v2 | mfi_integration_v3.7.1 | kg-flow | DPI foreclosure BPD include business day

## 2026-07-17 | workspace | initial-setup | mfi_integration_v3.7.1 | verified local Flyway runbook and 3.7.1 schema gap
Fresh upstream e4ade8c3f8: bundled Flyway 5.2.4 localhost.sh repair+migrate per schema; accounting/LOS reconciled locally; no migration adds loan_account.dpi_suspense_amount, so local idempotent setup is separate from required QA/prod migration.

---


## fetchLoanForeclosureSimulationDetails,loanPrepayment
## 2026-07-17 | acct `8a1a7cd07` | accounting-v2 | mfi_integration_v3.7.1 | unify BPD as-of util sim+create

---

fetchLoanForeclosureSimulationDetails bpd_amount: DpiForeclosureBrokenPeriodService projects from business (not nextDay) + HALF_UP 0dp; QA LAN 6003768627 FC 29-Jul-2026 → ₹29 | kg-flow | fetchLoanForeclosureSimulationDetails

## 2026-07-17 | acct `b256efd054` | accounting-v2 | mfi_integration_v3.4.2.4 | kg-flow | DCF force-bill client_ref platform-numeric
loanDeathForeclosure | kg-flow | buildForceBillClientReference=accountId||valueDateMs (drop DFC_PRTL_BILL_); isForceBillLabdShape prin=0; VERIFY ACCEPTANCE_STRICT e2e parent=6003896527 client_ref 79708671770489000000/79708661770489000000 orig=133/40 EMI preserved Obs2 RSCH 13702==prin excess=200 Obs3 1376/3382/1014

## 2026-07-17 | acct `48f9461f1` | accounting-v2 | mfi_integration_v3.4.2.4 | TDPQA-72 DFC_PRTL_BILL constant + slim Accrued reconcile
loanDeathForeclosure | FORCE_BILL_CLIENT_REF_PREFIX + build/isForceBillClientReference helpers (no scattered literal); reconcileAccruedInterestToBilledOriginal 99->68 LOC same 2 phases. REAL-FLOW VERIFY ACCEPTANCE_STRICT=1 DCF_SEED_EMI_LABD=1 e2e: FB labd prin=0 + EMI preserved, client_ref DFC_PRTL_BILL_7899567_1770489000000 tm.orig=38, Obs3 Accrued==Original 919/974/1845, Obs2 amount=13702==principal. KG SKIP (no flow change).

---
## 2026-07-17 | acct `dfec1e60f1` | accounting-v2 | mfi_integration_v3.4.2.4 | kg-flow | TDPQA-72 Obs3 Accrued≤Original (port)
loanDeathForeclosure | kg-flow | Port a7e6d1d1c: reconcileAccruedInterestToBilledOriginal after DFC force-bill (child+parent); VERIFY ACCEPTANCE_STRICT e2e parent=6002329725 Obs3+webapp PASS

## 2026-07-17 | acct `29bd01e8a6` | accounting-v2 | mfi_integration_v3.4.2.4 | kg-flow | TDPQA-72 dedicated force-bill labd + lapd EXTRA (port)
loanDeathForeclosure | kg-flow | Port cae54fd9d: INSERT dedicated DFC_PRTL_BILL labd (no EMI hijack); last-child lapd principal/excess; labd finder ORDER BY id DESC LIMIT 1; Issue A/B PASS on train

## 2026-07-17 | acct `a7e6d1d1c4` | accounting-v2 | feature/tdpqa72-dfc-acceptance-labd-lapd | kg-flow | TDPQA-72 Obs3 Accrued≤Original reconcile
loanDeathForeclosure | kg-flow | reconcileAccruedInterestToBilledOriginal after DFC; Accrued≤Original on summary/webapp

## 2026-07-17 | acct `cae54fd9d6` | accounting-v2 | feature/tdpqa72-dfc-acceptance-labd-lapd | kg-flow | TDPQA-72 dedicated force-bill labd + lapd EXTRA reconcile
persistForceBillBillingDetails INSERT (no EMI txn_ref hijack); last-child lapd principal=A2-netted POS excess=claimOverpayment; labd finder LIMIT 1; e2e ACCEPTANCE_STRICT+DCF_SEED_EMI_LABD; GAP-075 | kg-flow | loanDeathForeclosure deathForeclosureInsuranceJob loan_account_billing_details loan_account_payments_details

## 2026-07-15 | workspace | Synced disbursement-guide.html (NEFT v2 / 3.4.2.4) from Desktop

## createLoanAccount
## 2026-07-15 | acct `59e9686a80` | accounting-v2 | mfi_integration_v3.4.2.4 | kg-flow | SDCP-11085 SHG child sanction_date on CLB

ChildLoanBookingEventsQueueDataPopulator copies member-then-parent sanction_date into child loan_details on CLB; forward traffic only. VERIFY: disbursement.child_sanction_date_sim PROCESSOR_MIRROR_SIM PASS. INDL null LOS-owned (updateLoanAppStatus never setSanctionDate). Stock SHG children need ops backfill from parent. | kg-flow | createLoanAccount | childLoanEventProcessingBatchJob


---


## childLoanForeclosure
## 2026-07-15 | acct `dadb354cd5` | accounting-v2 | mfi_integration_v3.4.2.4 | SDCP-11058 re-land BPI parent distribute

---


## childLoanReopening
## 2026-07-15 | acct `163201d86` | accounting-v2 | mfi_integration_v3.4.2.4 | TDPQA-102 child reopen payment components

---


## 2026-07-15 | acct `5b1b928ed` | accounting-v2 | mfi_integration_v3.4.2.4 | kg-flow | last-child DFC A2 EXTRA-net + B force-bill labd
loanDeathForeclosure | kg-flow | DeathForeclosureInsuranceWriter: last-child parent POS/net/gross/TRANSACTION_AMOUNT/UNBLD_PRIN net EXTRA+overpaid penal/fee to match child claim; forceBillPartialCycleInterest persists/links labd txn_ref after postTransaction

---

Mirror of Desktop NEFT-v2-complete guide (`mfi_integration_v3.4.2.4`, entityType, NeftStage1InquiryGate, split("_", 3)) into `cursor-bundle/brain/guides/disbursement-guide.html`; Desktop kept as source (md5 `1eecccb3cd3ffa1ac79c5dfd8a65fef4`).



## 2026-07-13 | acct `bb6b37d178`+`682afe5ca2` | accounting-v2 | revert SDCP-11058 from 3.4.2.2/3.4.2.3
Reverted 8d9f0feed8 BPI distribute on origin mfi_integration_v3.4.2.2 and mfi_integration_v3.4.2.3; kept on 3.4.2.4. Upstream PR still required. Release 3.4.2.2/3 still have fix until merged.

---


## 2026-07-10 | acct `8d9f0feed8` | accounting-v2 | mfi_integration_v3.4.2.2 | SDCP-11058 SHG BPI parity (next release)
Cherry-pick of BPI distribute-any-N onto **3.4.2.2** (not 3.4.2.1 prod-today). Diff: ChildLoanForeclosureProcessor only. | kg-flow | loanPrepayment individualChildLoanForeclosure

## 2026-07-10 | acct `4acc7036d4` | accounting-v2 | fix/sdcp-11058-shg-bpi-parity | kg-flow | SDCP-11058 SHG parent FC BPI = sum(children) any N
ChildLoanForeclosureProcessor BPI uses getDistributedAmountEqually(parent) like foreclosure_fee for any N; ntest foreclosure.shg_bpi_parity unit PASS; product children sum to parent quote | kg-flow | loanPrepayment childLoanForeclosure

---


## 2026-07-10 | workspace | GAP-074 INT-180 deferred (user) — open gap; parked `61278d5f8`
User kept last-child parent INT/DPI under-settlement as open High GAP-074; fix on `fix/sdcp-10199-parent-int-dpi-last-child-dfc` @ `61278d5f8` — do not merge to `mfi_integration_v3.7.1` until QA/prod discuss; ASK-057 DEFERRED. Not RESOLVED in production.

---

## 2026-07-10 | acct `61278d5f8` | accounting-v2 | fix/sdcp-10199-parent-int-dpi-last-child-dfc | kg-flow | SDCP-10199 last-child parent INT from parent pending
doParentPartPrePayment last-child: sumPendingComponentOnOrBefore(getDueDetails) for INT/DPI + waiveFutureDpiPastReporting; e2e PASS | **PARKED / DEFERRED SHIP 2026-07-10 — not on mfi_integration_v3.7.1; see GAP-074**

---


## 2026-07-10 | acct uncommitted | accounting-v2 | mfi_integration_v3.7.1 | SDCP-10199 last-child parent INT from parent pending
UNCOMMITTED (no kg-flow until real SHA): doParentPartPrePayment last-child uses sumPendingComponentOnOrBefore(getDueDetails) for INT/DPI + waiveFutureDpiPastReporting on parent. Local e2e dcf.group_parent_last_child_e2e PASS this session. Apis: deathForeclosureInsuranceJob (orch verified).

---


## 2026-07-10 | acct `f45dbe3bd` | accounting-v2 | mfi_integration_v3.7.1 | kg-flow | SDCP-10199 forward-merge + dead waive removed
3.4.2.x SDCP-10199 ancestors of 3.7.1; removed unused waiveFutureParentPendingDuesOnLastChildDfc; parent last-child pays PRIN | kg-flow | deathForeclosureInsuranceJob RSCH_DEATH_FORECLOSURE

---


## 2026-07-10 | workspace | harness | mfi_integration_v3.7.1 | kg-flow | DPI quick regression + booking-anchor harness
dpiAccrualBooking sealed_unposted=anchor-only; DPI_REGRESSION_PROFILE=quick milestones+booking_anchor; column audit wired; branch gate 3.7.1

---


## 2026-07-10 | acct `77921d275f` | accounting-v2 | mfi_integration_v3.7.1 | kg-flow | dpiAccrualBooking EMI due seal anchor
dpiAccrualBooking books when endDate is month-end or any INT/PRIN due day (calc nextBoundary parity); avoid getLoanDueDetailsForDueDate LIMIT-1 DPI collision after billing — dpi_accrual_details.accrual_posting_date for next-EMI seals (2540301 / loan 8101960)

---


## 2026-07-10 | acct 412f4d03e3 | accounting-v2 | mfi_integration_v3.7.1 | kg-flow | DPI slice by EMI due not grace anchor
dpiAccrualCalculation resolveSliceInstallment: latest due<=segStart owns row; EMI1 end at next due_date (14-Jun) not overdue (18-Jun); dpi_accrual_details LAN 8101960

---


## 2026-07-10 | acct 4321639df | accounting-v2 | mfi_integration_v3.7.1 | kg-flow | DPI grace stored overdue gate
KG-FLOW: dpiAccrualCalculation resolveAdmissionOverdueDate uses stored loan_due_details.overdue_date only (>= gate; grace-0 overdue=due valid); first slice start_date=due_date; interest-parity seals unchanged. Tables: dpi_accrual_details loan_due_details

---


## 2026-07-10 | acct `b78e1113c` | mfi_integration_v3.7.1 | kg-flow | grace stored overdue + EMI1 seal
KG-FLOW: dpiAccrualCalculation resolveAdmissionOverdueDate + applyGraceBackfill; loan_due_details.overdue_date gate; tables dpi_accrual_details loan_due_details

---


## 2026-07-10 | acct `72e461e10` | accounting-v2 | feature/delayed_payment_interest | kg-flow | DPI grace stored overdue + EMI1 seal
KG-FLOW: dpiAccrualCalculation resolveAdmissionOverdueDate prefers loan_due_details.overdue_date; grace gate >= penal parity; first post-grace backfill from due_date; EMI1 seals due→next EMI due (skip month-end micro-split); extend posted slices. Tables: dpi_accrual_details, loan_due_details.

---


## 2026-07-10 | acct `f5c4e0a25` | accounting-v2 | mfi_integration_v3.7.1 | kg-flow | SDCP-11016 foreclosure sim DPI projection (changelog-sha `1baf3f4d8f` not ancestor of tip; labeled HEAD-eq)
KG-FLOW: fetchLoanForeclosureSimulationDetails projects billed DPI for future foreclosure dates

---


## 2026-07-10 | acct `1b34dee4b` | accounting-v2 | mfi_integration_v3.7.1 | kg-flow | loanPrepayment billed DPI + BPD in approve validation (changelog-sha `167d0942db` not ancestor of tip; labeled HEAD-eq)
KG-FLOW: loanPrepayment ValidateFinalPrepaymentProcessor includes billed_dpi_amount_to_be_paid and bpd_amount_to_be_paid in foreclosure amount check (SDCP-11048)

---


## loanPrepayment billed DPI+BPD validation; DPI column audit harness
loanPrepayment: ValidateFinalPrepaymentProcessor billed_dpi+bpd; verify_dpi_accrual_slice_integrity extended; run_dpi_three_job_verify + run_dpi_column_audit.sh

---


## 2026-07-10 | acct `068247cc9` | accounting-v2 | mfi_integration_v3.4.2.2 | kg-flow | SDCP-10227 bank error filler REQUIRES_NEW persist
| kg-flow | disburseLoan callBankAPIForDisbursement — INDL/JLG flat bank fail + SHG parent mirror use updateLoanAccountFillerNewTransaction so filler_1/2 survive fatal raise; loan_account

---


## disburseLoan getLoanAccountDetails
## 2026-07-09 | acct `b78517980` | accounting-v2 | mfi_integration_v3.4.2.2 | SDCP-10227 SHG CLMT bank error parent fillers

---


## 2026-07-09 | acct `f5c4e0a25` | accounting-v2 | mfi_integration_v3.7.1 | kg-flow | SDCP-11016 foreclosure sim DPI future date (changelog-sha `e175b78cb` not ancestor of tip; labeled HEAD-eq)
fetchLoanForeclosureSimulationDetails: DpiForeclosureBrokenPeriodService projects DPI through selected foreclosure date when future; reuses accrual simulate path aligned with broken-period interest.

---


## 2026-07-09 | acct `f5c4e0a25` | accounting-v2 | mfi_integration_v3.7.1 | kg-flow | SDCP-11016 foreclosure sim bpd_amount future dates (changelog-sha `e175b78cb` not ancestor of tip; labeled HEAD-eq)
fetchLoanForeclosureSimulationDetails: DpiForeclosureBrokenPeriodService + simulateAccrualAmountBetweenDates projects DPI till selected foreclosure date when future; parity with bpi_amount. Tables: loan_dpi_accrual_details, loan_due_details.

---


## 2026-07-09 | acct `b157b2d33` | accounting-v2 | NOT-ancestor-of-3.7.1-tip@b157b2d33 | kg-flow | loanAccountRebooking interest day-count guard
GenerateRepaymentScheduleProcessor.ensureInterestCalculationDayCounts loads product_scheme days when EC blank; ReducingBalanceInterestAmountCalculator fail-fast 130045/130046. Pairs Ramya `00292b217` resolveDaysInYear after PSFD master-data migration.

---


## dpiAccrualCalculation SHG parent child parity
## 2026-07-09 | acct `f42f5b117` | accounting-v2 | mfi_integration_v3.7.1 | SDCP-11012 SHG DPI parity window fix (changelog-sha `74da61acf` not ancestor of tip; labeled HEAD-eq)

---


## 2026-07-09 | acct `1b34dee4b` | accounting-v2 | mfi_integration_v3.7.1 | kg-flow | loanPrepayment approve 132268 billed DPI+BPD (changelog-sha `844081f83` not ancestor of tip; labeled HEAD-eq)
ValidateFinalPrepaymentProcessor.fetchForeclosureAmount adds billedDpiAmountToBePaid + bpdAmountToBePaid from prepayment_details; tables: prepayment_details

---


## 2026-07-09 | acct `425472cab` | accounting-v2 | mfi_integration_v3.4.2.1 | kg-flow | SDCP-10199 QA6 display gaps
last-child RSCH saveLoanAccountPaymentsDetails: net_amount=0 avoids 2x principal in statement; GetLoanAccountInstallmentDetails uses loan_status CLOSED; finalizeParent sets account.status CLOSED | kg-flow | getLoanAccountOverviewDetails RSCH_DEATH_FORECLOSURE

---


## 2026-07-09 | acct `425472cab` | accounting-v2 | mfi_integration_v3.4.2.1 | SDCP-10199 display gaps
last-child RSCH: net_amount=0 before payment details (principal not 2x); account.status CLOSED; overview installment uses loan_status | kg-flow | getLoanAccountOverviewDetails RSCH_DEATH_FORECLOSURE

---


## 2026-07-09 | acct `4d44f2f92` | accounting-v2 | NOT-ancestor-of-3.7.1-tip@4d44f2f92 | DPI EOD inclusive calc + booking anchor
dpiAccrualCalculation: processThrough=nextDay(today), inclusive segment walk, cursor=nextDay(segmentEnd), resolveSliceStart; dpiAccrualBooking: post when businessDate OR end_date is PRIN/INT due/month-end; tables dpi_accrual_details

---


## dpiAccrualCalculation dpiAccrualBooking dpiBilling
## 2026-07-09 | acct `e1875d1b4` | accounting-v2 | NOT-ancestor-of-3.7.1-tip@e1875d1b4 | DPI interest-parity calc + booking

---


## dpiAccrualCalculation
## 2026-07-08 | acct `a66900048` | accounting-v2 | feature/sdcp-11012-shg-dpi-parity-3.7.1 | kg-flow | DPI seals due/month-end only (grace day-walk)
KG-FLOW: dpiAccrualCalculation seals like interest — EMI due + month-end only; grace gates daily base/anchor; mid-slice amounts day-walked into one row (no overdue-date seal). Reverts 46f115199 overdue boundaries. Tables: dpi_accrual_details.

---


## dpiAccrualCalculation
## 2026-07-08 | acct `46f115199` | accounting-v2 | feature/sdcp-11012-shg-dpi-parity-3.7.1 | kg-flow | DPI per-EMI grace base/anchor + overdue boundaries (superseded for seals)
KG-FLOW: Per-EMI grace admit retained; overdue-date *seal* boundaries superseded by a66900048 (interest-parity seals only). Tables: dpi_accrual_details, loan_due_details.

---



## dpiAccrualCalculation SHG parent child parity
## 2026-07-08 | acct `daf6a331c` | accounting-v2 | feature/delayed_payment_interest | SDCP-11012 SHG DPI parent=sum(children)

---


## 2026-07-08 | acct `66e830670` | accounting-v2 | mfi_integration_v3.4.2.1 | kg-flow | parent DFC asset classification on closure
KG-FLOW: finalizeParentClosureOnLastChildDfc runs DPD + asset criteria + classification while parent ACTIVE (SEC NPA reset) before CLOSED; fixes stale DOUB_1 on Loan 360. Tables: loan_account, asset_classification_slabs.

---


## 2026-07-08 | acct `e919e3b33` | accounting-v2 | mfi_integration_v3.4.2.1 | kg-flow | SDCP-10199 schedule reduction formula L1
Core fix: parent first-child RSCH scheduleReduction = futurePrincipal - getUnpaidFutureBilledPrincipalForDeathForeClosure(child, deathDate) not minus all unpaid billed. Root cause: overdue billed (due<death) was double-subtracted → -3710 PRIN. Reverted GenerateRepaymentScheduleProcessor clamp.

---


## 2026-07-08 | acct `63f2314c1` | accounting-v2 | mfi_integration_v3.4.2.1 | kg-flow | SDCP-10199 negative parent PRIN guard
First-child group DFC parent RSCH: clamp negative netAmount (futurePrincipal-unpaidBilled) to zero in DeathForeclosureInsuranceWriter; skip PRIN appropriation when pending<=0; GenerateRepaymentScheduleProcessor early-return on non-positive part-prepayment. Fixes negative PRIN due rows on parent LAN mid-schedule death.

---


## 2026-07-08 | acct `82cb142e7` | accounting-v2 | mfi_integration_v3.4.2.1 | kg-flow | SDCP-10295 interest billed original + outstanding
getLoanAccountSummaryDetails interest_details: original_amount=billed interest (loan_account_billing_details non-reversed EXISTS), current_due_amount(Outstanding)=billed-(paid+waived+writtenoff). New LoanDueDetailsRepository.getBilledInterestAmount; GetLoanAccountSummaryDetailsProcessor.populateInterestOriginalAndOutstanding; response template original_amount mapTo interest_original_amount.

---


## deathForeclosureInsuranceJob
## 2026-07-07 | acct `74d566432` | accounting-v2 | fix/sdcp-10199-parent-last-child-dfc-v2 | SDCP-10199 last-child parent closure

---


## deathForeclosureInsuranceJob RSCH_DEATH_FORECLOSURE
## 2026-07-07 | acct `74d566432` | accounting-v2 | fix/sdcp-10199-parent-last-child-dfc-closure | SDCP-10199 last-child parent closure

---


## 2026-07-02 | acct `8a60c6591` | accounting-v2 | feature/delayed_payment_interest | kg-flow | DPI skip mapper cleanup
| kg-flow | dpiAccrualCalculation dpiAccrualBooking dpiBilling — delete DpiBatchWriterSkipItemSupport; Vo mappers plain after GenericListenerV3 resolveSkipItem

---


## dpiAccrualBooking force_async skip
## 2026-07-02 | lib `43144909ac` | trustt-platform-lib | feature/delayed_payment_interest | BatchWriterSkipItemSupport generic force_async skip

---

## 2026-06-12 | acct `8f1be5234` | accounting-v2 | feature/delayed_payment_interest | DPIC: fix DPI accrual window start — earliest-overdue installment (mirror DPD)
`DpiAccrualCalculationBatchService` used `getLatestLoanInstallmentDetailsEntity` (next *future* EMI, `installment_date >= businessDate`) → windowStart fell after windowEnd → every overdue loan skipped unless a prior `dpi_accrual_details` row was seeded. Now uses `getEarliestInstallmentDateWithUnpaidDpdComponents` (DPD's earliest-overdue predicate) for window start, reusing both existing queries (no new query). On top of user's `007135ba6` (min/max array order) + `6bf108847` (JTF templates). Found in user local dev-test. Build green. NOT runtime-verified.

## 2026-06-12 | acct `91a5b7536` | accounting-v2 | feature/delayed_payment_interest | DPIC: register DPI EOD batch jobs at startup (loader + placeholder beans)
The 3 DPI EOD jobs had `buildJobForTenant()` but no loader invoked it → never registered in `mfi_batch.batch_job`. Wired the 3 `Dpi*BatchConfigService` into `LoanSystemDailyJobLoader` (EOD order, mirroring interest) + added their `BatchJobPlaceholderConfig` stub beans. (api_master V000450 alone only did HTTP routing.) Rebased onto integrated SI/eNACH DPIC tip. NOT runtime-verified.

## 2026-06-12 | iset `b51630e7` | initial-setup | feature/delayed_payment_interest | DPIC: register DPI batch-job APIs in api_master (V000450)
platform_master Flyway `V000450__added_api_master_for_dpi_batch_jobs.sql` inserts `dpiAccrualCalculation` / `dpiAccrualBooking` / `dpiBilling` into `api_master` (service ACCOUNTING), mirroring V000039 — the 3 DPIC EOD Requests were unregistered in the API registry. NOT runtime-verified.

## 2026-06-12 | acct `1dbfd59b6` | accounting-v2 | feature/delayed_payment_interest | DPIC: restructure DPI capitalisation + post-maturity DPI billing date (product clarifications)
`loanAccountRestructuring` gets `CapitaliseAccruedDpiOnRestructureProcessor` (accrued-unbilled DPI → DPI due on first new installment + `markBilledTillDate`; billed DPI dues already preserved by component-agnostic `loan_due_details` delete). `DpiBillingBatchService`/`DpiBillingItemReader` bill post-maturity DPI on the next monthly anchor (`maturity_date` rolled past accrual `end_date`). v1 monthly only. NOT runtime-verified — awaiting QA.

## 2026-06-10 | acct `aecf3013e` | accounting-v2 | feature/neft-v2-payment-reinit-qa-3.3.1.2 | Fix MFT (SHG-parent/ACCTWB) repeat payment reinitiation blocked at reinit_disbursement_status=COMPLETED
Drop `!ACCTWB` guard on the COMPLETED->DTFC_SUCCESS reinit-cycle reset + make MFT branch honor reinitCycleWasReset (mirror NEFT); MFT/NEFT v1/NEFT v2 now repeat-reinit uniformly across SHG-parent/JLG/INDL.

## 2026-06-09 | acct `6e417f1df` | accounting-v2 | feature/neft-v2-payment-reinit-qa-3.3.1.2 | Restore payment_reinitiation_update bypass on updateLoanAccountPreDisbursementDetails (134130 fix)

NTB payment-reinitiation updates the disbursement account of an already-disbursed loan (disbursement_status in BLOCK list, e.g. COMPLETED) before re-triggering NEFT. Commit `953a468eb` stripped the `payment_reinitiation_update` gate + template field from this leg (scoping the 3.2.8.4.1 hotfix) and leaked into this reinit branch via merge → `updateLoanAccountPreDisbursementDetails` always ran `validateDisbursementUpdate` → 134130 "Loan Account is already disbursed" (LAN 6008853125, QA3). Restored on this leg only (disburseLoan/REINITIATE_BANK leg already retained the flag): when `payment_reinitiation_update=true`, bypass disbursed validation + CLMT cash-override, update mode details only; re-added field to shared request template so the flag travels from LOS. Build verified green (compileJava, Java 17, via dedicated in-boundary GRADLE_USER_HOME `.gradle-local` — shared `~/.gradle` had a filesystem-corrupted `groovy-bom/4.0.22` inode). Pushed; awaiting QA retest.

---

Same fix as `796c53187` (hotfix branch). Writer sets tenant via `batchComponent.setTenantByTenantCode(tenantCode)` → routes accrual writes to the tenant schema (`mfi_accounting`) instead of falling back to `platformMasterDataSource`/`platform_master` → fixes `relation "interest_accrual_details" does not exist`. Reader drops `account` + `batch_failure_audit` joins (la_* sourced from loan_account). Verified prerequisites on v3.3.1.1: base files identical, `la_*` populated (entity + CreateLoanAccountProcessor:156-160). Reader query verified on qa2+qa4 (row/value parity, 0 NULL la_*). Build green (Java 17). Fast-forward-pushed directly to `origin/mfi_integration_v3.3.1.1` (also synced the fork's mainline up to upstream's 3 newer commits); temp branch deleted. Writer routing still NOT runtime-verified — needs QA job run.

---

## 2026-06-09 | `c054f7149` | accounting-v2 | feature/delayed_payment_interest | Align advance DPI leg to product sheet — ADV_BILLED_DPI_INT_AMT

Product updated the sheet (`...DPI v 1.3.xlsx`, 11:06) to resolve the advance/due same-source_amount collision: the advance/excess DPI leg (DR EXCESS_ACCT) in rules 116/117/209 + DFC is now `ADV_BILLED_DPI_INT_AMT` (due leg stays `BILLED_DPI_INT_AMT`, DR DUE_TO_FC_B/TRMN_SUSP). Renamed the code's `ADV_DPI_AMT` → `ADV_BILLED_DPI_INT_AMT` in foreclosure, part-prepayment and death-FC processors (4 sites). Repayment EXCESS_AMT (rule 110) is `BILLED_DPI_INT_AMT` in the sheet (single leg, no collision) — reverted the earlier `dpi_reference_code`→ADV indirection back to plain `BILLED_DPI_INT_AMT`. Build green (Java 17). Pushed; awaiting QA retest. Note: this reverses the earlier "repayment should be ADV" ask — the product sheet kept 110 as BILLED_DPI_INT_AMT.

---

## 2026-06-09 | acct `a7812a2e8`+`796c53187` | accounting-v2 | hotfix-interest-accrual-calculation | Fix interestAccrualCalculation `relation "interest_accrual_details" does not exist`

Writer set a dbConfig-less `PlatformTenant(1L, tenantCode, "")`, so the tenant-less EOD write fell back to `platformMasterDataSource` (schema `platform_master`, table not visible). Now sets the tenant via `batchComponent.setTenantByTenantCode(tenantCode)` (resolves full tenant with dbConfig) → routes to `mfi_accounting`, matching the working InterestAccrualBookingItemWriter. Reader: dropped `account` join (la_currency/la_account_number/la_office_id from loan_account denorm cols, product_scheme via la_product_scheme_id) + dropped batch_failure_audit join. Verified on qa4: 2250=2250 rows, 0 value mismatches, 0 NULL la_* for ACTIVE. Build green (Java 17). Pushed to origin (DarpanSolanki fork). NOT VERIFIED at runtime — `setTenantByTenantCode` self-guards (`getTenant()==null || blank code`) so it won't override a stale decorator stub; needs a QA job run. Skip-mapper async `ClassCastException` left as a separate platform-lib item.

---

## 2026-06-09 | acct `39785b0f7` + init-setup `ebe4bd33` | accounting-v2 + initial-setup | feature/delayed_payment_interest | Forward-port DPI engine onto mfi_release_v3.5.0 for QA release

DPIC release-branch integration. `feature/dpic-v1` was based on mfi_integration_v3.3.2 (585/1279 commits behind 3.5.0) and the release branch already had a *different* partial DPIC line (`sli_dpic` = DPI **presentation**, not our **accounting engine**) — so a blind `git merge` would have produced duplicate Flyway versions + dragged the divergence. Instead forward-ported. **accounting-v2:** squash-merged dpic-v1 onto the release branch — 95 files clean, 4 conflicts resolved; `DeathForeclosureInsuranceWriter` re-implemented DPI legs on 3.5.0's new DEATH_FORECLOSURE ruleset (ADV_DPI_AMT / BILLED_DPI_INT_AMT / BILLED_DPI_INT_WAIVED_AMT, preserving DCF reporting-cycle force-bill; dropped POS/INT_AMT/ADV_POS/LOSSES_*_AIR). **initial-setup:** added the 3 missing engine migrations (V000187 create_dpi_accrual_details, V000188 add_dpi_amount_columns, V000193 dpi waiver columns) — config migrations (V000190/V000194/V000119) already present from sli_dpic. Build green (Java 17). NOT VERIFIED at runtime — death-FC DPI needs focused QA review; V000187/188/193 are out-of-order vs the release branch's V000189/190/194 (fresh QA DB applies in order; flag for already-migrated envs). Pushed to origin; awaiting QA retest.

---

## 2026-06-09 | `bfea657df` | accounting-v2 | feature/dpic-v1 | DPI NPA accrual + advance-leg alignment to product sheet v1.3(1)

Latest product sheet (`...DPI v 1.3 (1).xlsx`) adds daily `DPI_NPA_ACCRUAL` (New_Id_5, leg `DPI_ACCR_INT_AMT_NPA`, DR DPI_ACC_NOT_DUE / CR DPI_INT_SUSP_AIR) so DPI fully mirrors interest 104/105/106. Fixed `DpiAccrualBookingBatchService` NPA branch to emit that sub_type + leg (was wrongly `DPI_ACCR_INT_AMT`). Advance/excess DPI now routed via `ADV_DPI_AMT` (DR EXCESS_ACCT) distinct from due `BILLED_DPI_INT_AMT` (DR DUE_TO_FC_B/TRMN_SUSP): added DPI to the excess split in part-prepayment and to repayment EXCESS_AMT mode (`dpi_reference_code` in `PopulateAmountForExcessRepaymentModeProcessor` + `${dpi_reference_code}` leg); foreclosure/death-FC/reschedule-prepay already correct. Stripped explanatory comments per review. Build green (Java 17). NOT VERIFIED at runtime — product must seed rules for `DPI_ACCR_INT_AMT_NPA` and rename the advance legs to `ADV_DPI_AMT` in rules 110/116/117/209/DFC; pushed, awaiting QA retest + product sheet seeding.

---

Authorization had no working cache (zero `cacheClient.get`; the one `set` in `GetUseCaseDetailsProcessor` is never read back), so every permission check hit the DB — APM: role 2.18M, user_role_mapping 1.73M, role_permission 416K, role_hierarchy 389K, role_department 386K reads. Phase 1: added `authorizationCacheManager` (infra-cache, Redis DB 4, 24h TTL) + `@Cacheable`/`@CacheEvict` on the near-immutable role/role_permission/role_hierarchy/role_department DAO reads (keyspace bounded by role count, not traffic). Responses unchanged (cache below response-shaping layer). Both builds green (Java 17). NOT VERIFIED at runtime — needs infra-cache published + authorization dependency bump so `authorizationCacheManager` bean resolves; pushed, awaiting QA retest. Phase 2 (user_role_mapping working-set cache + targeted invalidation to stop the existing flushDb nuking ACTOR DB 3) pending.

---

`calculateAmountsForTransaction` folded `LOSSES_INT_WAIVED_AIR` into `LOSSES_INT_WAIVED` while `dcf_waived_partial_cycle` already carried the same post-death reporting-cycle accrual into `BLD_INT_WAIVED_AMT` → double-counted when `date_of_death` and DFC initiation (`dateOfReporting`) fall in different installment cycles. QA4 `6010335527` posted waive 99 vs expected 82 (+17). Removed the fold; short-gap cases unaffected (airWaiver clamps to 0; `6005361626`=81). Build green (Java 17). Pushed; awaiting QA retest.

---

## 2026-06-05 | `b546298f6` | accounting-v2 | feature/neft-v2-payment-reinit-qa-3.3.1.2 | Fix duplicate NEFT reinit client reference (BSTP_ERR_0004) — scope counter lookup to active leg

NEFT v2 payment-reinit regenerated a **stale `client_reference_number`** for the NEF/NEI legs, so HDFC rejected the re-attempt with `BSTP_ERR_0004` and the reinit stayed at `DTFC_SUCCESS`. Root cause: [`neftCounterLookupTransactionTypes(leg, reinit=true)`](../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/disbursement/util/DisbursementBankCallTypeUtil.java#L63) returned **all four** types (`NEF`, `NEF_REINIT`, `NEI`, `NEI_REINIT`), but the external-ref counter is **namespaced per leg prefix** (NEF=`07`, NEI=`08`). [`computeNextExternalReferenceNo`](../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/disbursement/util/ExternalReferenceNoUtil.java) takes the single latest row across the mixed set; when it belongs to the *other* leg, `extractCounterFromExternalReferenceNo` returns `1` on the prefix mismatch → the reinit leg regenerates `…02` and collides with the earlier attempt. Proven on QA3 `6009685830`: `NEI_REINIT` reused `…0802` (2×) and `NEF_REINIT` reused `…0702` (3×). Fix returns only the active leg `[type, type+_REINIT]` so the scanned rows and `legPrefix` are consistent and the counter increments monotonically per leg — mirrors the already-correct `neftV1CounterLookupTransactionTypes`. Build green (Java 17). Status: pushed; awaiting QA retest. (Separately diagnosed: getLoanAccountDetails `134139` for some GROUP enquiries is legacy `group_`-prefix data on pre-2025 loans, not a regression — no code change.)

---

## 2026-06-05 | `3eafa9dc98` | accounting-v2 | mfi_integration_v3.3.1.0.0 | SDCP-10199: close SHG/JLG parent when DFC closes the last active child

`DeathForeclosureInsuranceWriter.doParentPartPrePayment` hard-pinned the parent loan to `loan_status=ACTIVE` on every child DFC, with no check for "is this the last active child?" — so for SHG/JLG groups where the DFC'd child was the only/last active member, the parent stayed ACTIVE forever and never got an `la_closing_date`. RCA against QA3 group 387298 (parent 6002329725, children 6002330225 + 6002330226) confirmed: both children CLOSED, parent stayed ACTIVE with non-zero outstanding. Fix reuses existing `LoanAccountRepository.findAllByParentAccountExcludingCurrentLoan` (already filters `loan_status='ACTIVE'` AND excludes the current child by account_id) inside `doParentPartPrePayment` — 0 siblings still ACTIVE → set parent to CLOSED + stamp `la_closing_date = dateOfReporting`; otherwise keep ACTIVE (unchanged behaviour). Regression-safe: INDL loans early-return at `parentLoanAccountEntity == null`, every prior DFC test LAN (6007758026, 6007220925, 6006030630, 6005082732 etc.) was INDL so they don't enter this code path. For SHG groups where siblings remain ACTIVE the else-branch preserves existing behaviour exactly. Build green (`./gradlew build -x test`, Java 17). Pushed to origin only; awaiting QA retest. **Forward-merge needed for QA3 retest** — SIT is on 3.3.1.2, fix shipped to 3.3.1.0.0 (canonical for the DFC fix series); must propagate up through 3.3.1.0.1 → 3.3.1.1 → 3.3.1.2 before QA3 sees it. Bug 2 (`ChildLoanRestructuringProcessor.settleTillBalanced` looping infinitely when settling against already-closed children — parent OS stays non-zero) is a separate issue, not addressed in this commit.

---

## 2026-06-05 | `07ef5f6ac..bb1b78dbc` | accounting-v2 | sdcp-10172 (origin) | Isolate external_ref dedupe series onto SDCP-10172 (cut from tag 113)

`sdcp-10172` (upstream branch off `mfi_release_v3.3.1.0.0_113` = `2ede702e8`) was meant to carry ONLY the external_ref / entity_type disburse-dedupe work, with the DFC (SDCP-9301/9844) series that co-shipped in `mfi_integration_v3.3.1.0.0` (113→172) excluded. Cherry-picked the 9-commit dedupe block from `upstream/mfi_integration_v3.3.1.0.0` in order: `55e958cb3`(group_id↔loan_app_id collision) `cf2cd216a`(declare entity_type on disburseLoan) `93cd5bb18`(SHG scope by entity_type) `925ffc15a`(harden skip gate) `b69c88908`(Redis key entity_type segment) `0f0cab41d` `8e2467921`(consumer skip-gate simplify) `a9f8b5f63`(reinit skip gate) `bb1b78dbc`(=`d2b294d3b`: JPA Object[] false-dedupe `134139` fix — included deliberately so the series isn't shipped buggy, per [[feedback_jpa_object_array_return_trap]]). SDCP-10089 portfolio-transfer (`09b92deed`) and all DFC files correctly excluded — diff vs tag 113 = 8 dedupe files only (`ExternalRefLoanAccountLookup` new, `GetLoanAccountByExternalRefNumberProcessor`, `LmsMessageBrokerConsumer`, `ValidateDataForDisbursementProcessor`, `UpdateChildLoanDisbursementStatusProcessor`, `disburseLoan_requestTemplate.json`, `LoanAccountDAOService`/`Repository` dedupe-only hunks). Build green (Java 17). Pushed to **origin/sdcp-10172** only — upstream push boundary-forbidden + hard-disabled; forward-merge origin→upstream is the user's step. Status: pushed; awaiting QA retest.

---

## 2026-06-05 | `852ff85f6` | accounting-v2 | feature/neft-v2-payment-reinit-qa-3.3.1.2 | Restore reinit columns on getLoanAccountDetails (port of aefd53c4a missed on the -3.3.1.2 fork)

`getLoanAccountDetails` stopped returning the four NEFT-v2 payment-reinit keys on `feature/neft-v2-payment-reinit-qa-3.3.1.2`. Not a deletion — commit `aefd53c4a` ("Expose payment reinit columns…", 22 May, on the original `feature/neft-v2-payment-reinit-qa` @ `3ea207636e`) was never ported when the `-3.3.1.2` fork was cut over base `mfi_integration_v3.3.1.0.1` (`git merge-base --is-ancestor aefd53c4a HEAD` → false). Re-added across all layers: `LoanAccountRepository.getLoanAccountDetails` SELECT gains `reinit_disbursement_status`/`reinit_external_error_code`/`reinit_external_error_message` after `sanction_date`; [GetLoanAccountDetailsProcessor](../trustt-platform-accounting/src/main/java/in/novopay/accounting/account/loans/processor/GetLoanAccountDetailsProcessor.java) puts `parent_loan_account_id` [44] + the three reinit fields [46-48] into EC; [getLoanAccountDetails_responseTemplate.json](../trustt-platform-accounting/deploy/application/templates/response/product/getLoanAccountDetails_responseTemplate.json) declares all four SMPL fields under `loan_details`; plus the three `REINIT_*` constants on [LoanAccountConstants](../trustt-platform-accounting/src/main/java/in/novopay/accounting/account/loans/constant/LoanAccountConstants.java) (also absent on this fork). Column-index alignment verified programmatically: 49 SELECT cols, `has_child_accounts`=43, `parent_loan_account_id`=44, `sanction_date`=45, reinit=46/47/48. These run a parallel track to the unchanged `disbursement_status*` fields. Build green (Java 17). Status: pushed; awaiting QA retest.

---

## 2026-06-05 | `d2b294d3b` | accounting-v2 | mfi_integration_v3.3.1.0.0 | Fix disburseLoan false dedupe (134139) — external_ref Object[] lookup returned non-null empty array on no match

`ExternalRefLoanAccountLookup` blocked every brand-new SHG/group disbursement on QA5 with `134139` "loan already exists". Root cause is the JPA `Object[]` trap: [findLoanByExternalRefNumberUsingChildAccountFlag](../trustt-platform-accounting/src/main/java/in/novopay/accounting/account/loans/repository/LoanAccountRepository.java#L700) returned a single `Object[]` for a 3-column native query, and Spring Data adapts a multi-column projection as a collection — so **zero matches yield a non-null EMPTY `Object[]`, not `null`**. [loanExists()](../trustt-platform-accounting/src/main/java/in/novopay/accounting/account/loans/util/ExternalRefLoanAccountLookup.java#L21) used a bare `!= null`, so every absent `external_ref_number` read as an existing loan (verified on QA5: request refs `55566109`/`1345012`/`1344432`/`13455402` had 0 rows in `mfi_accounting.loan_account`, yet the parent check at `ValidateDataForDisbursementProcessor:130→156` threw). Fix: retype the finder + DAO wrapper to `List<Object[]>` and collapse to first-row-or-null via new `firstRowOrNull(...)`; guard the single-column `findOneByExternalRefNumber` fallback with `row.length >= 1`. The three column-reading callers (Kafka skip gate, ENQUIRY, child-status) already length-guard so were unaffected — only the validator's null-check path was wrong. Build green (Java 17). Status: pushed; awaiting QA retest.

---

## 2026-06-04 | `252881979` (accounting-v2) + `bef6fc27` (initial-setup) | accounting-v2 + initial-setup | feature/dpic-v1 | DPIC: integrate DPI/BPD across Part Prepayment, Death Foreclosure, Write-off and Loan 360 Overview

End-to-end DPI integration sweep across remaining UD §5.11/§5.12 touchpoints after foreclosure waiver. **Part Prepayment**: simple-field pattern (mirror bpi_amount, NOT the 6-field waiver block — part-prepayment has no user-side waiver model) — adds `bpd_amount` SMPL field to [loanAccountPartPrepayment_requestTemplate.json](../trustt-platform-accounting/deploy/application/templates/request/product/loanAccountPartPrepayment_requestTemplate.json) and [_approvalTemplate.json](../trustt-platform-accounting/deploy/application/templates/approval/product/loanAccountPartPrepayment_approvalTemplate.json); adds `bpdAmount` field + getter/setter to [LoanAccountPartPrepaymentDetailsEntity](../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/partprepayment/entity/LoanAccountPartPrepaymentDetailsEntity.java); `BPD_AMOUNT` constant on [LoanAccountPartPrepaymentConstants](../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/partprepayment/constant/LoanAccountPartPrepaymentConstants.java); persistence in both [CreateOrUpdateLoanAccountPartPrepaymentProcessor](../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/partprepayment/processor/CreateOrUpdateLoanAccountPartPrepaymentProcessor.java) (maker) and [LoanAccountPartPrepaymentProcessor](../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/partprepayment/processor/LoanAccountPartPrepaymentProcessor.java) (approval); EC put back in [PopulateLoanAccountPartPrepaymentDetailsProcessor](../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/partprepayment/processor/PopulateLoanAccountPartPrepaymentDetailsProcessor.java); V000194 in initial-setup adds the column. **Death Foreclosure**: [DeathForeclosureInsuranceWriter](../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/deathforeclosure/writer/DeathForeclosureInsuranceWriter.java) adds `LOSSES_DPI_WAIVED_AIR` + `LOSSES_DPI_WAIVED` EC keys (defaulted to 0 — BPD is already paid via DPI_AMT at line 331 so AIR loss is 0; non-zero values to be wired when DPI write-off cases emerge) plus two new `populateAdditionalAmountDetails` calls alongside the existing INT waivers so DCF GL rules can resolve the DPI loss legs. **Loan 360 Overview**: [getLoanAccountOverviewDetails_responseTemplate.json](../trustt-platform-accounting/deploy/application/templates/response/product/getLoanAccountOverviewDetails_responseTemplate.json) gains `dpi_paid_amount` + `dpi_due_amount` SMPL fields — the processor was already populating these EC keys (verified at `GetLoanAccountOverviewDetailsProcessor` 533/553/572 etc.) but the response template was dropping them. **Write-off**: `loanWriteoff` orchestration in [loans_orc.xml:1455](../trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml#L1455) adds the `DPI_AMT` populateAdditionalAmountDetailsProcessor next to PRIN_AMT/INT_AMT/FEE_AMT/PENALTY_AMT so the `LOAN_WRITE_OFF / FINAL_WRITE_OFF` GL rule can resolve the DPI write-off leg via `${DPI_AMT}`. **Reporting**: V001544 in initial-setup drops and recreates `mfi_reporting.soa_loan_account_payment_details` view to surface `lapd.dpi_amount` alongside the other component amounts (source column already added via V000188). Build green (Java 17). Status: pushed; awaiting QA retest.

---

## 2026-06-04 | `a2ab973f2` (accounting-v2) + `4d19d6a2` (initial-setup) | accounting-v2 + initial-setup | feature/dpic-v1 | DPIC foreclosure waiver: BPI-parity split for billed DPI and broken-period DPI (BPD)

Loan foreclosure (`loanPrepayment`) now treats DPI symmetrically with INT/BPI across validation, persistence, waiver application and posting placeholders. Request and approval templates ([loanPrepayment_requestTemplate.json](../trustt-platform-accounting/deploy/application/templates/request/product/loanPrepayment_requestTemplate.json), [loanPrepayment_approvalTemplate.json](../trustt-platform-accounting/deploy/application/templates/approval/product/loanPrepayment_approvalTemplate.json)) carry new `billed_dpi_details` and `bpd_details` CMPLX blocks mirroring `billed_interest_details` / `bpi_details` shape (6 fields each — due_amount, is_waived, is_fully_waived, waiver_percentage, waived_amount, amount_to_be_paid). [PrepaymentDetailsEntity](../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/prepayment/entity/PrepaymentDetailsEntity.java) gets 12 new persisted fields; [CreatePrepaymentDetailsProcessor](../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/prepayment/processor/CreatePrepaymentDetailsProcessor.java) parses both blocks into the entity. [V000193__add_dpi_waiver_columns_prepayment_details.sql](../`V000193__add_dpi_waiver_columns_prepayment_details.sql` (path retired — see initial-setup Flyway tree)) adds the matching `billed_dpi_*` and `bpd_*` columns to `prepayment_details`. [ValidateLoanPrepaymentDataProcessor](../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/prepayment/processor/ValidateLoanPrepaymentDataProcessor.java) parses both request blocks (null-safe so pre-DPI flows pass), extends the `pouplateLoanAccountAmountDetails` switch / `getTotalOverDueAmount` / `getTotalDueAmount` to count DPI rows in `loan_due_details`, computes broken-period DPI via `dpiAccrualDetailsDaoService.getUnbilledAccruedAmountTillDate`, and adds both to `prepaymentAmountDb` so the customer-side total reconciles. New DPI_DUE_AMOUNT / DPI_OVERDUE_AMOUNT / DPI_PAID_AMOUNT constants on [LoanAccountConstants](../trustt-platform-accounting/src/main/java/in/novopay/accounting/account/loans/constant/LoanAccountConstants.java). [UpdateDueDetailsForPrepaymentProcessor](../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/prepayment/processor/UpdateDueDetailsForPrepaymentProcessor.java) now applies `billed_dpi_waived_amount` to existing DPI rows in `loan_due_details` via the existing `processPendingInstallmentObject` pipeline (component="DPI") and applies `bpd_waived_amount` to the newly-created BPD row in `processDpiTillForeclosure`, with `waiver_details` + `waiver_loan_due_details` rows persisted via the same `saveWaiverDetails`/`updateLoanDueDetailsPaymentDTO` chain used for BPI. [PopulateAdditionalAmountAndAccountDetailsForForeclosureProcessor](../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/prepayment/processor/PopulateAdditionalAmountAndAccountDetailsForForeclosureProcessor.java) splits the previously-combined DPI value into `DPI_AMOUNT` (billed) and `bpd_amount` (broken-period) placeholders and registers `LOSSES_DPI_WAIVED_AIR` + `LOSSES_BILLED_DPI_WAIVED` next to the existing INT analogs. Build green (Java 17). Status: pushed; awaiting QA retest.

---

## 2026-06-02 | `116e371b4` | accounting-v2 | mfi_release_v3.5.0 | Resolve mfi_integration_v3.5.1 → mfi_release_v3.5.0 forward-merge conflicts

Two conflicts in the upstream forward-merge (PR `mfi_integration_v3.5.1` → `mfi_release_v3.5.0`). `DeathForeclosureInsuranceWriter.java`: release side carried only SDCP-8143 (Sec NPA reset block + 2 imports, rest whitespace) while integration carried the full DFC rework that had dropped the dead `updateLoanDueDetails` + `calculateBalanceInterest` methods — resolved by taking integration's deletion (no live callers; the `updateLoanDueDetailsProcessor` bean is unrelated) while preserving the auto-merged SEC NPA block. Proven: committed DFC writer == `integration_v3.5.1` byte-for-byte except the 6-line SEC NPA delta; and the DFC writer on 3.5.1 is itself byte-identical to the mainline-released `release_v3.3.1.1` (all 6 DFC-fix commits ancestors of both). `UpdateFailedSIPresentationListProcessor.java`: both branches made the same SI-customer-name refactor; integration was a strict superset adding `executionContext.putLocal("function_sub_code","HIERARCHICAL")` — kept the integration line, file now identical to `integration_v3.5.1`. Resolved in an isolated git worktree (`_wt-accounting-merge-350`); main `mfi_integration_v3.3.3` in-progress work untouched. Build NOT run (shared `platform-lib` checkout is on 3.3.1.1, not repointed) — correctness rests on content-equivalence + verified symbol availability. User pushes to upstream (boundary: no upstream push from this session).

---

## 2026-05-27 | `-` | accounting-v2 | mfi_integration_v3.3.3 | SDCP-10080 obs 4: parent waiver_details reconciliation

When a child loan foreclosure with principal waiver triggers `parentLoanAccountPartPrepayment`, the parent's foreclosure-date `loan_due_details` row receives `waived_amount > 0` and a matching `waiver__loan_due_details` line row (origin still under investigation — verifiably reaches this state) but NO `waiver_details` header. Reporting queries that join `waiver_details.loan_account_id → loan_account` then miss the parent's share of the waiver. Added a defensive reconciliation processor `EnsureWaiverDetailsForParentRescheduleProcessor` that runs after `callInternalOrchestrationProcessor` inside the `is_child_loan=true` block of `loanPrepayment do_prepayment` ([loans_orc.xml:2136](../trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml#L2136)). It iterates the parent's ldd rows for the foreclosure date with `waived_amount > 0`, and for each one without an existing approved `waiver_details` (checked via the existing `findAllByLoanAccountIdAndLoanDueDetailsIdAndWaiverStatus` DAO method) writes a new header row. Pure additive — skips when a header already exists, so no regression for the direct-waiver flows that already write both tables together. New native query `findWaivedDueDetailsByAccountAndDueDate` on `LoanDueDetailsRepository`. Build green (Java 17). Scope: child-foreclosure-with-waiver only (the `is_child_loan=true` Control). Held: obs 1, 2, 3 — awaiting product confirmation on catalogue-209 design + payment_details semantics + which ldd rows QA expects waiver to surface on.

---

## 2026-05-27 | `-` | docs | mfi_integration_v3.3.3 | SDCP-10080 child-foreclosure-with-waiver RCA + brain doc

RCA for SDCP-10080 (Issue in Loan Foreclosure) on QA2 — child 7000042524 (SHG product 104) foreclosed with 8 rs cash + 753 rs principal waiver against parent 7000035818. End-to-end trace + DB evidence shows six bugs: (1) TM 2003 catalogue-209 RSCH_LOAN_PREPAYMENT mirrors every customer-side leg of TM 2002 catalogue-117 LOAN_PREPAYMENT — cash GL over-debited by 8, waiver expense GL over-debited by 753, both catalogues share identical 17-rule expansion; (2) parent `loan_account_payments_details.amount=761` while child=8 (inconsistent semantics); (3) parent ldd 1703 paid/waived split is created by EC pollution; (4) `UpdateDueDetailsForPrepaymentProcessor.processForeclosureFee` writes a zero-amount FEE ldd row whenever a `foreclosure_fee` prepayment_charge_details record exists (no guard); (5) parent's `waiver_details` row is missing even though `waiver__loan_due_details` is written; (6) parent's future installments are silently reduced by the waived 753 with no per-installment waiver record. Underlying mechanism: `CallInternalOrchestrationProcessor.process:46-58` copies the full executionContext (shared+local) into the parent callee, so every reference code set during the child's appropriation leaks into the parent posting. New brain doc [`claude/runbooks/child-foreclosure-with-waiver.md`](runbooks/child-foreclosure-with-waiver.md) — full flow map, table-by-table writes, accounting-rule comparison, fix plan in 6 layers, first-SQL diagnostic. Indexed in [`runbooks/00-INDEX.md`](runbooks/00-INDEX.md). No code change; pre-fix design analysis.

---

## 2026-05-26 | `1f930f4451` | task | mfi_integration_v3.3.1.0.0 | Merge sdcp-9301-hotfix-3.3.1.0 (SDCP-DFC-OBS5)

Forward-merged feature branch `sdcp-9301-hotfix-3.3.1.0` into `mfi_integration_v3.3.1.0.0`. Origin was first fast-forwarded to upstream tip `b184b805` (carrying SDCP-9905/9923/9935 portfolio-transfer fixes). Single carryover: SDCP-DFC-OBS5 `@PreUpdate` hook on `TaskEntity` so `task.updated_on` is stamped on every UPDATE — fixes the DFC task rows that surfaced as stale when stages transitioned. Build green. Pushed to origin only; awaiting QA retest.

---

## 2026-05-26 | `abe401cf15` | accounting-v2 | mfi_integration_v3.3.1.0.0 | Merge sdcp-9301-hotfix-3.3.1.0 (DFC fix series)

Forward-merged feature branch `sdcp-9301-hotfix-3.3.1.0` into `mfi_integration_v3.3.1.0.0`. Origin was first fast-forwarded to upstream tip `9affbe78a` (latest 7539 PR + the SI customer-name fix + the foreclosure null guard). The feature branch ships the full Death Foreclosure correction series: SDCP-DFC-OBS1 (authoritative-row vs stale REJECTED), OBS3 (paid=total on closed loans), OBS4 (updated_on stamping on stage transitions), OBS6 (Reversed indicator after Loan Reopening), OBS9 (originating_office_id on DFC postings), plus the SDCP-9844 parent-DFC prepayment / death-cycle interest settlement / PRIN-bucket sourcing fixes and the SDCP-9301 partial-cycle DFC billing/waiver, BPP netting, double-BPI fix, overpaid-penal/fee BigDecimal-typing and pre-death INT exclusion. 15 files changed, +581/-204. Build green (`./gradlew build -x test`, Java 17). Pushed to origin only; awaiting QA retest.

---

## 2026-05-26 | `74c4b2f2a` | accounting-v2 | feature/dpic-v1 | DPIC: surface DPI on child-loan repayment, auto-closure, foreclosure APIs

Four UD-clear wire-format gaps where DPI was being computed but never reaching the consumer. (a) `childLoanRepayment` orchestration's manual additional-amount-details list dropped `DPI_AMT` while parent `loanRepayment` had it — meaning DPI accounting rules never fired for SHGDL/JLGDL child loan repayments; added the line in the same shape as INT_AMT/PENALTY_AMT/FEE_AMT. (b) Auto-closure's `checkAccountForAutoClosure` was deriving `unpaidIntAmount = outstanding - penal - fee - principal`, silently folding residual DPI into the INT amount → tolerance write-off posted DPI as `INT_AMT` and hit the wrong WOFF GL; now queries unpaid DPI separately, subtracts it explicitly from `unpaidIntAmount`, persists `UNPAID_DPI_AMOUNT` on the EC, and `processAutoClosureToleranceAmount` adds `DPI_AMT` to additional-amount-details. (c) UD §5.11 names two new foreclosure UI fields (Billed DPI, DPI Till Date of Foreclosure); `fetchLoanForeclosureSimulationDetails` template + processor now expose `billed_dpi` + `dpi_till_date_of_foreclosure` as flat keys (mirrors `billed_interest`/`bpi_amount` pattern). (d) `getLoanForeclosureDetails` processor was already putting `dpi_till_foreclosure_details` on the parent map but the template never declared it — added the matching CMPLX block. **Deferred to product clarification**: `billed_dpi_details` on the foreclosure-details API (the SQL row backing `billed_interest_details` needs a new column; need product to confirm Billed-DPI vs Till-Date split semantics + waiver eligibility) and Part Prepayment details API DPI field shape (UD silent on naming). Build green.

---

## 2026-05-26 | `354a21ab7` | accounting-v2 | feature/dpic-v1 | DPIC: surface DPI on getLoanAccountSummaryDetails + getLoanAccountStatement APIs

Web team flagged that both APIs returned no DPI fields even though the data was in the EC. Honest miss in my prior audit — I checked EC keys at the processor layer, never traced through to the response template, so the gap survived. Two changes (consistent with how PRIN / INT / FEE / PINT are wired today): (a) GetLoanAccountSummaryDetailsProcessor now has the DPI branch in the for-loop walking getLoanAccountAmountDueDetailsForSummary results (the query already projected DPI rows; we were dropping them) and initializes the DPI fields in initializeAmountFields; GetDpiAccrualDetailsProcessor collapsed to the interest-analogue pattern (only sets dpi_accrued_amount, the rest are summary-processor's job); response template gets the dpi_details CMPLX/MAP block matching interest_details shape with original_amount/accrued_amount/current_due_amount/waived_amount/paid_amount/overdue_amount/written_off_amount. (b) LoanAccountStatementRowMapper SELECT picks up lpd.dpi_amount (column has been on loan_account_payments_details since the DPIC schema landed) and the mapRow puts dpi_amount on the transaction_details map; response template adds dpi_amount SMPL field. Build green.

---

## 2026-05-26 | `a83ee1e25` | accounting-v2 | feature/dpic-v1 | DPIC: comment cleanup across the DPIC code paths

Comments-only pass across accrual / booking / billing / calc / scheme-config / Loan 360 surface / NPA movement / repayment appropriation. Rewrote each block to explain *why* the code does what it does in plain English, with UD section numbers kept only where they pin a non-obvious business rule. Removed dev-internal forward-references (Q1/Q3/Q4 planning items, "Rohit's task", "once X lands") that won't age well. Clarified the legacy-row fallback in RepaymentApproppriationProcessor and the post-maturity fallback in DpiBillingItemReader / DpiBillingBatchService. Loan 360 written-off DPI now documents that it's tracked on the GL side (INT ON UNPAID EMI WOFF) and reported zero here until a dedicated source is wired in. No behaviour change. Build green.

---

## 2026-05-26 | `5578dbd4a` | accounting-v2 | feature/dpic-v1 | DPIC: NPA suspense-AIR query covers first-NPA-before-first-billing

Audit before the user's release-readiness ask surfaced that the AIR-balance query for the NPA forward/reverse movement (DpiNpaMovementService.dpiAirAmount → DpiAccrualDetailsRepository.getDpiSuspenseAirAmountForNpa) was windowed on `start_date >= previous-DPI-due-date`. For any loan that goes NPA *before* its first DPI billing, no row exists in loan_due_details for DPI → `prevDpiDue` came back null → `fromDate = asOnDate` collapsed the window to today → earlier unbilled accruals were missed → AIR ON UNPAID EMI was left non-zero after the suspense move, breaking the trial balance. Switched the query to the posting-state flags directly (`accrual_posting_date IS NOT NULL AND billing_posting_date IS NULL`), dropped the fromDate parameter and the prevDpiDue lookup. Same result for the common case (loans with prior DPI billings; the start_date filter was redundant with the posting-flag filter in those scenarios), and the edge case is now correct. Build green.

---

## 2026-05-26 | `a3a96a7ee` | accounting-v2 | feature/dpic-v1 | DPIC: DPD anchor follows DPI per UD §5.5 — DPD ticks while DPI unpaid even after PRIN/INT knock-off

Product clarification: DPD continues to increase as long as DPI is unpaid; EMI knock-off (PRIN+INT only, UD §5.5 rule a) is independent. The existing DPD/Asset-Criteria anchor used `loan_installment_details.is_settled` which flips true on PRIN+INT settlement and so skipped any installment whose DPI was still outstanding — breaking the clarified rule. Added `getEarliestInstallmentDateWithUnpaidDpdComponents` on `LoanInstallmentDetailsRepository` (single SELECT, EXISTS sub-query on `loan_due_details` for component_type IN (PRIN,INT,DPI) where due_amount > paid+waived); replaced the 4 call sites (`LoanAccountDpdCalcProcessor`, `LoanAccountDpdCalcBatchProcessor`, `LoanAccountAssetCriteriaProcessor`, `LoanAccountAssetCriteriaBatchProcessor`) so both daily DPD recompute and NPA-start-date derivation now anchor on the earliest installment with any of PRIN/INT/DPI unpaid. Legacy `getInstallmentDateForDpdCount` left in place — no other callers. Also documented in `DpiAccrualCalculationItemReader` that UD §5.3 adds only 'Interest Frequency' + 'DPI Applicable' fields and DPI shares interest's `interest_calculation_days_in_month/year` (clarified vs. an earlier reading that DPI might have separate day-count config; rejected after re-reading the UD verbatim). Build green.

---

## 2026-05-24 | `482da613a` | accounting-v2 | sdcp-9301-hotfix-3.3.1.0 | DFC QA evidence — obs 6 — closure tab "Deposited" persists after Loan Reopening reversed the foreclosure

QA evidence: LAN 6005646333 was foreclosed 15 Apr 2026 and the foreclosure reversed via Loan Reopening on 16 Apr 2026 (loan_account_reopening_details row 5762 status=APPROVED); closure tab still showed "Deposited". Initial framing was wrong: I first thought QA might have used raw transaction reversal (which would be misuse). On verification: Loan Reopening WAS used and DID correctly set loan_account_closure_details.is_reversed=true on the FORECLOSURE row whose identifier_value matches the prepayment_details.id (row 30163, identifier_value=264357). The closure-tab UI processor (`GetLoanForeclosureDetailsProcessor`) was reading prepayment_details.prepayment_status (the request record, intentionally untouched by Loan Reopening because it's the foreclosure REQUEST not the closure-STATE) and mapping APPROVED -> "Deposited" without consulting the closure-state record. Fix: added `findReversedForeclosureIdentifierValues(List<Long> loanAccountIds)` on LoanAccountClosureDetailsRepository (single batched SELECT) and wired it into the processor — overrides `closure_status_value` to "Reversed" and adds `is_reversed=true` when the prepayment_details.id is in the reversed set. Read-only change, no DB migration, no reversal-flow change, no impact on Loan Reopening flow (which already does the right thing on the data side). Verified on QA4 against all 7 test LANs in the workbook: only 6005646333 picks up the override; other 6 byte-identical. Scope clarification: this displays the reversed state correctly; loan reactivation remains the Loan Reopening flow's responsibility (which sets loan_status=ACTIVE); raw transaction-reversal usecase is by design GL-only and does NOT reach this code path. Build green. Pushed; awaiting QA retest.

---

## 2026-05-24 | `255e84c3` | platform-task | sdcp-9301-hotfix-3.3.1.0 | DFC QA evidence — obs 5 — task.updated_on frozen at created_on on assignment / status changes

QA evidence (Vikram) showed task `updated_on` not advancing through DFC stage transitions. Reproduced widely on QA4: dozens of DFC tasks (Death Claim Initiation, Approval, Review, Download/Upload Death Claim Form) had `updated_on == created_on` despite multiple `task_activity` rows logged. Root cause: `TaskEntity` has manual `updatedOn` column with no JPA lifecycle hook, and most processors that mutate the entity (AssignTaskProcessor sets current_status + assignee; UpdateTaskStatusForTaskIdsProcessor batches; AssignTaskProcessor.process line 59-62) call `taskService.save(...)` without calling `setUpdatedOn(...)` first. The bug is systemic — 20+ save sites, including 2 in TaskPortfolioTransferService that bypass TaskDao and use `taskRepository.saveAll` directly. Fix: added `@PreUpdate void stampUpdatedOn()` to TaskEntity — JPA fires it on every UPDATE regardless of save path, so all current and future call sites are covered in one shot. Regression audit: 11 existing setUpdatedOn callers (CreateTaskDetailsProcessor [INSERT — PreUpdate doesn't fire], UpdateTaskProcessor, UpdateAooTaskDetailsNewApproverProcessor, UpdateTaskStatusForTaskIdsProcessor, TaskPortfolioTransferService, FinnoneCollectionTaskCreationConsumer, LogicalDeleteTaskDetailsProcessor, RejectTaskForCollectionProcessor, UpdateAssigneeContributorProcessor, UpdateDataCurrentTaskAndCreateNewTaskProcessor, CreateTaskByTaskCodeProcessor [INSERT]) all use `LocalDateTime.now()` — @PreUpdate stamps the same value, no behaviour change for them. Build green. Pushed; awaiting QA retest. Branch named to match accounting hotfix branch for symmetry.

---

## 2026-05-24 | `1c4d03436 40a142094 d30cbdf0f 9bce91265` | accounting-v2 | sdcp-9301-hotfix-3.3.1.0 | DFC QA evidence — 4 safe UI/audit fixes (obs 1/3/4/9 of the death-foreclosure QA workbook)

QA workbook (Death foreclosure — High level business scenarios.xlsx) raised 9 observations against DFC + 1 normal foreclosure. DB-verified each against QA4 and traced UI value → API → processor → DAO. Four are safe to fix in-branch alongside SDCP-9844; the rest are out-of-scope, wrong-per-evidence, or genuinely need a product call (mailback). **OBS1**: `DeathForeclosureDetailsRepository.findLatestOneByLoanAccountId` was `ORDER BY created_on DESC LIMIT 1` — for LAN 6005646333 it returned a REJECTED row (created 18:36) over the APPROVED row (created 12:43, id 26913) and the DFC details tab rendered rejected-attempt fields on a closed loan. Switched to semantic-first ordering: `CASE WHEN status='REJECTED' THEN 1 ELSE 0 END, created_on DESC, id DESC`. Avoids YugabyteDB sequence-cache id-order pitfall (per-session cache means lower id ≠ earlier insertion). Verified against all 7 test LANs in QA4 — only 6005646333 changes (now picks id 26913 APPROVED); other 6 unchanged. **OBS3**: `GetLoanAccountInstallmentDetailsProcessor` counted only `is_settled=true` rows — DFC closes mix settled + waived installments so a CLOSED loan showed "Paid 6/12" instead of 12/12. Added `if status==CLOSED: paid=total`. Mirrors the existing CLOSED branch at line 86 that already blanks next-installment fields. No change for DISB_CNCL/ACTIVE. **OBS4**: `ProcessDeathForeclosureAsPerStageProcessor` set status and called `saveOne` but did NOT touch `updated_on` for Stage 2/3/4/6 + re-upload — only Stage 5 INITIATED_INSURACE_CLAIM did. Confirmed in QA4: row id 27713 (LAN 6004560326, UPLOADED_DCF after 2 transitions) had updated_on == created_on. Threaded `valueDate` through each helper and set `setUpdatedOn(valueDate)` before every `saveOne`. Two readers of `getUpdatedOn` (GetDeathForeclosureDetailsProcessor reject_date, DeathForeclosureInsuranceWriter approved_on) still get the same value because Stage 5/reject already set updated_on themselves. **OBS9**: child DFC posting (DeathForeclosureInsuranceWriter line 517) and parent SHG/JLG RSCH_DEATH_FORECLOSURE posting (line 1079) were hardcoding `originating_office_id="1"` (Head Office) — anomalous: the same writer's forceBillSlice (line 1240) and syncBillingTillDate (line 1269) already use `loanAccountEntity.getOfficeId()`, and every other posting in the codebase (interest accrual, billing, closure, asset criteria) follows the loan's branch. Brought the two DFC postings in line. Mailback: obs 2 (paid_date — screenshot mismatches DB for supplied LAN), obs 5 (task.updated_on — task-service not accounting; current Review task advances correctly), obs 6 (foreclosure deposited-after-reversal — no FK from prepayment_details to transaction_master, fragile join required; recommend separate ticket with reversal-flow hook), obs 7 (DFC loan components blank — needs DFC writer to insert loan_account_payments_details row OR row-mapper SQL rewrite to aggregate TPD by reference_code; both have regression risk for collection/reporting), obs 8 (interest waived 1000 vs GL 81 — genuine semantic question: row-residual waiver vs GL-posted waiver; needs product call). Build `-x test` green. Pushed; awaiting QA retest.

---

## 2026-05-21 | `064c2f50e` | accounting-v2 | feature/dpic-v1 | DPIC v1 — billing due_date = NEXT installment (not the missed EMI)

`DpiBillingBatchService.processBilling` was creating the new `loan_due_details(DPI)` row with `due_date`/`overdue_date`/`loan_installment_details_id` set from the **overdue** installment (the one DPI accrued on), making the DPI immediately overdue from creation. Per UD v1.3 §5.4 + the calc-sheet (E18 accrued on missed EMI#1 → G19 billed on EMI#2 due date), DPI for a missed EMI must be **billed on the next installment's due date**. Fix: `DpiBillingItemReader` adds a `LEFT JOIN LATERAL` to project the next installment (`id`, `installment_date`) — first row with `installment_date > lid.installment_date` (the overdue installment's date). Service uses those for `due_date` / `overdue_date` / `loan_installment_details_id`; falls back to the overdue EMI when no next installment exists (post-maturity edge case). Reader filter and NPA detection unchanged. Build green; committed on feature/dpic-v1; not pushed; awaiting QA.

---

## 2026-05-21 | `d2f044ceb` (accounting-v2) `9de6dba9` (initial-setup) | feature/dpic-v1 | DPIC v1 — calc per UD/sheet, performant accrual reader, full NPA handling

DPI rate = loan `effective_rate` (ROI) per UD v1.3 §5.4 — the frequency-table `interest_setup_code`/`spread` are the existing loan interest config (already in effective_rate), not a DPI add-on, so no double-count. `DPICalculationService` day-count: DAYS360 for `DIM_30` / actual days for `DIM_ACTUAL` over `days_in_year`, percent ÷100, whole-unit rounding, grace in days. Accrual reader joins `product_scheme_frequency_details` and filters `dpi_applicable='YES'` at source (non-DPI loans never enter) and carries grace+day-count in-row, so the processor builds config from the row + one rate lookup — per-loan resolver round-trips dropped. NPA, per UD ("same logic as interest income"): `DPI_NPA_ACCRUAL` accrual sub-type + `INTEREST/DPI_NPA_BOOKING` in the billing job for NPA loans; new `loan/dpi/npa/DpiNpaMovementService` does the REGULAR↔NPA DPI income reclassification (forward `REGULAR_TO_NPA` / reverse `NPA_TO_REGULAR`, sub_type `DPI_INT_INCOME`; income leg from `loan_due_details(component=DPI)` + AIR leg from `dpi_accrual_details`, via reference codes `DPI_INT_AMT`/`DPI_INT_SUSPENSE_AIR_AMT`), invoked additively from the asset-criteria writer after the interest movement, no-op when the loan has no DPI. New DAO queries mirror the interest suspense queries with `component_type='DPI'`. initial-setup `49b32c18`: V000117 reduced to `DPI_GO_LIVE_DATE` only (V000119 is canonical for APPROPRIATION_LOGIC + DPI_APBL). Grounded in UD §5.4 + product calc sheet + QA4 existing-calc reference (loan_due_details component_type INT/PRIN/PINT/FEE → DPI analog). Product setup still required: GLs + accounting rules incl. the `DPI_INT_INCOME` reference codes. `build -x test` green. Committed to feature/dpic-v1; not pushed; awaiting QA.

---

## 2026-05-21 | `6dc5c3e44` | accounting-v2 | sdcp-9301-hotfix-3.3.1.0 | SDCP-9844 — settle death-cycle recovered interest on the row (fixes stale DPD on closed DFC loan)

LAN 6010574225 closed via DFC (overdue 0, excess 0, Standard slab) but UI showed Days Past Due = 4. Verified end-to-end on QA4. The death cycle (2026-10-02..2026-11-02, billed INT 215) was unpaid at death (2026-10-28); `calculateLossInterestWaived` waived only the post-death sliver (36), and the `deathCycleBilled` branch set `dcf_recovered_partial_cycle = 179` (the pre-death portion to recover). That 179 was published **only** to the GL leg `BLD_INT_AMT (= INT_AMT + dcf_recovered_partial_cycle)` — recovered into income at GL — but was **not** added to the `interest` bucket fed to `appropriateDeathForeclosure`, so the Nov-2 INT row's `paid_amount` was never bumped → row stayed pending 179. `loanAccountDpdCalcProcessor` (writer line 563) runs **before** the loan is marked CLOSED (line 570), sees the pending row, counts `business_date(2026-11-05) − 2026-11-02 = 4` → `past_due_days = 4` persisted; closure never resets it. Same GL-settles-but-row-doesn't class as the earlier PRIN gap. Fix: add `dcf_recovered_partial_cycle` to the `interest` appropriation bucket (child/individual path, line 484) so the row is settled, mirroring `BLD_INT_AMT`. Row passes the INT date-gate because `isGapInterestApplicable` is true on the death date; `dcf_recovered_partial_cycle` is a String (toPlainString) so `LoanUtil.getBigDecimalValue` is correct; `getCurrentPaidAmount` caps at pending so it can never over-settle (safe in both deathCycleBilled branches). GL posting untouched — reference codes captured into `additional_amount_details` before appropriation runs. Parent SHG/JLG path (line ~1033) left untouched, not in evidence. Regression: LAN 6005633825 had death-cycle INT fully paid → recovered 0 → fix adds 0, no change; already closes with DPD 0. Survey shows ~8 recent DFC'd LANs carry stale DPD from this + the earlier INT-zombie gap. Build green. Pushed; awaiting QA retest.

---

## 2026-05-21 | `69bdca5655` | actor | mfi_integration_v3.3.1.1 | perf — cache office basics in getOfficeCodeAndNameByIds (cross-service hot path)

`getOfficeCodeAndNameByIds` was a heavy cross-service hot path (accounting loan-overview / transaction-export / trial-balance EOD / GL/CBS / internal-account list, LOS renewal-groups, reporting) that hit the `office` table on every call and hydrated the full `OfficeEntity` (~155 columns) to read 4 fields. Office basics rarely change. Fix: new `OfficeBasicsCacheUtil` on Redis ACTOR DB 3, tenant-scoped, **no TTL** (matching the platform reference-data pattern in `ProductDAOService` / `ProductSchemeDAOService` / `PlaceholderMasterDAOService` and masterdata caches — invalidate-on-write, not time-based). Caches a 4-field `OfficeBasics` projection. `GetOfficeListByIdsProcessor` partitions requested ids into cache-hits and cache-misses, fetches only the misses through the **existing** `findAllByIds` query (no new query, no DB `ORDER BY`, no input cap), populates cache, builds same response. Invalidation hooks added in `UpdateOfficeProcessor`, `LogicalDeleteOfficeProcessor`, and `OfficeUpsertPersistenceService` (per-row in the bulk loop) — every code path that mutates `formatted_id` / `name` / `external_branch_code` is covered. `CreateOfficeProcessor` doesn't need a hook (new id, nothing cached). Verified `PopulateCorporateIdProcessor` and `CreateOrUpdateOfcToWrkAreaMappingProcessor` don't touch the 4 cached fields. All 8 cross-service callers verified to read the same fields under `office_details` — response contract byte-identical. Build green. Pushed; awaiting QA retest.

---

## 2026-05-21 | `04cd5bdbf1` | actor | mfi_integration_v3.3.1.1 | perf — cache role lookup + bound contact read in getUserBasicDetails (OOM amplifier)

`getUserBasicDetails` was hammering authorization via a **synchronous, uncached** `getRoleDetailsByUserId` HTTP call on every request and following it with an unbounded `SELECT contact_detail_id FROM actor__contact_detail__mapping WHERE actor_id=? AND is_deleted=false` plus a second `findOne` on `contact_detail`. The auth round trip was the OOM amplifier — request threads parking on the HTTP call accumulated, each retaining its ExecutionContext / persistence context / response buffers on the heap. Fix: new `UserRoleCacheUtil` (Redis ACTOR DB 3, 15-min TTL, tenant-scoped key `actor_user_role_details_v1_<user_id>`); processor checks cache before the HTTP call, populates on miss. `setContactDetails` now **reuses the existing `findAllByActorId` finder** (no new query, no DB ORDER BY — sort/select is done in Java by max id) which both removes the second SQL round trip's risk of `IncorrectResultSizeDataAccessException` and avoids pushing a per-request sort to the DB. Invalidation hooks added to `UpdateEmployeeRoleProcessor` (post-`updateUserRoleMapping` call) and `LogicalDeleteUserProcessor` (end of user logical delete). Out of scope: any change to authorization service itself — it already caches role/user mapping at its DAO layer. Build green. Pushed; awaiting QA retest.

---

## 2026-05-21 | `e433b74cd` | accounting-v2 | sdcp-9301-hotfix-3.3.1.0 | SDCP-9844 — source DFC PRIN settlement bucket directly from loan_due_details

Replaced the EC-algebra `principalForSettlement = principal + dcf_overpaid_penal + dcf_overpaid_fee` (which worked but required unwinding 5 layers of writer/service arithmetic to convince oneself it equals the gross obligation) with a direct call to the existing `loanDueDetailsDAOService.getPrincipalOutStandingAmount(loanAccountId)`. That method returns `SUM(due − paid − waived)` across all PRIN rows where `is_deleted = false` — exactly the row-side obligation `appropriateDeathForeclosure` must clear. **No new repo query** introduced (method exists at `LoanDueDetailsRepository:272-274`). GL legs unchanged — they still derive from the netted EC keys via the `populateAdditionalAmountDetails` block earlier in the method (`UNBLD_PRIN_AMT`, `BLD_PRIN_AMT`, `EXCESS_ACCOUNT_INC_AMT` all computed before bucket assembly). `calculateTotalTransactionAmount` and `populateAdvanceSrcAmount` both run before the new bucket call, consume EC keys, also unchanged. GL CR LOAN_ACCT (= UNBLD_PRIN + EXCESS_ACCOUNT_INC) still equals gross PRIN obligation, matching this bucket exactly. `waiveFutureInterestPastReporting` moved up 4 lines so the waive runs before bucket assembly — reads more naturally; correctness unchanged. Verified same value (20072) for both QA4 LANs with the original gap. Build green. Pushed; awaiting QA retest.

---

## 2026-05-21 | `f1aba037f` | accounting-v2 | sdcp-9301-hotfix-3.3.1.0 | SDCP-9844 — hotfix ClassCast on dcf_overpaid_penal/fee in just-pushed PRIN settlement patch

The just-pushed PRIN-settlement patch (895138db4) added `LoanUtil.getBigDecimalValue(executionContext, "dcf_overpaid_penal_amount")` and the matching FEE call inside `calculateAmountsForTransaction`. Service stores those two as `BigDecimal` (not `String`); `LoanUtil.getBigDecimalValue` does `(String) ec.get(...)` and blows up at runtime — same trap as commit `29d81052e` which existed to fix this exact key, and **I have a memory rule for it**. Caught on second-read of my own diff (user prompted "are you sure?"). Fix: switch both reads to `executionContext.getValue(key, BigDecimal.class)` with a null→ZERO guard (mirrors the safe pattern at line 444–451 in the same writer). Settlement math unchanged: `principalForSettlement = principal + overpaidPenal + overpaidFee`, GL legs unchanged. Memory `feedback_executioncontext_type_symmetry` updated with the specific BigDecimal-typed `dcf_*` keys and a "this was the second time I hit it" reflection. Build green. Pushed; awaiting QA retest.

---

## 2026-05-21 | `895138db4` | accounting-v2 | sdcp-9301-hotfix-3.3.1.0 | SDCP-9844 — settle PRIN to gross obligation + waive INT past dateOfReporting

QA4 LAN 6005646329: DFC closes the loan (excess=0, overdue=0) but `loan_due_details` shows PRIN outstanding 200 and INT outstanding 743. Traced two distinct DFC-writer bugs against verified QA4 data on 15 DFC'd LANs. **(1) PRIN under-settled by `overpaidPenal + overpaidFee`:** service computes `dcf_pos_amount = futurePrincipal − totalOverpayment` (correct for GL — insurance shouldn't reimburse customer's overpayment), writer carries that netted POS into the principal bucket fed to `appropriateDeathForeclosure`. GL stays balanced because `EXCESS_PINT_AMT → EXCESS_ACCOUNT_INC_AMT` credits the loan account by the overpaid amount — but no row-side step settles the extra obligation, so the last PRIN row gets short by exactly the overpayment. Hit 2 of 15 LANs (6005646329 & 6006129425, both 200). **(2) INT rows past `dateOfReporting` orphaned:** legacy `updateLoanDueDetails` helper soft-deleted all INT/PINT rows past `dateOfReporting` after DFC; commit 156ee3ba2 removed it and replaced PINT with full waive but only handled INT in `(deathDate, dateOfReporting]` via `calculateLossInterestWaived`. Rows past reporting are now never touched → permanent zombies (11–4096 ₹ per LAN, all 15 LANs, total ~19k). Fix: build a separate `principalForSettlement = principal + overpaidPenal + overpaidFee` for appropriation only (GL legs untouched, insurance receivable still correct); add `waiveFutureInterestPastReporting` helper that full-waives INT rows with `due_date > dateOfReporting` via the existing `waiveLonaDueDetailsEntries` path so `loan_due_details` matches GL after DFC. Build green. Pushed; awaiting QA retest.

---

## 2026-05-21 | `a82be35c8` | accounting-v2 | mfi_integration_v3.3.1.0.1 | enable NEFT v1; cut NEFT v2 QA feature branch
Flipped `DisbursementBankCallConstants.USE_NEFT_V1` from `false` → `true` on the production-bound branch `3.3.1.0.1`. NEFT v2 is being released to QA on a separate feature branch `feature/neft-v2-payment-reinit-qa` (pushed at `8323668ce`, cut from the pre-flip tip — carries all the NEFT v2 reinit fixes: `currentReinitStatus` fresh-read, mode-detail rewrite skip on reinit, and the `isReplayWithoutFreshModeUpdate` guard removal). Build green. Pushed; awaiting QA retest.


## 2026-05-20 | `e6d107d24` | accounting-v2 | sdcp-9301-hotfix-3.3.1.0 | SDCP-9301 — stop double-adding BPI to outstanding when customer's overpayment covers it (and revert paid>0 filter)
LAN 6005646333: posted outstanding 21,824 vs expected 21,558 (diff 266 = full partial-cycle BPI). Real root cause: `outStandingLoanBalance` was computed as `futurePrincipal − totalOverpayment + BPI`, where `extraInterest = paid − scheduled − BPI` already nets BPI out of the overpayment side. When customer's overpayment covers BPI fully, re-adding BPI to the outstanding double-counts it. The user spotted that the 820 INT row on this LAN was `is_deleted=true` AND this loan was foreclosed→reopened — verified the DAO query already filters `is_deleted=false` in its SQL, so the previous "paid>0 filter" commit (5281b87c5) was a no-op for this LAN and would have broken the legitimate-default case (active row with paid=0 belongs in customer obligation, not excluded). Fix: revert the paid>0 filter; expose `rawSurplus = max(paid − scheduled, 0)` from `calculateExtraInterestAmountPaid` via execution context; add only `max(BPI − min(rawSurplus, BPI), 0)` to outstanding so partial coverage works too. Math now matches all three known LANs end-to-end: 6005646333→21558, 6006129425→19996, 6007758029→3827. Build green. Pushed; awaiting QA retest.

---

## 2026-05-20 | `5281b87c5` | accounting-v2 | sdcp-9301-hotfix-3.3.1.0 | SDCP-9301 — extra-interest-paid: skip unpaid pre-death INT rows from obligation (handles NPA/correction-accrual outlier rows) [REVERTED in e6d107d24]
QA hit on LAN 6005646333 where outstanding loan balance came out 21,824 vs expected 21,558 (diff 266 = 53 INT overpayment + 200 PINT overpayment + 13 partial). Root cause: this LAN has an extra INT row (id 9699980, due 820, paid 0, created 4 days post-disbursement — likely an NPA/correction accrual). Both the legacy logic and the prior fix counted that 820 as customer obligation, so paid (3834) < obligation (3515 + 820 + 266 BPI = 4601), extraInterest returned 0 and the 53 genuine overpayment from the post-death-cycle advance payment was hidden. Fix: skip pre-death INT rows with `paid_amount = 0` from the obligation sum. Those unpaid rows are already recovered via the existing `BLD_INT_AMT` leg (INT_AMT context value sums `due − paid − waived`), so excluding them from the overpayment denominator prevents double-counting without losing the recovery. Math verified on three LANs (6005646333: 53, 6006129425: 59, 6007758029: 8) — all match QA's expected values. Build green. Pushed; awaiting QA retest.

---

## 2026-05-20 | `244809daa` | accounting-v2 | sdcp-9301-hotfix-3.3.1.0 | SDCP-9301 — extra-interest-paid now counts payments across all INT rows (advance death-cycle paid was missed)
QA hit on LAN 6006129425 where customer overpaid INT by 59 but system posted no `EXCESS_INCOME_INT_AMT` leg and `UNBLD_PRIN_AMT` came out 20055 instead of 19996. Root cause: legacy `calculateExtraInterestAmountPaid` called `getAllNextLoanDueDetailsForComponentTypeBetweenDates` which filters `due_date > startDate AND due_date <= deathMinusOne` and then summed both paid and due over that filtered set. Customer had pre-paid the death-cycle EMI (row due 2026-11-03, paid 296) — since 2026-11-03 > deathMinusOne 2026-10-27, that paid never entered the settled total. Settled was 3206, owed 3206 + 237 BPI = 3443, helper returned 0. Fix: switch to `getAllNextLoanDueDetailsForComponentType` (no upper-date bound) and sum paid across all rows from disbursement onwards, while keeping the owed side filtered by `due_date <= deathMinusOne` to preserve the pre-death-only owed semantics. Verified on QA4: 6006129425 now yields extraInterest = 3502 − 3443 = 59; 6007758029 still yields 8 (no regression). Build green. Pushed; awaiting QA retest.

---

## 2026-05-20 | `29d81052e` | accounting-v2 | sdcp-9301-hotfix-3.3.1.0 | SDCP-9301 — hotfix ClassCastException reading dcf_overpaid_* keys in DCF writer
Job failed at runtime with `ClassCastException: BigDecimal cannot be cast to String` at `DeathForeclosureInsuranceWriter.calculateAmountsForTransaction:444`. The service stores `dcf_overpaid_penal_amount` / `dcf_overpaid_fee_amount` as `BigDecimal` objects but the writer was reading them via `LoanUtil.getBigDecimalValue` which does `(String) executionContext.get(key)`. Switched both reads to `executionContext.getValue(key, BigDecimal.class)` with a null→ZERO guard (matches the pattern already used for `dcf_extra_int_paid_amount` at line 322). Build green. Pushed; awaiting QA re-run.

---

## 2026-05-20 | `d1a6ff057` | accounting-v2 | sdcp-9301-hotfix-3.3.1.0 | SDCP-9301 — adjust overpaid penal/fee against principal + recover unpaid pre-death billed interest
Two related GL-amount fixes after Product clarified that overpaid interest/LPP/fee is adjusted against principal via the excess GL. (1) **Overpayment (acct 6007758029):** service now computes `dcf_overpaid_penal_amount` and `dcf_overpaid_fee_amount` by iterating the existing component due-rows (total paid across all rows minus owed for rows due_date <= deathDate) and folds them into the netPos subtraction so `outstanding_loan_balance` / claim_amount reflect the adjustment. Writer pushes them under the new reference codes `EXCESS_PINT_AMT` and `EXCESS_CBC_FEE_AMT` (Product to add the corresponding rule legs: DR PENAL / CR EXCESS_ACCT and DR CBC_CHARGE / CR EXCESS_ACCT); existing `EXCESS_ACCOUNT_INC_AMT` now carries the combined overpayment so the existing DR EXCESS_ACCT / CR LOAN_ACCOUNT leg moves the full surplus to principal. (2) **Billed-interest recovery for unpaid death cycle (acct 6006030629):** when the death cycle is already billed but its interest is unpaid, `recoveredPartialCycle` is now `min(deathCycleUnpaidInt, preDeathBpi)` instead of 0 — the pre-death portion is recovered (post-death portion is already added to LOSSES_INT_WAIVED by `calculateLossInterestWaived`). No new DAO queries; reuses existing list methods with Java-side summation. Build green. Pushed; awaiting QA retest after Product/QA add the two new rule legs.

---

## 2026-05-15 | `e6d912523` | accounting-v2 | sdcp-9301-hotfix-3.3.1.0 | SDCP-9301 — DFC penal/fee waiver waives only the pending amount
`waiveLonaDueDetailsEntries` set `waivedAmount = full dueAmount` and recorded a waiver for the full due, ignoring `paid_amount` / existing `waivedAmount`. When a post-death PINT/FEE row was already (partly) paid, the paid portion was waived a second time — the row over-settled and a bogus `PINT_AMT_WAIVED`/`CBC_FEE_AMT_WAIVED` leg posted for money actually collected (QA4 LAN 6007758029: 200 penal overpaid, posted as a 200 waiver). Now waives only `pending = due − paid − waived` and skips rows with nothing pending — matching the INT path. Build green. Pushed; awaiting QA retest.

---

## 2026-05-15 | `1ec54afd2` | accounting-v2 | sdcp-9301-hotfix-3.3.1.0 | SDCP-9301 — fix DFC when billing has run past the death date
When the DFC job runs weeks after death, `loanAccountBillingJob` has already raised post-death installments — the writer wrongly assumed billing stops at death. **Symptom A** (LAN 6007758026: force-bill 47 vs 4; 6007220925: 55 vs 0): `forceBillSlice` applied `.max(preDeathBpi)` unconditionally, re-billing the BPI of an already-billed cycle. Fixed with `isDeathCycleBilled()` (checks `loan_account_billing_details` for the death-cycle installment) — on the billed branch `.max` is dropped and `recovered=0`, so only the genuinely un-billed accrual is force-billed. **Symptom B** (LAN 6007220925: `BLD_PRIN_AMT` 1674 vs 3306): `getUnpaidBilledPrincipal` keyed the billed/unbilled split on `loan_due_details.due_date` vs the death date, misclassifying billed-but-pre-death-due principal as unbilled. Replaced with `getUnpaidBilledPrincipalForDeathForeClosure` (new query — PRIN due-details with a non-reversed `loan_account_billing_details` row; `loan_due_details` row alone ≠ billed, the join IS required); overdue `PRIN_AMT` folded into the split and zeroed so `calculateTotalTransactionAmount` doesn't double-count. Scenario matrix verified (death-before-billing / same-cycle / cross-cycle — no regression to 6007569035/6007220926). Both reported loans are CLOSED so the `BLD_PRIN_AMT`=3306 split can only be confirmed by a fresh QA run. Build green. Pushed; awaiting QA retest.

---

## 2026-05-15 | `7dad5048a` | accounting-v2 | sdcp-9301-hotfix-3.3.1.0 | SDCP-9301 — revert `5accce4e8` (parent RSCH_DEATH_FORECLOSURE old-schema rebuild)
`5accce4e8` rebuilt the parent posting's `additional_amount_details` with **old-schema** codes (`INT_AMT`/`POS`/`BPI_AMT`/…) because catalogue 428 (`RSCH_DEATH_FORECLOSURE`) was still old-schema on QA4. Confirmed with product: catalogue 428 **will be migrated to the new schema** (same `source_amount` set as catalogue 22 — `BLD_INT_AMT`/`UNBLD_PRIN_AMT`/`PINT_AMT`/…) on QA4 **and** production, before/with this build. Once 428 is new-schema, the writer's bridge block already produces exactly those codes and the parent posting inherits that list correctly — so `populateParentAdditionalAmountDetails` would send the **wrong** (old) codes and re-break the parent posting. Reverted it (27 lines removed). Parent path now reuses the child's new-schema list — correct for new-schema 428. **Release dependency: this build MUST deploy together with the catalogue-428 → new-schema migration; deploying either alone breaks group-loan DFC.** Build green. Pushed; awaiting QA retest.

---

## 2026-05-15 | `5accce4e8` | accounting-v2 | sdcp-9301-hotfix-3.3.1.0 | SDCP-9301 — fix near-empty parent RSCH_DEATH_FORECLOSURE GL posting
Commit `42d551622` rewrote the DFC bridge block to push **new-schema** reference codes (`BLD_INT_AMT`/`UNBLD_PRIN_AMT`/`PINT_AMT`/…) for the child `DEATH_FORECLOSURE` posting. `doParentPartPrePayment` then posts `RSCH_DEATH_FORECLOSURE` (catalogue 428, still **old-schema**: `INT_AMT`/`BPI_AMT`/`POS`/`PENAL_AMT`/`FEE_AMT`/…) and inherited the child's new-schema `additional_amount_details` list unchanged. The posting engine resolves rule amounts by case-sensitive EC key lookup (`ExecuteTransactionRulesProcessor`); the old-schema keys were absent → every economic leg resolved to `null` and was silently dropped (no exception) → the parent group-loan GL posting was near-empty, parent outstanding not settled. Added `populateParentAdditionalAmountDetails`: clears the inherited list and rebuilds it with the old-schema codes catalogue 428 expects (the exact set emitted pre-`42d551622`). Standalone-loan path untouched (`doParentPartPrePayment` early-returns when no parent). Restores pre-regression parity. Build green. Pushed; awaiting QA retest.

---

## 2026-05-15 | `d4cead5eb` | accounting-v2 | mfi_integration_v3.3.1.0.1 | remove unsound replay guard blocking repeat payment reinitiation
`isReplayWithoutFreshModeUpdate` in `CallBankAPIForDisbursementProcessor` skipped the reinit bank call (`MFI-40005`) whenever `loan_disbursement_mode_details.updated_on` was not after the latest `_REINIT` CRR `system_date`. Premise — every fresh reinit bumps `updated_on` — is false: LOS updates mode details only when the account actually changes (not mandatory for reinit). Effect: the 1st reinit passed (no prior `_REINIT` CRR), but the **2nd and every subsequent reinit on an unchanged account** was misclassified as a duplicate replay and silently dropped — no bank call. Real duplicates are still caught by the `reinit_disbursement_status` CAS reset, the `REINIT_COMPLETE` block, inquiry-before-transfer, and the monotonic external-ref counter, so the guard was redundant. Removed the call + the method (39 lines). Build green. Pushed; awaiting QA retest.

## 2026-05-15 | `e8fc6c4a5` | accounting-v2 | mfi_integration_v3.3.1.1 | remove temp `[reinit-debug]` logging — RCA complete
Removed the temporary `[reinit-debug]` logging added by `b982025ff` during the NEFT v2 reinit RCA. Restored `DisbursementBankCallTypeUtil.java` and `ParentDisbursementNeftV2BankCall.java` byte-identical to `origin/mfi_integration_v3.3.1.0.1` (the clean production branch). Pure logging removal — no functional change: the logging-only locals (`primaryDisbursementStatusFromEc`, `reinitFlagAtBankCall`, `accountIdInEc`) and the inlined `isPaymentReinitiationTransferExecution` body collapse back to the original logic. Converges `3.3.1.1` with the lower branch so future forward-merges stay conflict-free. Build green. Pushed; awaiting QA retest.

## 2026-05-15 | `c523eb6f2 9085b5337` | accounting-v2 | mfi_integration_v3.3.1.0.1 | repeat NEFT v2 reinit — two follow-up fixes
(1) `c523eb6f2` — `currentReinitStatus` read stale: it loaded the L1-cached `LoanAccountEntity`, so after the repeat-reinit reset CAS (native `@Modifying` in `REQUIRES_NEW`) committed `COMPLETED→DTFC_SUCCESS`, the same-orchestration re-read still saw `COMPLETED` → `REINIT_COMPLETE` fired → no bank call (QA3 LAN 6009685830). Fix: new native scalar query `findReinitDisbursementStatusByAccountId` — projection result bypasses L1 cache → reflects the committed CAS. (2) `9085b5337` — `updateDisbursementModeDetailsProcessor` re-wrote `loan_disbursement_mode_details` from the disburseLoan request body during reinit, redundant + can clobber LOS-set values (LOS already persists them via the dedicated `updateDisbursementAccountDetails` API before triggering reinit). Fix: skip the overwrite+save when `isPaymentReinitiationTransferExecution`, only publish `disbursement_details_id`. Non-reinit flows unaffected. Build green. Pushed; awaiting QA retest. Forward-merge note: the `currentReinitStatus` change will conflict on merge to `3.3.1.1` with `b982025ff`'s temp debug logging in that method — resolve by taking this clean version.

## 2026-05-15 | `8400b8dd9 eab178a17 b3325612b` | accounting-v2 | mfi_integration_v3.3.1.0.1 | port NEFT v2 reinit fixes to production branch
Cherry-picked the three NEFT v2 payment-reinitiation fixes from `3.3.1.1` onto `mfi_integration_v3.3.1.0.1` (the branch shipping to production first): `function_sub_code` leak restore in `DisbursementCustomerNameHelper`, inquiry-on-STAGE_1_PENDING wiring + STAGE_1 CAS, and the `REINIT_COMPLETE` repeat-reinit reset. Cherry-pick (not fresh re-apply) chosen so the code is byte-identical to `3.3.1.1` — dry-run forward-merge `3.3.1.0.1`→`3.3.1.1` confirmed zero conflicts. Debug-logging commit `b982025ff` intentionally NOT ported (stays on `3.3.1.1` for QA only). Build green. Pushed; awaiting QA retest.

## 2026-05-15 | `8187a4f9e` | accounting-v2 | mfi_integration_v3.3.1.1 | repeat NEFT v2 payment reinitiation
`CallBankAPIForDisbursementProcessor`: a completed reinitiation left `reinit_disbursement_status=COMPLETED`, so a genuine second reinitiation was blocked by the `REINIT_COMPLETE` short-circuit (`MFI-40005`). Fix: before the inquiry block, for an explicit NEFT v2 reinit at `reinit_disbursement_status=COMPLETED`, CAS-reset COMPLETED → DTFC_SUCCESS (clears stale reinit error fields) to start a fresh cycle; inquiry skipped for the reset cycle. NEFT v2 only (`!ACCTWB`); MFT untouched; `isReplayWithoutFreshModeUpdate` untouched. QA3 LAN 6009685830. Pushed; awaiting QA retest.

## 2026-05-15 | `f43650205` | accounting-v2 | mfi_integration_v3.3.1.0.0 | foreclosure APPROVE_TASK NPE
`ValidateLoanPrepaymentDataProcessor.setExcessAmount()`: add fallback query (`findOneByLoanAccountIdAndPrepaymentStatus`) for APPROVE_TASK when primary `(PENDING,PENDING)` query returns null — mirrors existing `GetPrepaymentDetailsProcessor` pattern; prevents NPE when a prior partial APPROVE_TASK attempt left `task_status=APPROVED` in DB.

---

## 2026-05-15 | `72ed389a3` | accounting-v2 | SDCP-9301 (DFC slice — death-day gap)
`DeathForeclosureInsuranceWriter`: `forceBillSlice` was `preDeathBpi + computeUnbilledPartialCycleAccrual` — two windows that did not meet (preDeathBpi → death-1, partialCycleAccrual = accrued(reporting)−accrued(deathDate) → death+1 on), so the **death day's own interest** fell in the gap and was dropped (LAN 6007569035: force-bill 375/waiver 28 instead of 389/42). Now `forceBillSlice` = a single `calculateInterestTillDateUsingReducingBalanceForDeathForeclosure(reportingDate)`; `recovered = preDeathBpi`; `waived = forceBillSlice − recovered` — `recovered + waived == forceBillSlice` by construction. Deleted the now-unused `computeUnbilledPartialCycleAccrual`.

---

## 2026-05-15 | `f5315f7a0` | accounting-v2 | SDCP-9301 (DFC slice split)
`DeathForeclosureInsuranceWriter`: split the force-billed partial-cycle slice — pre-death BPI (interest up to death-1) recovered via `BLD_INT_AMT`, post-death accrual waived via `BLD_INT_WAIVED_AMT`. `274ba786b` recovered the full slice and overshot `outstanding_loan_balance`; the split makes the DFC posting total equal `outstanding_loan_balance` and nets GL `BILLED_INTEREST` to zero.

---

## 2026-05-15 | `274ba786b` | accounting-v2 | SDCP-9301 (DFC posting amount)
`DeathForeclosureInsuranceWriter`: add the force-billed partial-cycle interest slice (`dcf_partial_cycle_accrual`) to `BLD_INT_AMT` and `calculateTotalTransactionAmount` — the DEATH_FORECLOSURE posting was short by the slice (e.g. 5204 vs `outstanding_loan_balance` 5263), leaving a standing debit in GL 13336 and under-recovering from insurance.

---

## 2026-05-15 | `ec1f3a2b8` | accounting-v2 | SDCP-9428 (reorder)
`DeathForeclosureInsuranceWriter`: move `deleteTask` (non-fatal) to before `clearLocalMap()`/`postTransaction` — ensures chunk rollback on postTransaction failure also covers all DB writes; removes duplicate deleteTask block left after reorder.

---

## 2026-05-15 | `b8d60d5e1` | accounting-v2 | SDCP-9428 (follow-up)
`DeathForeclosureInsuranceWriter`: switch `deleteTask` EC setup (`FUNCTION_CODE`, `FUNCTION_SUB_CODE`, `id`) from `put` to `putLocal` — prevents `getOfficeCodeAndNameByIds` CBS response (`office.id=2`) from polluting the global EC key `id`, which was causing `deleteTask` to send `id=2` instead of the real task_id and getting FAIL from the task service.

---

## 2026-05-14 — Foreclosure: respect `task_status` IParam in UpdatePrepaymentTaskDetailsProcessor (accounting-v2 `7438b3ce9` on `mfi_integration_v3.3.1.0` prod)

- **Repo:** `trustt-platform-accounting` — `mfi_integration_v3.3.1.0` (commit `7438b3ce9`, pushed to origin; awaiting QA retest). `./gradlew build -x test` green. Forward-port to `3.3.1.0.0` / `3.3.1.0.1` / `3.3.1.1` pending.
- `UpdatePrepaymentTaskDetailsProcessor.populateTaskDetails()` computed `task_status` from `(sequence, channelCode, isProceed, functionCode)` and silently fell back to `PENDING` when `function_code != APPROVE` AND `taskId != null` AND `sequence == null`. The XML on the deposit/`do_prepayment` branch (line ≈ 2087 of `loanPrepayment` in `loans_orc.xml`) passes `<IParam fieldName="task_status" value="APPROVED"/>` but the processor ignored it. Runtime: foreclosure `prepayment_details.task_status` flipped to PENDING after deposit despite the loan reaching CLOSED. Confirmed on QA5 LAN 6004358026. Fix: read the explicit IParam after `populateTaskDetails` and override `entity.setTaskStatus(...)` if non-null/non-empty — orchestration is now the contract; `populateTaskDetails` becomes a fallback for callers that don't pass `task_status`. Knowledge base updated: new [`claude/flows/loan-servicing/lan-transactions-reference.md`](../flows/loan-servicing/lan-transactions-reference.md) covering all LAN transactions + the 3 gating models; [`claude/flows/foreclosure-and-closure.md`](../flows/foreclosure-and-closure.md) now documents the MFI 3-stage workflow path (loanPrepayment chain DEFAULT → VALIDATE → APPROVE_TASK(x2) → APPROVE) alongside the classic single-approve flow.

## 2026-05-12 — PRODSLISFR-3293 — DFC writer: fold pre-death BPI into force-bill + collapse AIR-side waiver under new schema

- **Repo:** `trustt-platform-accounting` · `sdcp-9301-hotfix-3.3.1.0` · pushed; awaiting QA retest.
- Force-bill amount is now `dcf_bpi_amount + computeUnbilledPartialCycleAccrual` instead of just the post-death partial-cycle slice — the SDCP-9301 clamp (slice start = max(lastBilled, deathDate)) was correct under the old schema where BPI_AMT had its own rule, but the new ruleset has no `BPI_AMT` / `LOSSES_INT_WAIVED_AIR` / `INT_SUSP_AIR` legs, so the pre-death BPI must also be force-billed to enter `BILLED_INTEREST`. After force-bill, all of `LOSSES_INT_WAIVED_AIR` is collapsed into `LOSSES_INT_WAIVED` (pushed as `BLD_INT_WAIVED_AMT`); `LOSSES_INT_WAIVED_AIR` and `BPI_AMOUNT` are explicitly zeroed in EC so `calculateTotalTransactionAmount` / `populateAdvanceSrcAmount` don't double-count.
- For test LAN 6000256703 this produces the exact 5 GL entries from `6000256703_Correct_GL_Entries`: BILLING force-bill 665 (BILLED_INTEREST / INT_REC), UNBLD_PRIN_AMT 52,945 (DUE_TO_FC_B / LOAN_ACCOUNT), EXCESS_INCOME_INT_AMT 1,475 (INT_INC / EXCESS_ACCT), EXCESS_ACCOUNT_INC_AMT 1,475 (EXCESS_ACCT / LOAN_ACCOUNT), BLD_INT_WAIVED_AMT 665 (BILLED_INT_WAIVE / BILLED_INTEREST). Per-LAN trial balance nets to 0.

## 2026-05-12 — PRODSLISFR-3293 — DFC writer: align EC pushes with new accounting rule reference codes (Sheet15)

- **Repo:** `trustt-platform-accounting` · `sdcp-9301-hotfix-3.3.1.0` · pushed; awaiting QA retest. Depends on product team installing the new ruleset + placeholders + per-product bindings (BILLED_INT_WAIVE, CBC_FEE, PENAL_AMOUNT, FEES_WAIVED, PINT_AMT_WAIVED, STD/NPA principal waivers) per env.
- Switched `DeathForeclosureInsuranceWriter` `populateAdditionalAmountDetails` block to push the new reference codes from product's Sheet15: `BLD_INT_AMT`/`BLD_PRIN_AMT`/`UNBLD_PRIN_AMT`/`PINT_AMT`/`CBC_FEE_AMT` for settlement legs, `BLD_INT_WAIVED_AMT`/`PINT_AMT_WAIVED`/`CBC_FEE_AMT_WAIVED` for waiver legs, `EXCESS_INCOME_INT_AMT`/`EXCESS_ACCOUNT_INC_AMT` for excess flows, and `ADV_BLD_INT_AMT`/`ADV_UNBLD_PRIN_AMT`/`ADV_PINT_AMT`/`ADV_CBC_FEE_AMT` for excess-fed legs. Dropped `BPI_AMT`/`LOSSES_INT_WAIVED_AIR`/`ADV_PRIN_AMT`/`ADV_BILLED_PRIN_AMT`/`ADV_BPI_AMT`/`ADV_FORECLOSURE_AMT` (no rules in new schema). Internal calculation keys (`INT_AMT`/`POS`/`BILLED_PRIN_AMT`/`PENAL_AMT`/`FEE_AMT`) and SDCP-9301 force-bill + slice-into-waiver swap untouched. Penal and fee waiver totals from `waiveLonaDueDetailsEntries` are now summed and pushed under `pint_amt_waived` / `cbc_fee_amt_waived` so `PINT_AMT_WAIVED` and `CBC_FEE_AMT_WAIVED` rule legs fire with the right amounts. STD/NPA principal-waiver split intentionally deferred.

## 2026-05-14 — Payment reinit NEFT v2 — wire inquiry-on-STAGE_1_PENDING + DB advance on inquiry success (accounting-v2 `2cfe04431` on `mfi_integration_v3.3.1.1`)

Reinit retry while at `reinit_disbursement_status=NEFT_STAGE_1_PENDING` was throwing "Invalid disbursement status" — the processor previously skipped inquiry for reinit and `doNEFTTransaction` has no `STAGE_1_PENDING` branch. Replaced "Skipping bank status inquiry" with the same `doStatusInquiry` call non-reinit uses (looked up against `_REINIT`-suffixed NEFT CRR types). Also made `performNeftV2InquiryWhenStage1Pending` advance `reinit_disbursement_status` STAGE_1_PENDING → STAGE_1_SUCCESS via CAS on inquiry success, so the processor's `currentReinitStatus` re-read picks up the inquiry result. Effect: reinit NEFT v2 now decides next-call from `reinit_disbursement_status` exactly like normal NEFT v2 decides from `disbursement_status`.

## 2026-05-14 — Payment reinit RCA + fix — `function_sub_code` leak in `DisbursementCustomerNameHelper` (accounting-v2 `5f9cb3c60` on `mfi_integration_v3.3.1.1`)

`fetchCustomerFullName` did `putLocal("function_sub_code","DEFAULT")` for the `getCustomerDetails` sub-call but never undid it; the local override persisted, downstream reinit strong check in `doNEFTTransaction:91` saw `DEFAULT` instead of `REINITIATE_BANK`, override path was skipped, primary `disbursement_status=COMPLETED` was used, throw fired. Fix: try/finally with `removeFromLocalMap("function_sub_code")` on the way out — minimal scope to avoid disturbing other flows.

## 2026-05-14 — Reinit debug logging — instrument flag-check + state-read sites on 3.3.1.1 to trace QA3 "Invalid disbursement status" (accounting-v2 `b982025ff` on `mfi_integration_v3.3.1.1`)

`[reinit-debug]`-tagged logs at `DisbursementBankCallTypeUtil.isPaymentReinitiationTransferExecution`, `PaymentReinitiationStateService.currentReinitStatus`, and `ParentDisbursementNeftV2BankCall.doNEFTTransaction` (entry + override + branch + pre-throw). Captures `function_sub_code`, `payment_reinitiation_update`, `account_id`-in-EC, primary `disbursement_status`, and resolved `reinit_disbursement_status` on every call. Temporary — remove after RCA.

## 2026-05-12 — Payment reinit — declare `payment_reinitiation_update` in disburseLoan request templates (accounting-v2 `0977abab8` on `mfi_integration_v3.3.1.0`)

Flag was read by `DisbursementBankCallTypeUtil.isPaymentReinitiationTransferExecution` but never made it into EC because neither `mfi/disburseLoan_requestTemplate.json` nor `product/disburseLoan_requestTemplate.json` declared it; added the SMPL/String field to both so reinit code path becomes reachable. Forward-merge to higher branches pending.

## 2026-05-11 — SDCP-9301 + SDCP-9428 — Forward-port DFC fixes onto mfi_integration_v3.3.1.0

- **Repo:** `trustt-platform-accounting` · new branch `sdcp-9301-hotfix-3.3.1.0` (tip `41c6a31a3`) off `upstream/mfi_integration_v3.3.1.0` @ `e6fa4adba` · pushed; awaiting QA retest
- Cherry-picked the full 13-commit DFC fix series from `sdcp-9301-hotfix-3.2.8.4` (`13a70c4c6..b74f88731`) — extra-interest baseline + waived-interest exclusion, DCF billing sync (new `DeathForeclosureBillingSyncService`), user_id/List sync handling, sync cutoff alignment, split-billed-principal + interest-waiver fix, SDCP-9301 partial-cycle force-bill (+ EC snapshot/restore + start-clamp + dead-code drop), and SDCP-9428 task↔accounting reorder. All applied cleanly with auto-merge only. Mirrors the 2.8.4 hotfix branch on the next integration line.

## 2026-05-11 — SDCP-9428 — DFC insurance writer: reorder so task ↔ accounting stay symmetric

- **Repo:** `trustt-platform-accounting` · `sdcp-9301-hotfix-3.2.8.4` `b74f88731` + `sdcp-9428-hotfix-3.3.1.0` `6327d98a5` (off `upstream/mfi_integration_v3.3.1.0`) · both pushed; awaiting QA retest
- Moved `updateTaskWorkflow` (RE_UPLOAD) and `deleteTask` (APPROVE) to the end of their respective chunk-tx blocks so all accounting DAO writes commit first; removed the `LOG.error` swallow on `deleteTask` so a task-side failure now propagates as `BatchRuntimeException` and rolls the chunk back. Closes the seconds-long drift window where task service committed while accounting later rolled back (and the reverse). Residual chunk-commit-after-task-success microsecond window is unchanged from any non-saga approach; postTransaction / LOS Kafka / GL-CBS drift sources flagged as separate follow-up.

---

## 2026-05-08 — SDCP — Allow pre-disburse detail update when disbursement_status=LOAN_BOOKED

- **Repo:** `trustt-platform-accounting` `40c1bba0d` · `mfi_integration_v3.3.1.0` · pushed · PR pending vs khoslalabs upstream
- `LOAN_BOOKED` is set after LMS GL posting but before the bank API leg fires; no money has moved, so LOS must be allowed to correct account/IFSC details via `updateLoanAccountPreDisbursementDetails`.

---

## 2026-05-08 — Brain — LMS deep-dive audit on 3.3.1.0.1 + 5 new skills

- **Repos:** doc-only (no code change) · brain docs in `/home/darpan/Documents/sliProd/claude/` and skills in `/home/darpan/Documents/sliProd/.claude/skills/`
- Six parallel deep-dive agents audited disbursement / repayment / posting engine / batch jobs / async event queue + lifecycle / closure flows + data model + 3.3.1.0.1 deltas against `trustt-platform-accounting` head `149009993`. Outputs: new consolidated [`accounting/11-deltas-3.3.1.0.1.md`](../accounting/11-deltas-3.3.1.0.1.md), new [`platform/state-machine-safety.md`](../platform/state-machine-safety.md), updates to `engines/{disbursement,posting,repayment}-engine.md` (branch headers + 3.3.1.0.1 delta blocks; `posting-engine.md` got the `134497` ↔ `134067` dup-CRN error code change), `accounting/03-batch-dependency.md` + `system/07-batch-atlas.md` (corrected — `runEODJobs` only fires 5 child Requests; billing/interest/posting/TB run on independent cron schedules), `runbooks/disbursement-stuck.md` (added §B.1 NDF-recovery + §B.2 auto-flush race CLOSED), `flows/loan-servicing/death-foreclosure.md` (STAGE_6 SDCP-9301 partial-cycle billing narrative). Five new skills landed: `txn-graph`, `batch-atlas-lookup`, `posting-rule-resolver`, `state-machine-safety`, `delta-3-3-1` — all routing / quick-reference, not deep-dive replacements. Project memory `project_lms_audit_2026_05_08.md` records the audit so the next branch upgrade can re-run the same shape.

---

## 2026-05-07 — SDCP — close MFT auto-flush gaps + flow design doc

- **Repos:** `trustt-platform-accounting` `3e8710f97` · `mfi_integration_v3.3.1.0.1` · pushed · awaiting QA retest
- Two writers in the original (non-reinit) MFT lane were still doing `dao.save` after in-memory setters — the auto-flush race that hard rule §3 calls out. Migrated `CallBankAPIForDisbursementProcessor.saveBankErrorResponseCode` `FALSE+!isNeft` branch to `LoanAccountStateMachineService.transition` (explicit `fromStates=[DTFC_SUCCESS]`, advances to `PARENT_SUCCESS` when children present, else `COMPLETED`). Migrated `PostMFTChildLoanBankDisbursementProcessor.updateAndSaveQueueRow` FAIL branch to `childClmtStateMachineService.patchJsonFields` (state-agnostic patch). The `state-machine-safety` skill's "outstanding gap" is now closed — every writer to `loan_account.disbursement_status / filler_*` and `loan_account_events_queue.data->>'disbursement_status'` goes through CAS or `patchJsonFields`. Routing for the original lane stays inline per the agreed plan; reinit lane keeps `PaymentReinitiationStateService` as its central control block. New design doc [`engines/disbursement-state-machine-flows.md`](engines/disbursement-state-machine-flows.md) documents both machines with Mermaid state + sequence diagrams, NDF recovery, replay-with-different-fsc semantics, and a per-column writer map.

---

## 2026-05-07 — SDCP — payment reinitiation: MFT lane folded into the central state machine

- **Repos:** `trustt-platform-accounting` · `mfi_integration_v3.3.1.0.1` · pushed · awaiting QA retest
- Brought MFT (DISB_MODE_ACCTWB) under the same `PaymentReinitiationStateService` so MFT + NEFT v1 + NEFT v2 share a single control block. Added `FIRE_MFT_REINIT` to `NextStep`; updated `nextStep(loanAccountId, disbursementMode, useNeftV1)` to branch on mode first. Replaced the NEFT-only reinit-complete short-circuit in `CallBankAPIForDisbursementProcessor.process` with a unified `nextStep == REINIT_COMPLETE` gate evaluated after both the MFT-CRR-check and NEFT-skip-inquiry branches. `saveBankErrorResponseCode` `!isNeft` branch now advances `reinit_disbursement_status` to COMPLETED via CAS when reinit, leaving original `disbursement_status` and `filler_1/_2` untouched (CAS uses `rankBackwardSafeFromStates(COMPLETED)` so any pre-COMPLETED state advances cleanly). Memory `project_payment_reinitiation_scope.md` updated.

---

## 2026-05-07 — SDCP — payment reinitiation state machine for NEFT v1/v2 (parent)

- **Repos:** `trustt-platform-accounting` · `trustt-platform-initial-setup` · `mfi_integration_v3.3.1.0.1` · pushed · awaiting QA retest
- Reinit on a `loan_account` whose `disbursement_status=COMPLETED` previously failed for NEFT v2: `doNEFTTransaction` couldn't route NEF vs NEI without a stage tracker, callbacks REJECTED CAS against the COMPLETED loan, and `saveBankErrorResponseCode` clobbered the original disbursement fillers. Added a parallel state machine: V000189 introduces `loan_account.reinit_disbursement_status / reinit_external_error_code / reinit_external_error_message`; new central `PaymentReinitiationStateService` owns CAS + routing (`nextStep` returns `FIRE_NEFT_V1_REINIT / FIRE_NEF_REINIT / INQUIRE_NEF_REINIT / FIRE_NEI_REINIT / REINIT_COMPLETE`). Reinit-aware wire-ins in `ParentDisbursementNeftV2BankCall.doNEFTTransaction`/`performNEFTTransactionInquiry`, `CallBankAPIForDisbursementProcessor.process` (CRR-type override + reinit-complete short-circuit), `saveBankErrorResponseCode` (forward CAS, NDF rollback, empty-fromStates, error-only patch all retargeted to reinit columns when reinit), and `DoGenericSyncSTPBankNeftCallBackProcessor.processLoanAccount`/`processFailedLoanAccount`/`processInProgressCallback` (route by `transactionType.endsWith(_REINIT)` to new `processReinitNEFCallback` / `processReinitNEICallback`). UTR continues to `loan_disbursement_mode_details.utr_number`. Original `disbursement_status / filler_*` left untouched. Parent JLG/INDL only — child loans use the LAR cash-delivery task and do not flow through here.

---

## 2026-05-07 — SDCP — NEFT v2 retry-after-failure: rollback + re-fire path

- **Repos:** `trustt-platform-accounting` · `mfi_integration_v3.3.1.0.1` · pushed · awaiting QA retest
- After previous fixes for the parser-NPE / CRR-drop / empty-fromStates crash, retries from a failed bank attempt still didn't reach COMPLETED. Two underlying issues: (1) `performNeftV2InquiryWhenNotStage1Pending` else branch hard-set `DO_TRANSACTION=FALSE` for any pre-NEFT state, so a second `disburseLoan` from `disbursement_status=DTFC_SUCCESS` (with a prior FAIL NEF CRR) silently skipped the NEFT call → state never advanced; (2) when the bank inquiry returned `{"faxml":{"errorCode":"NDF","errorDesc":"Batch details not found..."}}`, the loan stayed pinned at `NEFT_STAGE_1_PENDING` even after the parser-NPE was caught — `rankBackwardSafeFromStates` is forward-only so no rollback was possible. Fix: (a) parent inquiry router now allows `DO_TRANSACTION=TRUE` for `DTFC_SUCCESS` so retry fires a fresh NEF; (b) parser-NPE catch in parent + child inquiry now sniffs the raw bank response for NDF / "batch not found" signals and signals a rollback (`NEFT_STAGE_STATUS=DTFC_SUCCESS`, `IS_BANK_CALL_FAILED=FALSE`); (c) `saveBankErrorResponseCode` (parent + child) now does a backward CAS `fromStates=[NEFT_STAGE_1_PENDING] → DTFC_SUCCESS` when the empty-fromStates guard fires for `DTFC_SUCCESS`, races safely (REJECTED if a callback advanced state), then sets `IS_BANK_CALL_FAILED=TRUE` so child disbursement aborts and the next `disburseLoan` re-fires NEF cleanly.

---

## 2026-05-07 — SDCP — NEFT v2 bank-error-envelope NPE drops CRR (LAN 6009685525)

- **Repos:** `trustt-platform-accounting` · `mfi_integration_v3.3.1.0.1` · pushed · awaiting QA retest
- Bank's NEFT v2 inquiry returned `{"faxml":{"errorCode":"NDF","errorDesc":"Batch details not found..."}}` (no `paymentlist`). HDFC infra JAR's `NeftTransactionStatusInquiryV2.doServiceCall` NPE'd reading `paymentlist.get(...)`, exception unwound out of `performNeftV2InquiryWhenStage1Pending` before any CRR write. Outer catch in `CallBankAPIForDisbursementProcessor.process` reached, but the `request`/`EXTERNAL_REFERENCE_NO` keys were putLocal'd inside the inquiry leg — by the time `handleDisbursementBankCallTryFailure` ran, fallback ref-no produced a row that either collided or had blank fields. Net: CRR not visible for the LAN, state stuck at NEFT_STAGE_1_PENDING. Fix: wrap the `neftTransactionStatusInquiryV2` and `neftPaymentV2`/`neftPaymentV2Stage2` calls (parent + child inquiry) with `try { … } catch (RuntimeException) { … }` that persists CRR locally with the actual bank response, sets `IS_BANK_CALL_FAILED=TRUE`, and returns — guarantees CRR is written and disbursement state stays put for any bank-side parser failure / malformed response.

---

## 2026-05-07 — SDCP — NEFT v2 inquiry crash on pre-NEFT disbursement_status (LAN 6009685025)

- **Repos:** `trustt-platform-accounting` · `mfi_integration_v3.3.1.0.1` · pushed · awaiting QA retest
- `disburseLoan` re-trigger via `function_sub_code=DTFC_SUCCESS` after a NEFT URL failure crashed with `IllegalArgumentException: at least one fromState is required` in `CallBankAPIForDisbursementProcessor.saveBankErrorResponseCode`. `performNeftV2InquiryWhenNotStage1Pending` was setting `DO_TRANSACTION=FALSE` without `IS_BANK_CALL_FAILED=TRUE`, so the caller entered the NEFT-success CAS branch with `neftStageStatus=DTFC_SUCCESS`, which has no rank-1 predecessor → empty fromStates → throw. Fix: mark bank-call failed in that else branch; add defensive empty-fromStates guard in both `CallBankAPIForDisbursementProcessor.saveBankErrorResponseCode` and `ChildDisbursementLoanEventsQueueSync.saveBankErrorResponseCode` (also covers the parent/child stage-1-pending "PROCESSED+reply 0" rollback paths that hit the same crash).

---

## 2026-05-07 — SDCP — NEFT v2 stuck-CLMT-row fix (Hibernate auto-flush race)

- **Repos:** `trustt-platform-accounting` `4c339282f 09295c377` · `mfi_integration_v3.2.8.4.1` · pushed · awaiting QA retest
- After CAS APPLIED, sync post-handler was still mutating the in-memory CLMT entity → outer-`disburseLoan` Hibernate auto-flush rewrote the row with stale `updated_on`, reverting any later async-callback `COMPLETED`. Removed all post-CAS in-memory mutations across `ChildNeftClmtPostBankService`, `DoGenericSyncSTPBankNeftCallBackProcessor.processInProgressCallbackForChild` advisory branch, and `ChildDisbursementLoanEventsQueueSync` inquiry-failure branch. Advisory/error-only writes now go through new state-agnostic `ChildClmtStateMachineService.patchJsonFields`. Closes QA3 stuck-row class for parent LAN 6009683725 child 19 (queue id 21360).

---

## 2026-05-07 — SDCP-9301 — Death-foreclosure full fix on 3.2.8.4

- **Repos:** `trustt-platform-accounting` `13a70c4c6 178814a75 216bdb6b1 f822b9a32 e91ae4b5e 917dddc4b daa263e8b aa5a798ea 0ebb2fa4a c71ea95c8 59e253c54` · `sdcp-9301-hotfix-3.2.8.4` · pushed · awaiting QA
- Closes claim/GL-outstanding mismatch, billed-principal GL routing, and adds force-billing for the post-deathDate partial-cycle accrual (paired force-accrual + force-billing per Sudheer's spec; no DPI). Requires product-ops to add `BILLED_PRIN_AMT` / `ADV_BILLED_PRIN_AMT` legs (`24511 → 13335`) on `DEATH_FORECLOSURE` and `RSCH_DEATH_FORECLOSURE` rules in QA + prod.

---

## 2026-05-06 — SDCP — close remaining backward-write paths on CLMT queue rows

- **Repos:** `trustt-platform-accounting` `ccf7f6b89` · `mfi_integration_v3.2.8.4.1` · pushed · awaiting QA
- Two more sites guarded: async-NEF success callback now also accepts `DTFC_SUCCESS`; `ChildDisbursementLoanEventsQueueSync.saveBankErrorResponseCode` success branch now consults `ChildClmtTerminalStateGuard.isAtOrBeyondStage` before save. Together with `c704969ec`, every disbursement state-machine writer is forward-only without `@Version`.

---

## 2026-05-06 — SDCP — close async-NEI-callback vs sync-inquiry-post-handler race

- **Repos:** `trustt-platform-accounting` `c704969ec` · `mfi_integration_v3.2.8.4.1` · pushed · awaiting QA
- Async callback now accepts `NEFT_STAGE_1_SUCCESS` (not just `NEFT_STAGE_2_PENDING`) so it can drive `COMPLETED` even when sync inquiry post-handler hasn't committed yet; sync handler consults `isAtOrBeyondStage` in OK branch (was OLE-only, never fired). Verified against QA3 LAN 6009683325 child 2 (queue 21042).

---

## 2026-05-06 — SDCP — tighten verbose comments on populate-before-prepare fix

- **Repos:** `trustt-platform-accounting` `65bdd2a11` · `mfi_integration_v3.2.8.4.1` · pushed
- Pure comment trim per `feedback_crisp_comments.md`; no behaviour change.

---

## 2026-05-06 — SDCP — populate per-member amounts BEFORE writing CLMT queue rows

- **Repos:** `trustt-platform-accounting` `55e58d31d` · `mfi_integration_v3.2.8.4.1` · pushed · awaiting QA
- Closes regression from `a6fdc1c88` prep-block split: `net_disbursed_amount` was NULL in CLMT data, every child NEFT v2 leg silently bailed at `CallBankAPIForIndividualChildLoanDisbursementProcessor:61-65` (zero log lines). QA3 parent 11850460 (LAN 6009682925) had 23 dropped legs. Defense-in-depth: silent early-return now logs at ERROR.

---

## 2026-05-06 — DPIC v1 — manual completion round 2: derived fields + repayment audit + reversal (3.3.2)

- **Repos:** `trustt-platform-accounting` `1f71a8b9c`, `trustt-platform-initial-setup` `aacfc99f 234241a7` · `feature/dpic-v1` · pushed · awaiting QA
- Closes 6 correctness gaps: derived-fields totals, `loan_account_payments_details.dpi_amount`, `transaction_reversal_details.dpi_amount`, repayment reversal DPI walker, `EXCESS_AMT` reversal recompute, payments-reversal clone copies `dpiAmount`. Pattern: forward path was built but persistence audit / write-side / reversal walker / clone paths were skipped.

---

## 2026-05-06 — DPIC v1 — manual completion of gaps in Claude-session WIP (3.3.2)

- **Repos:** `trustt-platform-accounting` `2f3c7e25a 456b4d34e 0d0376b85`, `trustt-platform-initial-setup` `716a4bd4` · `feature/dpic-v1` · pushed · awaiting QA
- Closes 8 correctness gaps in the prior WIP: GL postings actually fire, `loanRepayment` carries DPI split, DPD base = PRIN+INT+DPI (per UD §5.5), idempotent flyway scripts + V000xxx naming, NPA detection, deterministic txn-ref-numbers, sub-type system-property overrides, Vo metadata propagation.

---

## 2026-05-06 — DPIC v1 — WIP head-start scaffolding (3.3.2)

- **Repos:** `trustt-platform-accounting`, `trustt-platform-initial-setup` · `feature/dpic-v1` (off `upstream/mfi_integration_v3.3.2`) · local WIP
- Calc service + appropriation processor + code-master seeds done; batch jobs + Loan 360 + lifecycle handlers deferred pending Product Q1-Q6 in `claude/dpic/05-open-questions.md`.

---

## 2026-05-05 — SDCP — stabilize child MFT post-bank handler under high CLMT contention

- **Repos:** `trustt-platform-accounting` `5bb49d7a4` · `mfi_integration_v3.2.8.4.1` · pushed · awaiting QA
- MFT path aligned with NEFT v2 fix from `c2583dca9`: 1→2 OLE retries + targeted catch in `execute()` so OLE doesn't escape reactor pipeline or trigger SOF re-fire.

---

## 2026-05-05 — SDCP — split disburseLoan: commit CLMT rows in own Transaction before child-bank-call block

- **Repos:** `trustt-platform-accounting` `a6fdc1c88` · `mfi_integration_v3.2.8.4.1` · pushed · awaiting QA
- Replaces the reverted `e8fef5c35` Java REQUIRES_NEW with an XML `<Transaction>` block split. Orphan recovery via existing `PerformChildLoanBankDisbursementProcessor:74-78` lazy-create fallback.

---

## 2026-05-05 — SDCP — CLMT REQUIRES_NEW commit + idempotency guard — **REVERTED in `2d9730818`**

- **Repos:** `trustt-platform-accounting` `e8fef5c35` (reverted by `2d9730818`) · `mfi_integration_v3.2.8.4.1`
- Safety story relied on `accountingBankServiceRetryJob` recovering orphan CLMT rows — false (it queries CRR, not queue; `childLoanEventProcessingBatchJob` excludes CLMT). Rolled back same day. `8abd48f49` retry-with-backoff remains as defence pending proper fix (landed in `a6fdc1c88`).

---

## 2026-05-05 — SDCP — retry CLMT queue lookup in child NEFT callback to absorb orchestration commit lag

- **Repos:** `trustt-platform-accounting` `8abd48f49` · `mfi_integration_v3.2.8.4.1` · pushed
- 5-attempt linear-backoff retry (100/200/300/400ms; total max ≈1s) on `findOneByFiller2` covers the bank-async-callback-arrives-mid-orchestration-commit window observed for parent 6009682825 (20-child SHG).

---

## 2026-05-05 — SDCP — canonicalise child NEFT UTR write to filler_3

- **Repos:** `trustt-platform-accounting` `7ab965fe3` · `mfi_integration_v3.2.8.4.1` · pushed
- Sync/inquiry post-bank UTR write now matches async-callback path (both → `filler_3`) so `BookChildLoanProcessor` can populate `loan_disbursement_mode_details.utr_number` regardless of which path delivered success. Pre-fix: sync wrote to `filler_1`, UTR stranded.

---

## 2026-05-05 — SDCP — stabilize child NEFT v2 post-bank handler under CLMT contention

- **Repos:** `trustt-platform-accounting` `c2583dca9` · `mfi_integration_v3.2.8.4.1` · pushed
- Closes OLE-drop / lost-CRR / re-fire-bank-call cascade observed for parent 11849960 on QA3.

---

## 2026-05-04 — SDCP — atomic child in-flight gate + broadened NEFT stage-1 evidence

- **Repos:** `trustt-platform-lib` `4cb437b28`, `trustt-platform-accounting` `ede4aa325` · `mfi_integration_v3.2.8.4.1` · pushed
- Fixes TOCTOU race in cursor's Redis dedup + over-strict NEFT stage-1 guard that was blocking 5+ QA3 children.

---

## 2026-05-04 — SDCP — fail-fast on task pre-step errors, defer FREEZE flip until after task workflow

- **Repos:** `trustt-platform-accounting` `154b500c0` · `SDCP-fix-task-id-orphan-3.2.8.4` (off `upstream/mfi_integration_v3.2.8.4`) · pushed · PR pending vs khoslalabs upstream

---

## 2026-05-04 — SDCP — friendly error for duplicate `client_reference_number` on `loanRepayment`

- **Repos:** `trustt-platform-accounting` `d358a9034`, `trustt-platform-initial-setup` `62cefa1e` · `SDCP-fix-dup-crn-loan-repayment` (off `upstream/mfi_integration_v3.3.1.0.0`) · force-pushed · PRs open vs khoslalabs upstream

## 2026-07-13 | initial-setup | rollback SQL 3.4.2.2_055 → 3.4.2.1_017
Prepared prod rollback for 13 Flyway scripts between tags (audit/los/masterdata/notifications/platform_master). Path: scripts/sql/deploy/rollback_initial_setup_3.4.2.2_055_to_3.4.2.1_017.sql. QA: varchar(255)→TEXT on forwarded_notes; truncate USING left(...,255) required.
