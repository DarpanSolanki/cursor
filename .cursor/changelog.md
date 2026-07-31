## 2026-07-31 — SHG INT distribute tip calendar + full IAD column audit bar
- accounting `InterestGroupLoanAccrualDistributionService`: tipBehind asOf → freeze+new when posted else setEndDate(asOf) (independent-calc calendar parity; Accrued=parent share intentional).
- Workspace: `iad_column_audit` audits ALL 11 physical IAD columns fail-closed; tip carry=0 intentional; `money_behavior_parity_gate` + interest_accrual enforced; never WARN tip lag.

## 2026-07-31 — SHG child IAD column audit in local stitch
- `flowtest.iad_column_audit` + wire into `flowtest.shg_int_accrual_stitch`; acceptance manifest `interest_accrual` IAD columns. Tip end_date lag = WARN (LMS-DEFECT-child-iad-stuck-tip); money columns fail-closed.

## 2026-07-31 — SEMANTICS CLOSE-UP (GL DB + config)
- `gl_rule` from local transaction_accounting_rule (191); placeholder F absent; QA3 parity OK on 3 samples; GL truth MATCH on BILLING/INTEREST/repay.
- Kafka MessageBroker.xml threads/poll; skipLimit MAX; Tomcat Boot defaults; txn reconcile; activation path→novopay-platform-lib; money-core purpose backfill.

## 2026-07-31 — SEMANTICS + FRAMEWORK BONE
- KG layer: `entity`/`txn_type`/`gl_mech`/`batch_cfg`/`redis_key`/`framework`/`server` via `build_semantics_bone.py`; wired `build_activation.py`; `kg concept` + MCP `kg_concept`; doctor SEMANTICS-BONE; impact framework warning.
- Provenance-only (no invented GL accounts). Query: `kg concept LOAN_PREPAYMENT` / `autoflush` / `loan_due_details`.

## 2026-07-31 — empty pending after GC is PASS
- ship-loop-gate + autopilot end: GC-cleared pending → PASS (not exit 2).

## 2026-07-31 — pending-ship GC (no forever sticky money)
- `pending_ship_gc.py`: drop clean+pushed paths; keep dirty/unpushed. Wired into register, harness push-skip, session auto-close, stack-doctor. CLI `pending-ship-gc.sh`.

## 2026-07-31 — ship-loop credit PASS skip re-fire (TAT)
- `ship_credit_pass.py` + ntest record + ship-loop `SKIP CREDIT` when pending fingerprint matches recent PASS. Env: SHIP_CREDIT_PASS / SHIP_FORCE_REFIRE / SHIP_CREDIT_PASS_MAX_AGE_S.

## 2026-07-31 — flowtest e2e lock harness (owner + wait + stack-doctor)
- `lock.py`: owner meta, `FLOWTEST_LOCK_WAIT_S` (default 120), clear busy msg; `flowtest-lock-status.sh`; stack-doctor clears only flock-free stale files.
- Memory: `feedback_flowtest_e2e_lock_smooth.md`. L2: ship-loop same-case PASS skip while lock held — deferred.

## 2026-07-31 — interestAccrualCalculation reader exclude SHG children
- accounting `aa13f99d0` on mfi_integration_v3.4.2.4: reader+partitioner `parent_loan_account_id IS NULL` (SHG children only; JLG/INDL have none). e2e: shg_int_accrual_stitch + accrual_billing + batch.interest_accrual_calc PASS.

## 2026-07-31 — GAP-062 WONT_TRACK (loanWriteoff not live)
- Stop tracking writeoff EC mismatch / suite / backlog / defect as open High. Code already reverted `131e57a2f`. Reopen only if product delivers writeoff.

## 2026-07-31 — revert GAP-062 writeoff appropriation (dead code)
- accounting `131e57a2f` on mfi_integration_v3.4.2.4: revert `896c02a56` PrepaymentApproppriationProcessor writeoff EC normalize — loanWriteoff not in production.

## 2026-07-31 — JOURNEY BONE: kg-switch --help + env reachability
- `kg-switch.sh --help` no longer triggers rebuild (was cache-miss path).
- `cursor-bundle/kg/kg.db` → symlink `data/kg.db` (empty stub removed).
- env-matrix reachability refreshed 2026-07-31 (qa2/qa6 UNREACHABLE); qa-catchup queue added.
- Self-learn: `af52abe3d` accrual booking soft-skip still missing `kg cases interestAccrualPosting` (changelog lacked kg-flow tag) — see defect LMS-DEFECT-accrual-booking-abort.

## 2026-07-31 — booking abort formalize
- Defect LMS-DEFECT-accrual-booking-abort + child stuck tip probe; L2 skip log on accounting; QA blast UNKNOWN (DB down).

## 2026-07-30 — BONE AUDIT residuals
- InterestAccrualBookingBatchService: continue on non-booking-day IAD (empty processDtos fix); shg stitch schedule-derived window; writeoff/penal out of suite15; _contract_scan restored; doctor HEALTHY; suite 10/15.

## 2026-07-30 — FINISH: validators length-only + partprep PTC + GAP-062
- accounting `93be08eaa` length-only postTransaction validators; `896c02a56` GAP-062 appropriation EC normalize.
- harness: product-44 PART_PREPAYMENT DPI_BILLED_INTEREST seed; flowtest.part_prepayment TRIAL PASS; coverage YES.
- writeoff local still 132223 (no LOAN_WRITE_OFF catalogue) after NPE cleared.

## 2026-07-30 — D2 postTransaction length validators + harness STAN≤64
- accounting `90ed78ab0`: product_transaction_orc postTransaction mandatory cref (130121) + stringLength≤64 cref/stan (132181).
- harness `6ba1b7e`: stop STAN double-append; reclassify NPA varchar defect; residual 132160 evidence.
- Proof: flowtest.dpd_npa PASS (slab 31-500 is_npa=true; invariants PASS).

## 2026-07-30 — MCP hang fix (trustt-kg 1.9.1)
- Handler watchdog: daemon `join` + structured `TIMEOUT` (reads≤2s, heavy≤15s, enhance≤45s); no `shutdown(wait=True)`.
- SQLite: `check_same_thread=False` + serial lock; TIMEOUT invalidates without close (avoid abandon deadlock).

## 2026-07-30 — GAP-CLOSE: enforcement + money-truth + MCP cache
- U0: `with-budget.py` portable kill; hooks.json all budgeted (sessionStart 600→30); run-guarded kill proven.
- U1: telemetry RED blocks money ship; flow_coverage alias YES→PARTIAL (posting/reversal/event); NOT-COVERED path banner; taxonomy REFUSE unknown; PROVISIONAL on fresh/header.
- U2: mcp_auth instant; workspace_status/map_audit TTL cache; sessionStart --fast.
- U3: deleted 7 orphan KG builders + refresh-kg-state.sh; ship_baseline lives in registry.json (10 cases).

## 2026-07-30 — Workspace hygiene: KG cache LRU + scratch cleanup
- Pruned orphan KG cache manifests (build kept 8 `*.db` but left `*.manifest.json`); live key kept; cache ~589MB→~332MB.
- `build.sh` + `workspace-hygiene` (max 8) now drop sidecar+orphan manifests; `kg-switch` cache-hit touches LRU mtime.
- Closed-task `scripts/scratch/*` removed (kept `logs/`, `services/`, `dpic_demo_state.env`); Jul-2 KG temp jsonl removed. No ops script deletes.

## 2026-07-30 — Push-origin: workspace-safe HEAD skips sticky money close
- `is_workspace_push_safe_paths` + `ship_push_gate` skip when HEAD has zero service-repo paths (harness/docs).
- Prunes harness/scratch/kb from pending; keeps accounting Java for next product push. Scratch never registered.
- Regression: `test_ship_push_workspace_safe.py`. KG `ship_plan` remains advisory (not push-close SoT).

## 2026-07-30 — NEFTv2 local simulator (Chameleon) enrichment for 3.4.2.4
- Gold JSON stubs: `scripts/mfi_simulator_neft_v2_seed.sql` + `neft_v2_local_prepare.sh` (probe NEF/NEI/Inquiry on :8018).
- `disburse_loan_sanity` v2 profile writes nested JSON (not XML) + single-token validation `ST_NEF`/`ST_NEI`.
- `disburse-indl-quick.sh` defaults `--neft-version v2`; callbacks: `complete_neft_v2_via_callbacks.py` (no real bank).

## 2026-07-30 — Harness fidelity gate (ntest ≈ prod/QA real flow)
- New `scripts/lib/harness_fidelity_gate.py`: money runtime cases must declare `fidelity.entry`; undeclared audit truncate / Accrued SQL mutate / soft_fail / ACCEPTANCE_STRICT=0 fail closed.
- Wired into `ntest validate` + `registry_companion_gate`; inventory `scripts/testing/harness_fidelity_inventory.json`.
- SHG stitch: `CLEAR_BATCH_FAILURE_AUDIT` default 0; `dateroll.roll` soft_fail default False; flowtest cases annotated; remaining money cases AUTO-STUB fidelity for ratchet.

## 2026-07-30 — L2 harness: SHG INT calc→posting→billing stitch
- New `flowtest.shg_int_accrual_stitch` (`ntest run flowtest.shg_int_accrual_stitch`): quarantine + `CHAIN_ACCRUAL_BILLING`, window Accrued parity SQL, Posted/LABD asserts, optional `batch_failure_audit` truncate.
- `dateroll.roll(..., soft_fail=False)` for money stitch; change_test_map → `InterestGroupLoanAccrualDistributionService`; proposal promoted.
- LIVE PASS on `6000012030` (~164s). Product SkipListener ClassCast deferred (senior discuss).

## 2026-07-30 — trustt-kg MCP 1.8.3: hot-reload without IDE restart
- On `tools/list|call|ping`, re-exec MCP process if server/kg.py mtimes changed (stdio pipes kept).
- Re-open SQLite when `kg.db` mtime or watermark `built_at` changes.
- `capabilities.tools.listChanged=true`; e2e impact query points at distribute service.

## 2026-07-30 — SHG INT Accrued: parent SoT installment-window distribute (3.4.2.4)
- New `InterestGroupLoanAccrualDistributionService` (~230 LOC): SET ACTIVE child window Accrued via existing `GroupLoanUtility` carry-over; posted floor; reuse `findAllByAccountId` (child IAD p95≈25); no new `@Query`; no aide/extra installment lookups on create.
- Wire online+batch (skip child calc; distribute after parent; also when `stop_interest_accrual`); removed forceful `adjustChildLoanAccountsInterestAccrual`.
- Prod-grade live: Posted invariant, Accrued≥Posted, child-LAN redirect, multi-window SET 2174→3125 parity (`scripts/scratch/shg_int_distribute/run_prod_grade_checks.py`).

## 2026-07-30 — trustt-kg train routing: autopilot sync + honest kg_enhance (v1.8.2)
- `train_sync.py`: parse user train from message → scoped `sync-branches --domain … --yes` when live ≠ requested.
- Autopilot: auto `train_sync` step + directive when message names a train (e.g. 3.4.2.4).
- MCP `kg_enhance`: optional `train` + `sync_domain` + `dry_run` — sync then kg-switch. **kg_align remains detect-only.**
- Smoke: train-routing gate + kg_enhance schema; E2E 25 tests.

## 2026-07-30 — DPIC harness: exec-id batch wait + local single-node registration (3.7.1 verified)
- wait_batch_job binds job_execution_id; dpi_demo_fixture single-node SQL; suite quarantine; test-map + TDPQA-207; MCP 1.8.1 KG cache refresh on watermark drift.

## 2026-07-30 — trustt-kg MCP 1.8.0: close honest gaps (22 tools)
- Added kg_reads, kg_error, kg_node, kg_doctor, kg_enhance; orient verify paths; fetch_if_stale default; MAX_CHARS 24k; E2E 24 tests PASS.

## 2026-07-30 — trustt-kg MCP 1.7.0: 17-tool E2E audit + fixes
- Fixed kg-mcp-smoke.sh branch detection; orient `brief` + why `auto_cap`; workspace_status summaries; E2E test `scripts/lib/test_kg_mcp_e2e.py`.

## 2026-07-30 — trustt-kg L1+L2: event-queue dispatch + cross-service contracts in build
- `build_event_dispatch.py` (EVENT_TYPE_ORC_API_MAP), ternary/callInternalAPI in internal_calls, `build_contracts.py` wired with repo-scoped `calls` edges.

## 2026-07-30 — trustt-kg: generic orient/why reachability (internal calls + transitive why)
- `build_internal_calls.py` indexes Java `api_name` dispatch → `calls` edges; `kg why`/`kg flow` walk nested Requests + related diags (no per-flow curated patches).

## 2026-07-30 — trustt-kg MCP 1.6.0: 17-tool audit patch
- Per-tool timeouts; stack-doctor 12s+cache (workspace_status no longer blocks 45s); isError on align/misaligned exits; kg_align in smoke; version 1.6.0.

## 2026-07-30 — trustt-kg L1+L2: knowledge ship routing + require-align
- L1: `scripts/bin/kg-*` / `scripts/lib/kg_*` are knowledge-only; knowledge HEAD skips sticky money/DPIC auto-close (`ship_push_gate`).
- L2: `--require-repo/--require-branch` + `KG_ALIGN_*` / `KG_REQUIRE_ALIGN` on impact/flow/orient/why/crud/writes; MCP v1.5.0; `kg-self-enhance.sh`; post-checkout align when env set.
- Tests: `scripts/lib/test_kg_knowledge_ship_routing.py`.

## 2026-07-30 — trustt-kg: branch-wise align + Java symbol impact (system-wide)
- `kg align` / `kg-align.sh` / `kg-switch --assert-repo/--assert-branch` / MCP `kg_align` — fail-closed watermark vs expected train before money impact.
- `build_java_symbols.py` — method nodes (`symbol:repo/Class#method`) for `kg impact`; wired into `build.sh`.
- Orient/impact print accounting train; curated diags for Accrued last-child pad + child→parent force-bill mirror; `kg-profiles.md` PARTIAL (align shipped, overlays deferred).

## 2026-07-29 — SHG parent INT ₹1: mid-cycle proven; due-date seal (not month-end)
- QA4: Vikram `6011424425` full EMI periods Accrued/Posted/Schedule Δ=0; partial `2026-12-21` posted 29 vs 15+15. Mid-cycle `6000000638` 2133 vs 2134 before first due. Cohort ±1 ACTIVE parents: 70 mid-cycle / 58 latest-on-due / 0 month-end-only.
- Clarify: month-end = GL posting day; Accrued catch-up = due-date RPS seal. KG diag + changelog updated.

## 2026-07-29 — trustt-kg: SHG parent INT ₹1 + resolve request>scheduler
- Curated diags: `diag:rounding.shg_parent_child_interest_accrued_rupee` (SDCP-3245 forceful-only adjust; mid-cycle HALF_UP; QA4 fixtures 6011424425 / 6000000638), GAP-080 future INT, SDCP-11058 BPI, SDCP-11012 DPI.
- `kg.py resolve` / flow / crud: prefer unique Request label over same-named `scheduler:` (fixes empty `interestAccrualCalculation` spine).
- Promoted learning `diag:learn.shg_parent_int_accrued_rupee_tdpqa72` from TDPQA-72 Vikram + QA4 SQL.

## 2026-07-29 — trustt-kg MCP close (1.3.1)
- Verified 16/16 tools: JSON-RPC smoke + semantic needles + live Cursor MCP (validate/why/map_audit/mcp_auth).
- Shipped: stdout capture (kg.py), dup2+reload map_audit, mcp_auth no-op, kg_map_audit soft_gap, kg-mcp-smoke.sh semantic gate.

## 2026-07-29 — Ship-loop: stop BY_LATEST harness → full FC+DCF suite
- Root: `_foreclosure_path_touch` matched `scripts/testing/foreclosure/*` + selection force-promoted domain cases to full (~1h17m on push-origin).
- Fix: write-path-only fc_touch; domain_added stay smoke; foreclosure `read_impact_cases`; `SHIP_CLOSE_REPO` scopes push-origin close. Plan for by_latest ≈ 4 cases / ~145s.

## 2026-07-29 — TDPQA-207 train push + JIRA sequencing
- Correction: fix was only on `origin/fix/tdpqa-207-foreclosure-by-latest`; now also on **`origin/mfi_integration_v3.5.2.2` @ c7657a07df** (upstream tip + cherry-pick). Never call feature-branch-only “pushed for QA”.
- Rules: jira-fix-update Push gate; `jira-tdpqa-qa-test-fields.mdc`; memory `feedback_jira_push_train_before_enrich.md`.

## 2026-07-29 — TDPQA-207 L1 + MCP knowledge
- L1 confirmed: PrepaymentDetailsRepository demotes REJECTED for BY_LATEST (sha 3a21599a1). ntest `foreclosure.by_latest_details_api` PASS on LAN 0000001440. No system_created_on (PlatformDateUtil prod valueDate==systemDate).
- MCP genuine gaps: curated diags for BY_LATEST+PlatformDate; workspace_status stack-doctor timeout 12→45s; by-latest test harness fixes (LAN/payment_mode/python argv).

## 2026-07-29 — trustt-kg MCP stdout protocol fix
- Root cause: kg validate / fixed-elsewhere subprocess stdout polluted MCP JSON-RPC (`OK: N nodes`, `REUSE_FORBIDDEN`) → Cursor serverStatus=error.
- Fix: capture in kg.py; MCP dup2 stdout→stderr; kg_map_audit tool; `scripts/bin/kg-mcp-smoke.sh` 15/15 PASS.

[2026-07-29] | WORKSPACE | Full LMS map audit: change_test_map v2 (specific needles before broad packages); lms_flow_map_audit.py CRITICAL fail-closed; TDPQA-207 class misroutes fixed | change_test_map.json, lms_flow_map_audit.py

[2026-07-29] | FIX TDPQA-207 L1 | BY_LATEST deprioritises REJECTED/REJECT in findLatestByLoanAccountNos (DISTINCT ON) + getIdAndLoanAccountIdByAcctNo; build green + QA3 proof | PrepaymentDetailsRepository.java @ mfi_integration_v3.5.2.2 3a21599a1

[2026-07-29] | WORKSPACE | fixed-elsewhere unblock: stale `novopay-upstream-fetch.stamp` no longer hides real upstream fetch; `git-fetch-all.sh` writes stamp after upstream fetch | branch_train.py, git-fetch-all.sh, test_branch_train.py

[2026-07-29] | FIX TDPQA-192 L1 | Dual-code DIY/DIM hubs: accept raw 360/365/ACTUAL + DIY_*/DIM_* (DPIC masterdata); fix /0 in getDaywiseInterestRate + Days360 path | AssetsConstants.java, RepaymentScheduleUtil.java, InterestCalculationUtil.java @ mfi_integration_v3.7.1

[2026-07-28] | FIX TDPQA-72 L1 | Parent FC mirror: force-post INTEREST slice (=child billAmount) then bill; stamp IAD only after TM; parent RSCH remap INT_AMT→BLD_INT_AMT (BI) + local TAR setup | ForceBillAccrualSliceSupport.java, RegularForeclosureForceBillService.java, PopulateAdditionalAmountForPartPrepaymentProcessor.java, local_setup_rsch_loan_prepayment_bld_int_tar.sql @ mfi_integration_v3.4.2.4

[2026-07-28] | SHIP-TIME | Live progress contract (ship_progress + run-guarded heartbeats); booking wait floor; exclude ship_scope=manual (full_regression+ud_compliance); invariants gate on main; stack-doctor/chain_budgets | scripts/lib/ship_progress.py, run-guarded.sh, ship-loop-gate.sh, wait_batch_job.sh, impact_tests.py, registry.json

[2026-07-28] | TEST harness | Fail-fast batch wait + dpi_prep_before_batch; harness SoT on origin/main (cherry-pick from 3.4.2.4 + overlay) | scripts/dpic/lib/wait_batch_job.sh, dpi_demo_fixture.sh, dpi-sanity.sh, agent-ops-lib.sh, feedback_harness_push_origin_main_only.md

[2026-07-28] | TEST harness | DPIC overview registry asserts; demo_runtime helpers; repayment wall-clock platform date; part-prep JTF nest | scripts/testing/registry.json, scripts/dpic/demo/lib/demo_runtime.sh

[2026-07-28] | TEST harness upgrade | DPIC harness lib (two clocks, safe repay, preflight, learnings); feedback_dpic_harness_gotchas.md | scripts/dpic/lib/dpic_harness_lib.sh, demo_runtime.sh, registry, learnings.jsonl

[2026-07-28] | FIX (timeout) | Correct derived DPI batch wait budget computation (median from durations via argv; no stdin-heredoc loss) | scripts/dpic/lib/wait_batch_job.sh

[2026-07-28] | FIX (ship-determinism) | DPI batch wait budget derived from mfi_batch durations + human waiver requires head_sha+expiry (no silent future carry) | scripts/dpic/lib/wait_batch_job.sh, scripts/lib/ship_fingerprint.py, scripts/lib/impact_tests.py

[2026-07-28] | FIX (L1) | Align `ChildLoanForeclosureProcessor` mapping to KG request `childLoanForeclosure` (C1 selection truth) | scripts/lib/change_test_map.json

[2026-07-28] | FIX TDPQA-180/184/186/187/188 | Seal DPI accrual on AID rate change; accept scheme days_in_month 30; LIQ_INSTL installment-before-charge; LAPD-sourced reversal DPI; part-prep due_amount excludes unbilled BPD | trustt-platform-accounting @ mfi_integration_v3.7.1 852f72097


[2026-07-27] | FEATURE | FINAL SYNC: drain A1–A9 (tier variants≈⅓ ForceBill wall, FLOW_CASE_COVERAGE, penal/stubs wont-do, ntest canonical, orphan hooks documented, consumer denom 44/44, IDE Grep footnote, lean perf idioms, ship_baseline serial caveat); B path rewrite 108→0 stale docs; doctor GAP-G rails; smoke hook-contract allow-or-deny; SELF-REPORT F3/F4 | scripts/lib/impact_tests.py, map_completeness.py, workspace-doctor.sh, smoke-workspace.sh, brain+cursor docs, SELF-REPORT.md

[2026-07-27] | FIX TDPQA-72 L1 | Surgical EC split: force_bill_posted + force_bill_amount on FC force-bill; keep bpi_amount for lapd/UI; suppress BPI_AMT/ADV_BPI_AMT GL; roll slice into INT_AMT on LOAN_PREPAYMENT (DFC BLD_INT_AMT parity) | ForceBillBillingSupport.java, RegularForeclosureForceBillService.java, PopulateAdditionalAmountAndAccountDetailsForForeclosureProcessor.java @ mfi_integration_v3.4.2.4

[2026-07-27] | FIX TDPQA-72 | Centralize bpi_amount=0 after partial-cycle force-bill in ForceBillBillingSupport — covers INDL/JLG/SHG child FC (loans_orc + group_mfi_orc) and DFC child/parent via DeathForeclosureForceBillService; prevents double AIR credit on LOAN_PREPAYMENT BPI_AMT after AIR→BI billing | trustt-platform-accounting ForceBillBillingSupport.java @ mfi_integration_v3.4.2.4

[2026-07-27] | STITCH-FIX | X1: process_matrix at scripts/lib (not testing/) — absorbed into process_router.py (Upgrade 8 / 6f95865); X2: fast-exit hooks (grep-leak+pre-commit non-match 28→5ms); X3: expect.status for YES-coverage (disbursement.quick PASS / dpic PARTIAL) + drift probe; X4: orient-before-edit gate (kg.py touch session; after-ship-path-edit fail-closed) | .cursor/hooks/*, cursor-bundle/kg/bin/kg.py, scripts/testing/registry.json

[2026-07-27] | FEATURE | KG truth: fix /home/darpan/darpan FRESH lie + fail-closed STALE KG-paths; MCP in-process SQLite (≤20ms warm); unified cache key; consumer/scheduler/unresolved parse; after-edit fail-closed + light incremental; grep-leak counter | cursor-bundle/kg/**, scripts/lib/kg_state_banner.py, .cursor/hooks.json

## 2026-07-27 — DCF S_C harness: stop SEED_EXTRA group billing extend

- Root cause: fixture billed whole group through CURRENT_DATE before non-last DCF → sticky BLD_PRIN → parent POS desync (Δ=extra billed PRIN). Product Writer not at fault for this fail mode.
- Fix: gate extend behind `SEED_EXTRA_EXTEND_GROUP_BILLING=1` (default off); EXTRA still seeds last-child via loanRepayment path. S_C re-verified PASS.

## 2026-07-27 | workspace | DCF full-matrix harness + schema column audit (QA4-aligned)
- S9 `assert_full_money_column_audit` + `dcf_full_schema_audit.py` + `run_dfc_scenario_matrix.sh`; registry S9 db_asserts on Vikram/clean/main DCF cases.
- QA4-aligned OS/UNBLD/dual-DFC Obs2 scope; learnings for EXTRA POS open (S_C) and repay-close BLOCKED (S_D). No product Java.

## 2026-07-25 | workspace | FLOWTEST F1 — extract flow-agnostic harness core + RSTCRE pilot
Shared `scripts/testing/flowtest/` (lock/fixture profiles/asserts/runner); DFC wraps same core; registry `flowtest.rstcre_spine` + domains restructuring impact; `flow_coverage.json` ratchet + SELF-REPORT %. Pilot 54s PASS; DFC parity 187s S1-S8 PASS.

## 2026-07-25 | workspace | FC/DFC fixtures closed + LMS-wide impact + KG self-learn
- Harness: dcf_fixture_backup restores account+labd+iad; pin 6000137433 re-snapped; Vikram→fresh default; Obs1b accumulate fallback; quarantine overdue-window + pinned-Vikram 134207.
- LMS-wide: lms_service_domains.json/py + impact_tests mandatory health.* for LOS/payments/actor/…; ntest quarantine skip; enrichment-sync CASES→FULL if kg.jsonl missing; hooks drain learning_bus.

## 2026-07-24 | workspace | local Sheet15 DFC/RSCH TAR sync
- Added `scripts/sql/setup/local_setup_sheet15_dfc_rsch_tar.sql` (QA4→local DEATH_FORECLOSURE + RSCH_DEATH_FORECLOSURE rules, FEE_WAIVED IAD 6793 + products 1/44/45 placeholder maps). After apply flush Redis DB5 TAR cache for catalogues 22/428. Local retest: settlement Debit=Credit on child DFC + parent RSCH.

## 2026-07-24 | accounting `mfi_integration_v3.4.2.4` | TDPQA-72 trim Accrued/force-bill comment noise
- After live-schedule Accrued query: shortened verbose Javadoc/inline comments on DaoService RSTCRE repoint, force-bill resolvers/services, ChildLoanRestructuringProcessor. No logic change; live-join SUM kept. Processor rewrite already reverted earlier.

## 2026-07-24 | accounting `mfi_integration_v3.4.2.4` | TDPQA-72 Summary Accrued live-schedule query
- Reverted oversized L1a processor rewrite (`94eddfd8e` → `d5f61e19c`).
- Minimal: `getAccruedAmountByLoanAccountId` SUM joins `loan_installment_details` `is_deleted=false` (sole Summary caller). Proof: Accrued-all 2707 → live 2681 = Original 2681; Summary API Accrued=Original=2681 with orphan IAD still present. No IAD.is_deleted (column absent). Write-path Accrued clear not shipped.
- Tip was `6f500ff8e` (live join); comment-trim tip follows.

## 2026-07-24 | accounting | TDPQA-72 L1a Summary Accrued (superseded)
L1a processor rewrite was reverted; Accrued fix is repository live-join only (`getAccruedAmountByLoanAccountId`).

## 2026-07-24 | dcf harness | TDPQA-72 default child FC = loanPrepayment (ICF_USE_LOAN_PREPAYMENT=1)

Vikram non-last child FC path defaults to webapp loanPrepayment (parent PPP + RSTCRE). Opt-in Sim A: ICF_USE_LOAN_PREPAYMENT=0 for individualChildLoanForeclosure only. Parent POS≠remaining after ICF was harness-only — not an Accounting product bug.

## 2026-07-24 | workspace | CG prevention harden + DFC 0-partition fail-closed
- Harness: `ACCEPTANCE_STRICT` → FAIL when TM exists with 0 partitions (force-bill shape + DFC/RSCH GL); no soft Out-of-scope.
- JIRA: `jira-fix-adf` hit `child_gl_renamed_to_parent_name`; jira-fix-update skill note.
- KG curated: `diag:display.child_cg_gl_vs_parent_named` + `diag:env.dfc_rsch_tm_zero_partitions_local` (FTS/why).
- Local note: DFC/RSCH SUCCESS TM with 0 legs is env-systemic (product-44 PTC present; PREPAYMENT/BILLING OK).

## 2026-07-24 | workspace kb + dcf harness | Child CG* vs parent named GL (TDPQA-72)
- Root cause of wrong handoff: agents stripped CG and joined parent `general_ledger.name`; child force-bill stores `CG13336`/`CG13578`.
- Docs: memory `feedback_child_cg_gl_vs_parent_named.md`, brain `08-gl-posting-engine.md` display rule, `gl-and-placeholders.md`, SDCP-10199 runbook GL shape row, registry BILLING assert.
- Harness: `assert_force_bill_gl_shape` on child/parent force-bill (CG* vs bare). JIRA handoff comment **391531**.

## 2026-07-24 | accounting `mfi_integration_v3.4.2.4` | TDPQA-72 Accrued follows schedule + FC/DFC force-bill EMI align
- RSTCRE: after soft-delete+recreate future EMIs, repoint Accrued off deleted lids onto replacement lids (same date).
- FC/DFC force-bill labd attaches to newest Accrued EMI (same as bill amount); stops Accrued>Original by FB amount after member exit.
- Local Vikram `dcf.vikram_fc_rstcre_dfc_e2e` PASS (Obs3 + Accrued_on_deleted=0). Product: Accrued-after-rebuild = approval of shipped behaviour; only open product item = ₹1 parent vs members (handoff 391531).

## 2026-07-24 | accounting `mfi_integration_v3.4.2.4` | TDPQA-72 restore Sheet15 EXCESS_* on child+parent RSCH
- L1: child DEATH and parent last-child RSCH both push EXCESS_* again (same catalogues; undo SHG child zero + parent GL zero from `5f4661b03`/`9b6454df6` GL half).
- Keep `lapd.excess_amount=0` — that was Darpan fix for JIRA **390372** (₹54 Excess on txn UI while already in Principal).
- Targets Vikram GROSS RCV child-only EXCESS Δ (391188).

## 2026-07-24 | accounting-knowledge | Job-owned tables map (never hand-mutate IAD)
Standing rule + map: `.cursor/skills/accounting-knowledge/job-owned-tables.md`. Reject Accrued trim in DCF writer; IAD only via jobs/forceful booking. Memory: `feedback_job_owned_tables_no_hand_mutate.md`. TDPQA-72 Obs3 reconciler = hack (not restore).

## 2026-07-24 | scripts/testing + dcf_sanity | TDPQA-72 harness: batch headers + wait-by-exec-id
- `api-fire`/`batch_envelope` was missing `operation_mode=SELF` (prod scheduler sends it) → billing/accrual `postTransaction` hit NOT NULL and jobs FAILED; suite falsely blamed product.
- Also: wait used `EXTRACT(EPOCH FROM create_time)` without TZ → matched old FAILED rows; now `wait_batch_after(max_execution_id)`.
- Product `CreateTransactionMasterProcessor` unchanged (SELF default reverted).

## 2026-07-24 | accounting `mfi_integration_v3.4.2.4` | TDPQA-72 parent FB = child FB; drop harness hacks
- Product: every DFC/FC child force-bill is mirrored on parent with the **same amount** (SHG sync).
- Removed: Accrued consume-after-FB, parent EMI labd harness, alignParentNewestAccruedToAllChildren.
- ~~Kept SHG child EXCESS_*=0~~ — superseded: restore EXCESS_* GL on child+parent; lapd excess stays 0 (390372).
- FC: `RegularForeclosureForceBillService` mirrors parent after child FB.
- Verify: full Vikram matrix this session.

## 2026-07-24 | accounting `mfi_integration_v3.4.2.4` | TDPQA-72 Wave A+B genuine fixes; remove Accrued hacks
- Superseded by parent=child FB entry above (consume/alignParent removed per Darpan).

## 2026-07-23 | accounting `mfi_integration_v3.4.2.4` | TDPQA-72 Accrued≤Original invariant + CLOSED child Accrued re-lift
- `InterestAccrualBookingService`: parent Accrued aligned to Σ children before forceful book (see 2026-07-24).
- ~~`AccruedInterestToBilledOriginalReconciler`~~ removed.

## 2026-07-23 | accounting `mfi_integration_v3.4.2.4` | TDPQA-72 L1 split FC vs DFC force-bill policy
- Separate policy: `DeathForeclosureForceBillService` (value_date=reporting, cycle=death−1→next INT) vs `RegularForeclosureForceBillService` (foreclosure never backdated = business today; labd on last INT due ≤ today, not future EMI). Shared: `ForceBillBillingSupport`, `PartialCycleForceBillAmountResolver`, `AccruedInterestToBilledOriginalReconciler`.
- FC Obs3 reconcile moved after CLOSED in `loans_orc` / `group_mfi_orc` (mirror DFC Writer late pass).
- Verify: full Vikram/DFC matrix pending this session.

## 2026-07-23 | accounting `mfi_integration_v3.4.2.4` | TDPQA-72 L1 force-bill = partial-cycle (not Σ Accrued)
- `resolvePartialCycleBillAmount` / `latestPeriodAccruedAmount`: bill newest IAD period Accrued capped by reporting/BPI — matches QA4 FB≈15/16; stops lifetime Σ Accrued over-bill.
- FC processor + DFC `syncForceBillToAccruedAfterBooking` use the same helper. Orch already covers `loanPrepayment` (INDL/JLG) + ICF (SHG child).
- Verify: fresh Vikram PASS — FC FB=17 DFC FB=11 parent FB=28 (=17+11); audit fails=0. Open: parent posted≠Accrued (V2), QA4 ₹1 (V4), INDL dedicated LAN e2e not run.

## 2026-07-23 | accounting `mfi_integration_v3.4.2.4` | TDPQA-72 Obs H — FC force-bill (mirror DFC)
- `ForceBillPartialCycleInterestForForeclosureProcessor`: after accrual booking on `loanPrepayment` / `individualChildLoanForeclosure`, partial-cycle BILLING via `DeathForeclosureSettlementSupport.forceBillPartialCycleInterest` (CRN deathForeclosureDetailsId=null). Amount rule corrected in L1 entry above (not lifetime Accrued).
- Orch: `loans_orc.xml` do_prepayment + `group_mfi_orc.xml` individualChildLoanForeclosure — after `bookingNonPostedPenalProcessor`, before `updateDueDetailsForPrepaymentProcessor`.
- Explicitly **not** flipping IAD parent→last-child adjust (existing SHG booking rule).

## 2026-07-23 | accounting `mfi_integration_v3.4.2.4` | TDPQA-72 Vikram reopen + ₹1 RSTCRE @ `c0d8c52f76`
- Extracted `DeathForeclosureSettlementSupport`: force-bill = reportingAccrual (no max BPI → Accrued 14 vs FB 15); after booking bill Accrued IAD; EXTRA applied to PRIN dues then netted appropriation + child lapd; parent last-child same.
- `ChildLoanRestructuringProcessor`: single-child absorb residual (no peer ₹1 loop); multi-child fail-fast when no surplus/shortfall peer.
- Committed `c0d8c52f76` on `mfi_integration_v3.4.2.4` only (no 3.4.2.5 merge). Local e2e `dcf.group_parent_last_child_e2e` pending this session. No push.

## 2026-07-23 | accounting | SP-308 cache mobile_number only (due+bounce)
Step-scope Map<String,String> for msisdn — keeps HTTP dedupe, drops full getCustomerDetails map retention (JVM-safe). Job SMS behavior unchanged.

## 2026-07-23 | workspace | Upgrade 11-LEAN — query-plan-gate
Detect query_touched → local EXPLAIN PASS/WARN/FAIL + reuse proof; ship-loop conditional; process_matrix + impact-tests WHY. Catalog deferred as SU-PERF-IDIOMS-001.

## 2026-07-23 | workspace | IMPACT-TESTING dynamic KG resolver (reconcile+prove)
Kept change_test_map as seed only. Added impact_tests.py (git→KG writes/topics/processors→cases+WHY+stubs), ship-loop block, process_matrix impact_tests, sessionStart/pre-push banners, self_upgrade pipeline (SU-IMPACT-001 done). Proofs: sibling WHY, ship FAIL without plan, sessionStart banner.

## 2026-07-23 — Ship-test autonomy: change→impact cases (permanent)

- **Why:** Code ships were pushable after compile / wrong frozen cases / knowledge HEAD skipped money close.
- **Fix:** `register_pending_ship` on afterFileEdit; `resolve_ship_impact` always re-resolves; money fail-closed empty cases; `change_test_map.json`; penal/advance/notification domains; fingerprint + push-origin knowledge gate; post-commit `.last-ship-commit` re-register.
- **Verify:** `python3 -m unittest scripts.lib.test_ship_change_test_autonomy scripts.lib.test_kg_ship_resolve_notification scripts.lib.test_ship_change_scope scripts.lib.test_accounting_flow_domains` → OK (30).

## 2026-07-23 | workspace | SP-308 local-test gap: registry + wait_batch + ship wire
Honest miss: L0/L1 pushed compile-only. Added due/bounce batch smokes + SMS throughput assert; ship path-triggers them; fixed wait_batch_job (match run_started / `time` param). Local: config PASS + due job COMPLETED PASS.

## 2026-07-23 | workspace | Fix push-origin hang: no invented disburseLoan for SMS/MessageBroker
Root cause: `kg_ship_resolve` defaulted any MessageBroker.xml → `disburseLoan` → `disburse-quick` E2E hung KB pushes. Fix: no invent default; notification paths = service tier; knowledge-only HEAD skips auto-close.

## 2026-07-23 | accounting+notifications | SP-308/TDPQA-79 L0+L1 on 3.4.2.5
L0: SMS consumer threads 1→4, maxPollRecords 10→50. L1: step-scope cache for getCustomerDetails in due+bounce notification writers (N+1 actor HTTP). Train `mfi_integration_v3.4.2.5`.

## 2026-07-23 | workspace | Post-analysis OPTIONS BOARD (planning engine)
After RCA/Jira/perf analysis always emit L0+L1+L2+L3 (code options included); evidence-only next-step forbidden. Autopilot directive + `00-workspace-core` § board; Gate E / tiered-solutions / memory `feedback_post_analysis_options_board`.

## 2026-07-23 | workspace | Upgrade 10 — KG map enrichment (extractors)
Extractor-only close of Brain Truth Audit gaps: money aliases (`account_entry`/`client_reference_number`), Kafka topics+emits/consumes, doc nodes (392), scheduler nodes, repo-scoped request IDs (deleteUser/createTaskWorkflow), Writer CRUD, bus→graph promotion, map-completeness SELF-REPORT+doctor, 3 missing flow docs (writeoff/MJE/DCF), explicit exclusions in `build_config.json`. Rebuild 7535n/35524e; req coverage weak repos →100%.

## 2026-07-23 | workspace | Brain truth audit — coverage+SoT corrections
Fail-closed KG/brain truth vs disk on watermark `ad0a3619`. SoT: ACC `entity_type` key FIXED-STALE→RESOLVED; citation refresh (flushDb/Pending-FR/asset-criteria); GAP-079/080/081 + resolved tooling rows; edge_case entity_type doc corrected. Full: `scripts/scratch/brain-truth-audit.md`.

## 2026-07-23 | workspace | Micro-fix daily sanity kg CLI
workspace-sanity: replace removed `kg map`/`test-gaps` with validate/watermark/orient; fix test-learn.sh SLIPROD_WORKSPACE so learn probe exits 0. Daily log exit 0.

## 2026-07-23 | workspace | Upgrade 9 — sweep remainders
pr-review freshness: merged OK when head+pull agree; base = PR base.sha (not live tip). Skill `--depth` = agent-only. rule_inventory +11; skills-manifest regen (canonical `cursor-bundle/brain/`; sweep false miss). batch-write-skip + dpi-money-proof globs retargeted to 3.4.2.x live paths. kg.py --help validate/orient. intel-automation daily/weekly → `.cursor/automations/logs/` (utc|job|exit|duration, rotate 30). Skip #7 KG miss churn (ops).

## 2026-07-23 | workspace | Final full-system sweep — mechanical pre-U3 drift
Digest-first onboarding; skill dead refs (`kg.py test-gaps`, tiered-solution-approach.mdc, gbuild.sh); sync-branches primary (git-workflow, mixed-train, memory, OPS-INDEX); glob path fixes (dcf docs, disburse reset script); config.yml mcp-atlassian comment→plugin. Structural: pr-review merged-PR freshness hard-exit, rule_inventory lag, skills-manifest missing, batch-write-skip/dpi globs, KG telemetry misses — proposed only. Details: `scripts/scratch/final-sweep-details.md`.

## 2026-07-23 | workspace | TDPQA-72 close-out — harness fail-exit + D8 + registry pins
ntest `_run_flow_case` applies registry `defaults` + coerces unrecovered printed `FAIL:` to exit ≠0 (`ntest.dcf_e2e_fail_exit`). D8 asserts `interest_details.accrued_amount`/`original_amount` with SQL parity / INT-0 guard. Promoted: `ntest.dcf_e2e_fail_exit`, `dcf.non_last_rsch_amount_eq_principal`, `dcf.parent_statement_dfc_prtl`, `dcf.parent_member_future_int_parity`. D-matrix local Pass; QA4 NOT-VERIFIED; product Qs open for non-last amount≠prin + ₹1 schedule.

## 2026-07-22 | workspace | Upgrade 8 TASK E — local-parity gate
ship-discipline + process_matrix `local_parity` (conditional schema/masterdata): migrations/seeds must back local schema; duplicate Flyway versions fail (GAP-077); DDL hand-patches via db-local-write logged and must match Flyway/initial-setup (GAP-076 class). Fixture UPDATEs ignored. Summary: `LOCAL PASS — parity: migrations ✓ / seeds ✓ (predicts <train> envs)`.

## 2026-07-22 | workspace | Upgrade 8 — process router + LEARN + SELF-REPORT
process_matrix.json (18×7) + process_router PLAN/TTL/money-cell ratchet; autopilot prints PLAN and honors SKIP/CACHED on steps. super-agent close = LEARN lifecycle (captured→proposed→…); weekly intel: bus age + SELF-REPORT.md. Doctor WARN alwaysApply >35KB soft ceiling. Fast = selection, never weaken money required cells.

## 2026-07-22 | workspace | Upgrade 7 — QA bar self-improving
Enforced acceptance: death_foreclosure+disbursement+repayment+foreclosure (ratchet). All 56 money cases declare verify_mode. registry-proposals auto-draft + gap miner; ntest telemetry + flaky quarantine proposals; capture-flow Dev-Test ADF + jira-handoff --dry-run (post gated).

## 2026-07-22 | workspace | Upgrade 6 — KG train-safety (light)
Money-task KG STATE banner + HARD STOP on PROVISIONAL/mismatch; MCP/CLI provenance header; kg-session-sync/kg-switch telemetry (last 20); doctor consecutive-miss/slow-build flags; decision doc defers multi-profile overlays (`brain/decisions/kg-profiles.md`).

## 2026-07-22 | workspace | Upgrade 5 — mixed-train banner + scoped sync + env-matrix
Computed TRAINS banner in autopilot + HARD STOP on [MIXED] money/cross-service (00/10 gates). sync-branches --domain/--train/--yes foot-gun guard; sync_branches_v2 thin deprecated wrapper. scripts/env/env-matrix.json + TODO + env-smoke → ops-state. OPS-INDEX + ops-bin-hygiene (grandfather pre-U5 orphans). Cross-env: NOT VERIFIED ON &lt;env&gt;; forbid “verified” for local evidence vs named QA.

## 2026-07-22 | workspace | Upgrade 4 — KG MCP + gate tiering + arch digest
trustt-kg MCP (stdio wrapper over kg.py); mcp-atlassian dead entry removed (use plugin; rotate exposed token). Self-expansion READ-ONLY proceed / MUTATION stop-wait. architecture-digest.md bootstrap. TASK0 archive-only mandates promoted or justified.

## 2026-07-22 | workspace | Upgrade 3 — collapse alwaysApply redundancy
28 alwaysApply → 5 thematic (`00/10/20/30-*.mdc` + `darpan.mdc`), ≤45KB. Verbatim archives in `.cursor/skills/workspace-gates-reference/`. Mandate checklist 153/153 preserved. Thin `.cursorrules` + `AGENTS.md`. Mapping: `scripts/scratch/upgrade3-mapping.md`.

## 2026-07-22 | workspace | Upgrade 2 — defuse accounting/architect glob bomb
Thin `accounting.mdc` (gates+routing) + `.cursor/skills/accounting-knowledge/` topic files; deleted `accounting-module-knowledge.mdc`. Thin `architect-thinking.mdc` + `.cursor/skills/architect-thinking/`. Digest cap 14KB with Medium/Low index. U1 residual gaps READ mandates → digest-first.

## 2026-07-22 | workspace harness | Fresh+EXTRA loanRepayment seed PASS (134253 + future-EMI EXCESS)
- EXTRA seed: unique per-phase receipt/CRN (no ReceiptNumberDedup 134253); phase2 pays full advance cycle after labd; `DCF_FRESH_EMI_MONTHS_BACK=2` so advance EMI is past (future dues post EXCESS_AMT). Fresh+EXTRA PASS parent 6004093925; S2 pin EXTRA reaffirmed. GAP-074 still OPEN.

2026-07-22 | workspace | gaps digest token-tax cut
Session bootstrap reads `.cursor/gaps-and-risks-digest.md` (≤10KB, High verbatim) instead of full gaps-and-risks.md; escalate to SoT when GAP-id/area flagged. Builder `scripts/bin/build-gaps-digest.sh`; regen in intel-session-sync.sh. Added `.cursorindexingignore` (excludes cursor-bundle/kg/ etc from indexer).

2026-07-22 | workspace harness | DCF matrix true-results — full scope + fresh disburse PASS
- Registry `dcf.group_parent_last_child_e2e_full` (ACCEPTANCE_SCOPE=full); RSTCRE drain retry; non-last txn-audit phase. Matrix @935c527430: S1/S2/full/fresh(SEED_EXTRA=0) PASS. GAP-074 still OPEN (INT-180 parked). Fresh+EXTRA seed 134253 documented.

2026-07-22 | workspace harness | DCF e2e vs accounting `935c52743` — Pass SEED_EXTRA=0|1 obs123
- group_parent_last_child_dfc_local_e2e: ACCEPTANCE_SCOPE obs123|full (GAP-074 Out-of-scope vs fail); last-child Obs2 amount==principal excess=0; force-bill asserts via CRN shape accountId||17…[||dfdId] (GL posts, not LAN/narration); legacy CRN collision gate; two-phase EXTRA loanRepayment. Local Pass pin 6000137433 DEATH_DATE=2025-08-02. Product CRN fix owned by accounting SHA (sibling).

2026-07-22 | workspace | automation gates — impact matrix, KG watermark, registry companion
- ship_discipline: extended impact_analysis (entry_paths/scenario_modes/downstream/out_of_scope); service tier on accounting/payments/LOS. New kg_watermark_gate + registry_companion_gate; autopilot end/close hardened; ntest validate on service/money close; enrichment-audit pre-push blocks stale KG/changelog.

2026-07-22 | accounting `9b6454df6` | mfi_integration_v3.4.2.4 | TDPQA-72/SDCP-10199 parent force-bill + RSCH excess=0
- DeathForeclosureInsuranceWriter: parent forceBillPartialCycleInterest before RSCH; zero parent EXCESS_* + lapd.excess; BLD_INT clear; receipt/local-map hygiene. Matrix PASS EXTRA=0|1 + EMI seed. GAP-075 Product update.

2026-07-21 | workspace | Fail-closed cross-branch reuse (no false-positive ports)
- `fixed-elsewhere` now requires unique SHA resolve + auto diverge → VERIFIED_FIXED_CLEAN only for REUSE_ALLOWED; FILE_TOUCH_HINTS/DIVERGED/stale = REUSE_FORBIDDEN. Autopilot no longer swallows lookup failures. Memory `feedback_cross_branch_no_false_positive.md`. Watermark honesty in BRANCH-SAFETY.

2026-07-21 | workspace | Cross-branch fixed-elsewhere + forward-port train tooling
- `kg fixed-elsewhere` verifies KG case SHA containment on higher upstream trains; `fwd-port.sh` restores train/path/missing/diverge/audit; autopilot runs lookup for explicit BUG/FIX apiNames with 12h upstream freshness.

2026-07-21 | accounting `ac8f185bbc` | mfi_integration_v3.7.1 | TDPFR-547 DPI due/overdue from amountMap
- LoanRecurringPaymentBatchProcessor: dpi_due/dpi_overdue use fresh per-LAN amountMap (not chunk-shared EC). Sim: collections.tdpfr547_dpi_amountmap_sim.

2026-07-21 | initial-setup (uncommitted) | mfi_integration_v3.4.2.5 | TDPQA-54 masterdata V000125 seeds disburse Redis TTL configs
- product `V000125__tdpqa54_disburse_redis_inflight_ttl_config.sql`: `mfi.disburse.loan.producer.marker.ttl.ms` (LOS) + `mfi.disburse.loan.consumer.lock.ttl.ms` (ACCOUNTING) = 600000. Prod pack: `scripts/sql/deploy/prod_pre_V000125_tdpqa54_disburse_redis_ttl_config.sql` (Pre; `schema_version`).

2026-07-20 | accounting 7e1642a57e | mfi_integration_v3.4.2.4 | Parent disburse 134126 on member multi REP_ACCT; remove CLB keepAtMostOneRepAcct trim
## 2026-07-20 | workspace | no auto-open documents (opt-in IDE open)
- `open-final.sh` default prints path only; `--open` / `OPEN_FINAL=1` to open. Rule+skill flipped; memory `feedback_no_auto_open_documents.md`. sessionStart hooks do not open HTML.

## 2026-07-19 | lib `793ebabbcd` + acct `d982430d1` | bank HTTP wire INFO (CRR JSON unchanged)
- Platform-lib: `WebClientServiceExecutorDecorator` + `AbstractJSONRestServiceExecutor` put/log `http_wire_request`/`http_wire_response` (post-XML / pre-JSON) without overwriting EC `request`/`response`. Accounting: `DisbursementBankCrrLogHelper` companion INFO at CRR save; parent/child NEFT CRR via helper. NEI `NeftV2BankReferenceUtil` JSON parse intact. Sim: `disbursement.neft_crr_exact_audit_callback_sim` updated (`ab50830`).

## 2026-07-19 | acct `ed9b610cc`+`f2491e99c` | accounting-v2 | mfi_integration_v3.4.2.4 | Mandate CASA match on createOrUpdateLoanAccount
- After ≤1 REP_ACCT (134126), DIRDR/ACH must match pre-created mandate CASA (`DisbursementRepaymentMandateMatchValidator`; 134382 / 134348). MFI `customValidate…` + product `ValidateDisbursement…`. CLB threads `group_id` (+ `group_details` fallback) and `loan_application_id` from external_ref. Sim: `disbursement.clb_mandate_match_sim` PROCESSOR_MIRROR_SIM.

## 2026-07-19 | workspace | Money ship impact_analysis fail-closed gate
- `ship_discipline_gate` requires `impact_analysis` keys for money pending; CLI `--impact-*`; memory `feedback_full_impact_analysis_before_money_ship.md`.

## 2026-07-19 | workspace | CRR callback column assert gate (disbursement money-tier)
- Hole: backlog `disbursement` skipped all `acceptance_coverage` checks → NEFT callback PROCESSOR_MIRROR_SIM shipped without `client_reference_number` assert. Fix: `db_assert_enforced_on_money_tier` + required CRR columns; sim asserts paymentref client_ref; memory `feedback_crr_callback_column_assert.md`. Self-test 3c rejects weak CRR sim.

## 2026-07-19 | acct `ca558ec186` | accounting-v2 | mfi_integration_v3.4.2.4 | CLB REP_ACCT dedupe + NEFT CRR exact audit
- Write-path: `ChildLoanBookingEventsQueueDataPopulator` skips parent `REP_ACCT` append when member already has one + `keepAtMostOneRepAcct`. NEFT: `DisbursementBankCrrLogHelper.saveWithExactAudit`, `responseForClientRequestLog`, inbound `persistInboundCallbackCrr` `*_CALLBACK` on `DoGenericSyncSTPBankNeftCallBackProcessor`. Sims PASS: `disbursement.clb_rep_acct_dedupe_sim` (PROCESSOR_MIRROR_SIM), `disbursement.neft_crr_exact_audit_callback_sim` (ORCH_SIBLING_SIM+PROCESSOR_MIRROR_SIM). Ops poison rows: `scripts/sql/adhoc/clb_dedupe_rep_acct_events_queue.sql`.

## 2026-07-19 | workspace | CRR ops SQL — contract-native FAIL first (not local-archive)
- Standing correction: prefer keep `status=FAIL` + `eligible_for_retry=false` + optional `~` LAN over inventing/`LOCAL_RESET_ARCHIVED` as default. Decision ladder in `prod-ops-sql-impact-gate.mdc` + skill; memory `feedback_prod_ops_sql_crr_impact_gate.md` rewritten; minimal-fix scope includes ops SQL; autopilot OPS_SQL directive asks “is contract-native FAIL enough?”. Prior changelog row that preferred `LOCAL_RESET_ARCHIVED` for prod is superseded.

## 2026-07-19 | workspace | prod-ops-sql-impact gate (CRR status miss)
- Miss: adhoc `prod_neft_v2_fail_reset_to_dtfc_reinit.sql` used invented `PROD_NEFT_V2_FAIL_ARCHIVED` without caller matrix. Rule `prod-ops-sql-impact-gate.mdc`, skill `prod-ops-sql-impact`, autopilot `OPS_SQL`, memory `feedback_prod_ops_sql_crr_impact_gate.md`. *(Superseded same-day: prefer contract-native FAIL, not LOCAL_RESET_ARCHIVED as default — see entry above.)*

## 2026-07-19 | workspace | open-final-file (IDE final buffer vs Review diff)
Skill `.cursor/skills/open-final-file/`, rule `00-workspace-core.mdc`, script `scripts/bin/open-final.sh` — agents open forwardable files via MCP `open_resource` / `cursor -r` (final content); `[Review](…#changes)` stays diff-only.

## 2026-07-17 | workspace | DPI grace_overlap column-audit settle-poll (harness race, not product bug)
- RCA: `dpiAccrualBooking` marks Spring Batch COMPLETED before `accrual_posting_date` writes are visible on a fresh psql conn (partition COMPLETED races JPA flush on cold local JVM). Column audit fired immediately → transient `posted_slice_missing_posting_date` ×2 on seal-anchor slices (05-31 month-end, 06-14 EMI2 due); apd settles ~1s later. Final product state correct (accounting repo unchanged — no product fix).
- Fix: `scripts/dpic/lib/run_dpi_column_audit.sh` bounded settle-poll (AUDIT_SETTLE_TRIES=10×1s) re-runs slice+booking audit until 0 or timeout; genuine persistent violation still fails (no masking). Shared gate → benefits all 5 dpi e2e callers. grace_overlap PASS ×2. Also cleared 28k-row `mfi_batch` dpi metadata bloat (status-flip lag source).

## 2026-07-17 | workspace | code-comment lint + JIRA mode comment validation
- Primary: `java_comment_lint.py` / `java-comment-lint.sh` fail-closed on DPI narrative comments (consecutive `//`, ticket/parity essays); wired into money `ship-loop-gate --from-pending`. Memory RULE 1 points at the gate.
- Secondary: `jira-fix-adf.py validate_mode_comment` — SDCP short ping (or omit); TDPQA structured rca+impact+dev; pack carries `comment_id` for edit-in-place. Tests: `test_java_comment_lint.py`, `test_jira_fix_adf.py`.

## 2026-07-17 | workspace | PR review zero-false-positive hardening
- Fresh base/head/ref provenance, proof-only confidence taxonomy, developer-claim separation, codebase-specific absence/value/scope guards, money runtime bar, and mandatory finding-falsification pass.

## 2026-07-17 | DPI foreclosure BPD day-window (mfi_integration_v3.7.1)
- `DpiForeclosureBrokenPeriodService`: project gap from business date (not nextDay) + HALF_UP 0dp; SHA `e2789d5f05` — QA LAN 6003768627 expects bpd ₹29.

## 2026-07-17 | acct `48f9461f1` + workspace | TDPQA-72 DFC hardcoding + real-flow DB-write gate
- Accounting: `DFC_PRTL_BILL_` → `FORCE_BILL_CLIENT_REF_PREFIX` constant + `build/isForceBillClientReference` helpers; `reconcileAccruedInterestToBilledOriginal` slimmed 99→68 LOC (same 2 phases). Real-flow e2e PASS (FB labd prin=0 + EMI preserved, Obs3 Accrued==Original, Obs2 amount==principal).
- Blast radius `findByLoanInstallmentDetailsId ORDER BY id DESC LIMIT 1`: all callers null/reversed-only → multi-row (EMI+FB) safe; real DB proof both children.
- Workspace upgrade (fail-closed): `acceptance_coverage.py` now requires value-level `db_asserts` vs `domain_money_tables` for enforced money domains (presence-only rejected); memory `feedback_real_flow_db_write_validate.md`; rules ship-test-mandatory / code-backed-sim / agent-quality-gates Gate D / workspace-contract / workspace-developer-tester. Self-test 6/6 PASS.

## 2026-07-17 | workspace | fail-closed reuse-query discipline gate
- Repository/DAO query-semantic diffs now require reuse-ladder step, checked methods/callers, and index/scan/limit performance evidence in ship discipline; step 3 requires justification. Focused gate suite: 18/18 PASS.

## 2026-07-17 | acct `ff19f0c8c` | TDPQA-72 comment strip (keep labd ORDER BY)
- Strip TDPQA-72 / A2+B / Accrued explanatory comments in `DeathForeclosureInsuranceWriter` + Repository.
- **Query not removable:** `findByLoanInstallmentDetailsId` keeps `ORDER BY id DESC LIMIT 1` (dedicated force-bill multi-row labd; no existing list finder for Java pick). Behaviour unchanged; KG SKIP.

## 2026-07-17 | TDPQA-72 port to mfi_integration_v3.4.2.4
- accounting `29bd01e8a6`+`dfec1e60f1`: cherry-pick dedicated force-bill labd + Accrued≤Original reconcile onto upstream tip (`5b1b928ed` already present).
- Files: `DeathForeclosureInsuranceWriter.java`, `LoanAccountBillingDetailsRepository.java` only.
- Verified RUNTIME on train JVM: ACCEPTANCE_STRICT=1 DCF_SEED_EMI_LABD=1 SEED_EXTRA=1 parent=6002329725 — Issue A/B + Obs1b/Obs3 + webapp APIs PASS.

## 2026-07-17 | acct `a7e6d1d1c4` | TDPQA-72 Obs3 Accrued≤Original + webapp gate
`DeathForeclosureInsuranceWriter.reconcileAccruedInterestToBilledOriginal` (zero IAD past billed INT + trim Accrued excess to getBilledInterestAmount). E2e `assert_accrued_le_original` + `assert_webapp_bound_apis`. Acceptance coverage WEBAPP_UI_FIELD_MARKERS. Memory: feedback_tdpqa72_obs3_accrued_original, feedback_webapp_verify_mandatory_ui_ships. GAP-075 Obs3. Fixture: equivalent local product-70 (QA LAN clone blocked).

## 2026-07-17 | TDPQA-72 / GAP-075 QA acceptance (Obs1+Obs2)
- accounting `cae54fd9d6`: dedicated DFC force-bill labd (no EMI hijack) + last-child lapd principal=EXTRA-net + excess; workspace acceptance_coverage gate + strict e2e. Evidence: parent 6000023640 RSCH amount=principal=7654 excess=333; EMI_LABD_FIXTURE preserved + FB labd interest=27 on same installment.

- **2026-07-16** | JIRA enrich fast path: `jira-fix-adf.py pack`, `jira-enrich.sh` (venv + cached OAuth), token cache in REST helper; SKILL fast-path — skip field-meta API and multi-subprocess ADF chain.
- **2026-07-15** | GitHub org/repo rename hygiene: canonical map `scripts/lib/github_repo_map.{sh,py}` (`trusttai` + `trustt-*`); sync scripts set origin/upstream from map (was wrongly using local `novopay-*` folder for forks); docs/hooks/memory/rules updated; `python3 scripts/lib/github_repo_map.py verify` → 20/20 OK.
- **2026-07-15** | jira-fix-update: TDPQA handoff comment now **requires AITDP** (Yes + % + remarks) via `handoff_comment`; posted handoff on [TDPQA-72](https://novopay.atlassian.net/browse/TDPQA-72) (comment `388281`) and refreshed AITDP on TDPQA-102 (`388253`).
- **2026-07-15** | jira-fix-update: TDPQA `comment_handoff` — RCA/Impact/Dev go in one structured comment (`handoff_comment` + `owners_tdpqa`); no companion SDCP for missing fields. Memory `feedback_jira_tdpqa_comment_handoff.md`.
- **2026-07-15** | TDPQA-102 pushed | accounting-v2 `163201d86` on `mfi_integration_v3.4.2.4` — child SHG reopen payment components parity; sim `reopening.child_payments_parity_sim` PASS.
- **2026-07-15** | workspace post-ship knowledge closure for A2+B DFC: GAP-075 RESOLVED, runbook/registry/scenarios/edge/flows + memory `feedback_post_ship_registry_runbook_gap_mandatory.md` + ship-knowledge-gate companion WARN. Code already @ acct `5b1b928ed` / ws `7d22003`.

- **2026-07-15** | workspace once-and-for-all: `ship_discipline_gate.py` fail-closed (minimal/hot-path/verify_mode/KG/assumptions); path-absolute smoke+enrichment; `00-workspace-core.mdc`; restore `super-agent corroborate`; max-pass self-heals enrichment-sync. Memory `feedback_workspace_once_and_for_all.md`.
- **2026-07-15** | workspace: code-backed simulation testing rule + platform suite — prefer realtime; if stage blocked use orch sibling / processor mirror (`orch_sibling_parity.py`); registry `reopening.child_payments_parity_sim` (TDPQA-102); domain `reopening` in accounting_flow_domains.
- **2026-07-15** | accounting-v2 `group_mfi_orc.xml` (`mfi_integration_v3.4.2.4`): TDPQA-102 — `childLoanReopening` now runs `initiateClosureTaxReversalProcessor` + `loanAccountPaymentsDetailsReversalProcessor` (parity with parent `loanAccountReopening` approve path) so child reopen reversal txn gets `loan_account_payments_details` component rows.
- **2026-07-15** | accounting-v2 `5b1b928ed` (`mfi_integration_v3.4.2.4`): last-child parent DFC A2 EXTRA-net statement amounts + B force-bill labd txn_ref persist/link (`DeathForeclosureInsuranceWriter`); e2e harness under `scripts/dcf_sanity/group_parent_last_child_dfc_*`.
- **2026-07-15** | TechOps disbursement guide SHG≠JLG≠INDL accuracy pass: truth matrix + Applies-to callouts; §04=flat INDL/JLG, §05=SHG parent–child (MFT PARENT_SUCCESS vs NEFT note); LAR/reinit/SQL Q3/walker scoped; Desktop↔brain md5 identical (`74f6d3f0`).
- **2026-07-15** | Synced `cursor-bundle/brain/guides/disbursement-guide.html` from Desktop NEFT-v2-complete guide (3.4.2.4); Desktop kept as authoritative source (md5 `1eecccb3cd3ffa1ac79c5dfd8a65fef4`).
## 2026-07-13 | accounting-v2 | Revert SDCP-11058 from **3.4.2.2** and **3.4.2.3** (keep **3.4.2.4**)
- Reverted `8d9f0feed8` (BPI distribute in `ChildLoanForeclosureProcessor`) on origin `mfi_integration_v3.4.2.2` @ `bb6b37d178` and `mfi_integration_v3.4.2.3` @ `682afe5ca2`. Fix retained on upstream/origin path for **3.4.2.4**. PR into upstream still required for 2/3. Release trains `mfi_release_v3.4.2.2` / `.3` still contain the fix until merge or matching revert.

## 2026-07-10 | workspace | AiTDP Remarks = agent-help narrative (no Cursor brand)
SDCP-11058 remarks rewritten; jira-fix-update skill + fields-reference + `jira-fix-adf.py` scan (`\bCursor\b`); memory `feedback_jira_aitdp_remarks_no_cursor_brand.md`.

## 2026-07-10 | workspace | jira-fix-update skill
SDCP-11058: forbidden-token pre-flight scan + mandatory assignee/owners; cleaned ticket fields/comment (removed 3.4.2.2 / harness Dev Test). Memory: feedback_jira_enrich_forbidden_scan_assignee.md.

## 2026-07-10 | SDCP-11058 ship target **mfi_integration_v3.4.2.2** (not 3.4.2.1)
- Cherry-pick BPI distribute fix onto upstream 3.4.2.2 tip; pushed origin `mfi_integration_v3.4.2.2` @ `8d9f0feed8` (ChildLoanForeclosureProcessor). Standing: train sync-first gate in `10-quality-gates.mdc` + `feedback_train_branch_sync_origin_upstream.md`.

## 2026-07-10 | SDCP-11058 | accounting-v2 `4acc7036d4` | SHG parent foreclosure BPI distributed to children (any N) via getDistributedAmountEqually — sum(child BPI)==parent quote; gap RESOLVED; ntest foreclosure.shg_bpi_parity PASS

## 2026-07-10 | workspace | GAP-074 INT-180 parked off 3.7.1 (open gap)
- Last-child DFC parent residual INT (latent 3.4.2.1+) / DPI residual risk on 3.7.1 kept **OPEN** (not RESOLVED). Fix parked on `fix/sdcp-10199-parent-int-dpi-last-child-dfc` @ `61278d5f8` — **do not merge/push to `mfi_integration_v3.7.1`** until QA/prod discuss. ASK-057 DEFERRED; dual-home gaps + MEMORY synced. Integration tip remains `f45dbe3bd`.

## 2026-07-10 | workspace | Gap-closure: harmony H01–H10 + kg validate/orient + train matrix
- Wired `kg validate`/`orient` into kg.py; hooks/docs already ship-path; gaps SoT dual-home; mixed-train-matrix runbook; MEMORY ask-tracker gate; capture-flow fid fix + DFC footprint; thin-domain backlog WS-025..034; nps_app_log ops-state hardened.

## 2026-07-10 | accounting-v2 `61278d5f8` | (later parked) | SDCP-10199 INT-180 last-child parent INT settlement
- Was committed on 3.7.1 then **parked** to `fix/sdcp-10199-parent-int-dpi-last-child-dfc` (see GAP-074 open entry above). Parent overdue INT/DPI from parent pending; local e2e PASS×2.

## 2026-07-10 | workspace | Harmony FAIL fixes (hooks/ship/docs/gaps/scripts/ops)
- hooks.json: afterFileEdit→after-ship-path-edit.sh; wire post-commit-ship-test.sh. Re-pending dirty DeathForeclosureInsuranceWriter. Changelog JIRA count=9. brain CHANGELOG non-ancestor 3.7.1 SHA labels corrected. gaps dual-home INT-180 synced. Restored workspace-bootstrap.sh + install-user-cursor-gates.sh wrappers. nps_app_log added.

## 2026-07-10 | workspace | Accounting-wide self-upgrade (domains + JIRA + stale train banners)
## 2026-07-10 | workspace | JIRA graph v3 maximally verified (orch+HEAD+e2e)
- Rebuilt `cursor-bundle/brain/jira/` from orch Request + Java on 3.7.1 + ancestor/HEAD-equivalent SHAs. INT-180 e2e PASS×2; parent INT pending 0. kg_validate OK. No speculative related edges.

- `accounting_flow_domains.json` v2: canonical_train 3.7.1, writeoff domain, DFC release_cases, portfolio/insurance notes, jira pointers. Registry domain tags + `_meta`. JIRA graph v3: **9 verified nodes** (`cursor-bundle/brain/jira/jira-flow-graph.json`). Stale banners: workspace-state, dpic-demo-local, DFC walkthrough, child-FC. Backlog WS-019..021 (portfolio/writeoff/walkthrough rewrite). INT-180 e2e PASS earlier this session.

## 2026-07-10 | accounting-v2 WIP | mfi_integration_v3.7.1 | SDCP-10199 last-child parent INT settlement + JIRA flow graph
- Root cause: last-child parent appropriation used child `INT_AMT`, leaving overdue billed INT pending (fixture 180 on due 2025-09-01) on CLOSED parent. Fix: `sumPendingComponentOnOrBefore` via `getDueDetails` + Java; also `waiveFutureDpiPastReporting` on parent. `ntest run dcf.group_parent_last_child_e2e` PASS. JIRA graph: `cursor-bundle/brain/jira/`.

## 2026-07-10 | workspace + acct | SDCP-10199 on mfi_integration_v3.7.1 — forward-merge confirmed + knowledge sync
- Verified tips of 3.4.2.1/2/3 + release 3.6.1 are ancestors of 3.7.1 (`f45dbe3bd`); key SHAs e919e3b33/66e830670/425472cab present. Removed dead `waiveFutureParentPendingDuesOnLastChildDfc` (unused; would waive parent PRIN). Enriched e2e DPI pending assert, scenarios/registry/release-trains/runbooks/gaps/system_brain.

## 2026-07-10 | workspace | Disbursement suite gap cleanup
- `--help` before run lock + stale-PID auto-clear; `disburse-indl-quick.sh` + registry `disbursement.indl`; stale FILES/README/DPIC/NEFT-v2 refs fixed; non-child NEFT `NEFT_STAGE_*` accepted as WARN (INDL local awaiting NEI)

## 2026-07-10 | workspace | DPI harness sync to mfi_integration_v3.7.1 product rules
- Quick profile: milestones two_emi + booking_anchor_next_due + column audit; booking guard matches 77921d275f any-EMI-due; SEED_CALC_WINDOW default 0; DPI_TEST_COVERAGE + branch gate updated

## 2026-07-10 | accounting-v2 `77921d275f` | mfi_integration_v3.7.1 | dpiAccrualBooking EMI-due posting anchor (sealed_unposted audit)

## 2026-07-10 | workspace | mfi_integration_v3.7.1 release blockers closed
- SDCP-11030: grace-overlap verify SQL aligned to EMI2 ownership (412f4d03e); e2e + column audit PASS
- SDCP-11016: DEFAULT FC sim BPD growth harness (`run_foreclosure_bpd_growth_e2e.sh`) PASS 54→68.68
- SDCP-11048: loanPrepayment APPROVE billed-DPI amount gate harness PASS (132268 without DPI)

- 2026-07-10 acct 412f4d03e3 @ mfi_integration_v3.7.1: DPI slice owner = latest EMI due on/before segStart (not grace lastAnchor); EMI1 Jun seal →14-Jun not →18-Jun overdue; LAN 8101960/6004055825 daily+milestone PASS.
- 2026-07-10 acct 4321639df @ mfi_integration_v3.7.1: DPI grace gate-only — stored overdue_date >= admission (grace-0 overdue=due valid); first slice start=due_date; reverted slice-engine mutations; fresh LAN 8101960/6004055825 column audit 0 PASS.
- 2026-07-10 acct b78e1113c @ mfi_integration_v3.7.1 (origin): grace stored overdue + backfill + EMI1 seal ported from 72e461e10; build PASS; SDCP-11030/11012 e2e PASS; 8060160 EMI1 slice May14-May20 column audit 0.
- 2026-07-10 acct 72e461e10 @ feature/delayed_payment_interest: L1 DPI grace — resolveAdmissionOverdueDate (stored overdue_date), penal >= gate, due-date backfill, EMI1 seal due→next EMI due; june slice + grace overlap + column audit 0 violations on 8060160/8057160. Push pending (ship-close post_maturity unrelated FAIL).
- 2026-07-10 acct e175b78cb @ mfi_integration_v3.7.1: SDCP-11048 JIRA enriched; loanPrepayment approve validation includes billed DPI+BPD (844081f83); DPI fixture 8060160 june-slice job proof + billing + ntest batch.dpi_* PASS.
- 2026-07-10 workspace: DPI harness — run_dpi_three_job_verify.sh (ntest batch APIs), run_dpi_column_audit.sh, extended verify_dpi_accrual_slice_integrity.sql + booking/billing audit; registry dpic.three_job_verify* + ntest wait_batch; purge_batch job_time|time param fix.
- 2026-07-10 acct 068247cc9 @ mfi_integration_v3.4.2.2: SDCP-10227 L1b — updateLoanAccountFillerNewTransaction on INDL/JLG flat bank fail + SHG parent mirror; fillers survive fatal raise. Pushed.
- 2026-07-10 workspace: SHG S6 harness staging — `_force_shg_s6_child_ft_stage` archives `LOAN_DISBURSEMENT_EXTREF*_MFT`, resets ACCTWB CLMT to P, restores parent MFT SUCCESS after S5; S6 uses LOAN_BOOKED + child-fail assertions (fillers, ext_delta).
- 2026-07-10 workspace: Disbursement suite cleanup — removed dead `regression_driver`/Makefile/mock targets; canonical payloads only under `scripts/disbursement/payloads/canonical/`; INDL `370164` payload added; registry `disbursement.jlg` → full stage via `disburse-quick.sh`.
- 2026-07-09 acct @ mfi_integration_v3.4.2.2: SDCP-10227 SHG has_child_accounts — child CLMT bank error → parent filler_1/2 + getLoanAccountDetails promote; JLG/INDL flat path unchanged.
- 2026-07-09 acct @ mfi_integration_v3.7.1: SDCP-11016 foreclosure sim `bpd_amount` — project DPI for future foreclosure dates (parity with `bpi_amount`); webapp maps `billed_dpi`/`bpd_amount` on simulation screen.
- 2026-07-09 workspace: Job-first DPI verify session — purge + `reset_dpi_fixtures.sh`; full regression 11/13 PASS; june_slice_job_proof PASS (8060160 slice integrity 0 violations); two_emi FAIL (calc 2026-06-21); ud_compliance harness path bug.
- 2026-07-09 acct b157b2d33 @ mfi_integration_v3.7.1: Rebooking/schedule interest day-count — GenerateRepaymentScheduleProcessor.ensureInterestCalculationDayCounts from product_scheme when EC blank; ReducingBalanceInterestAmountCalculator fail-fast 130045/130046 (pairs Ramya 00292b217 resolveDaysInYear). LAN 6003960930 local scheme DIY_360/DIM_30.
- 2026-07-09 acct 425472cab @ mfi_integration_v3.4.2.1: SDCP-10199 QA6 display gaps — RSCH payment principal not doubled (net_amount=0 last child); overview clears next EMI when loan_status CLOSED; account.status CLOSED on parent finalize. e2e extended.
- 2026-07-09 workspace: DPI job-first harness — dpi_call_batch/dpi_call_eod_chain in dpi_demo_fixture.sh; SEED_CALC_WINDOW default 0; dpi-june-slice-proof.sh + registry dpic.june_slice_job_proof; DPI_TEST_COVERAGE audit table.
- 2026-07-09 workspace: SDCP-11030/11012 verified on mfi_integration_v3.7.1 @5645a9dc0 — grace overlap + two-EMI chain PASS (8057160); SHG parent=sum(children) PASS (116360/6000001074 parent=624); harness run_dpi_shg_parent_child_parity.sh + registry dpic.shg_parent_child_parity + full_regression quick step.
- 2026-07-09 acct 5645a9dc0: DPI calc window watermark (run EOD when max end=today), seal dormant grace-overlap open rows at month-end, row end=lastActiveDay on seal; verify_dpi_accrual_slice_integrity + two-EMI chain gates. LAN 6004041325: slices May14/May31, Jun01/Jun14, Jun15/Jun17 tail, EMI2 Jun14/Jun30; DPI due ₹42 Jun-14; grace/overlap/multi-emi/posting_calendar PASS. Pushed mfi_integration_v3.7.1.
- 2026-07-09 workspace: DPI JIRA regression harness — dpi-booking-posting-guard aligned to businessDate|end_date anchor (4d44f2f92); compute_dates 60d gap; disburse demo path + reset script path; verify_dpi_billing_ud next-EMI filter; QA1 fixture undelete serial 6-8; post-maturity SQL date vars; go_live_ud product join.
- 2026-07-09 acct 4d44f2f92: DPI EOD inclusive calc day (processThrough=nextDay(today), inclusive walk, cursor=nextDay(segmentEnd), resolveSliceStart); booking posts when businessDate OR end_date is PRIN/INT due/month-end. Full chain LAN 6004041325: DPI due ₹42 on EMI2 due; posting calendar + EOD txn + go-live UD + integration smoke PASS. Pushed mfi_integration_v3.7.1.
- 2026-07-09 acct e1875d1b4: DPI calc interest-parity refactor (segment=due/month-end seal, nextDay watermark, in-run seal tracking); booking posts on PRIN/INT due or month-end only (not PINT). Full chain LAN 6004041325: ₹18+₹19+₹4 tail, DPI due ₹37 on EMI2 due. Pushed mfi_integration_v3.7.1.
- 2026-07-08 workspace: SDCP JIRA ADF enrichment workflow — improved `jira-fix-adf.py` (scenario/dev/test_result/comment/mention ADF helpers), added `jira-fix-handoff.sh`, added `mentions.json`, and expanded JIRA skill/field docs for correct RCA/Impact/Dev evidence + AITDP metrics.
- 2026-07-08 workspace: local DB write gate — `db-local-write.sh`, `purge-local-dpi.sh`; `darpan.mdc` allows localhost writes; `db-local.sh` ignores QA PGHOST; `purge_local_dpi_all.sql` local-schema fixes.
- 2026-07-08 acct a66900048: DPI accrual seals = due date + month-end only (interest/penal/UD); grace only via daily base/anchor day-walk — no overdue-date dpi_accrual_details rows. Core E2E grace/overlap/multi PASS on 8057160.
- 2026-07-08 acct 46f115199 (mfi_integration_v3.7.1 via feature/sdcp-11012-shg-dpi-parity-3.7.1): DPI grace — per-EMI overdue admit into base/anchor + overdue-day segment boundaries (EMI1 continues during EMI2 grace; EMI2 anchors after its overdue). E2E: dpic.grace + grace_overlap + multi_emi on LAN 8057160 PASS.
- 2026-07-08 acct 775b9e8a7 (mfi_integration_v3.7.1 via feature/sdcp-11012-shg-dpi-parity-3.7.1): SDCP-11012 cherry-pick of daf6a331c — SHG DPI parent=sum(children) last-child adjust after dpiAccrualCalculation. QA1 audit+bulk accrual/LDD repair scripts under scripts/sql/setup/qa1_*sdcp_11012*.
- 2026-07-08 acct daf6a331c (DPI feature): SDCP-11012 SHG parent DPI ≠ sum(children) — DpiGroupLoanAccrualAdjustService + post-calc tasklet mirrors interest last-child adjust; QA1 L0 SQL scripts/sql/setup/qa1_repair_sdcp_11012_shg_dpi_accrual.sql. batch.dpi_calc + batch.dpi_booking PASS.
- 2026-07-08: Webapp local — sidebar loan-account menu uncommented; notifications real svc :8015; gateway/authorization post-login APIs verified; singleStepLogin kept.
- 2026-07-08 acct e919e3b33 (3.4.2.1): SDCP-10199 L1 core — parent schedule reduction = futurePrincipal − futureUnpaidBilled (not all billed); new getUnpaidFutureBilledPrincipalForDeathForeClosure; reverted generic processor clamp. dcf.group_parent_last_child_e2e PASS.
- 2026-07-08 acct 63f2314c1 (3.4.2.1): SDCP-10199 guard negative parent RSCH netAmount on first-child group DFC — clamp part-prepayment principal to zero; skip PRIN appropriation when pending<=0; e2e negative-PRIN assertion. Tested dcf.group_parent_last_child_e2e PASS LAN 6000137433.
- 2026-07-08: Webapp local single-step login (singleStepLogin); fix login.service error swallow; SQL local_setup_webapp_login_contact_verified.sql for 220402 bypass.
- 2026-07-08 acct 82cb142e7 (3.4.2.1): SDCP-10295 Loan360 Summary interest Original=billed, Outstanding=Original-(paid+waived+writtenoff). Tested LAN 6000000583/6000000798 API=DB.
[2026-07-07] | FIX | SDCP-10199 shipped: parent PRIN paid (not waived) on last-child RSCH; EC putLocal(parent) shadowing fix; upsert additional_amount_details; removed PINT paid hack; group e2e + fixture backup 6000137433 | accounting 74d566432 DeathForeclosureInsuranceWriter.java, scripts/dcf_sanity/*, registry dcf.group_parent_last_child_e2e
[2026-07-07] | FIX | SDCP-10199 e2e green: putLocal(parent) fixes EC local shadowing on parent appropriation; PINT orphan sweep on child DCF; notifications stub :8015 + restore purges DFC_PRTL_BILL CRNs | DeathForeclosureInsuranceWriter.java, scripts/dcf_sanity/local_notifications_stub.*, dcf_fixture_backup.py, ensure_dcf_local_stack.sh
[2026-07-07] | FIX | SDCP-10199 parent last-child DFC: INT-only waive on parent (mirror child), full parent PRIN OS appropriation + RSCH amounts, skip parent ACTIVE reset, direct CLOSED+la_closing_date; local verify scripts | novopay-platform-accounting-v2/.../DeathForeclosureInsuranceWriter.java, scripts/dcf_sanity/parent_last_child_dfc_*
[2026-07-02] | WORKSPACE | Batch write-skip contract gate: audit-batch-skip-mappers.sh + ship-loop hook + batch-write-skip-contract.mdc; DPI Vo mappers stripped of redundant unwrap | scripts/bin/audit-batch-skip-mappers.sh, ship-loop-gate.sh, .cursor/rules/batch-write-skip-contract.mdc, DPI failure mappers
[2026-07-02] | BUG_FIX | Generic force_async skip path: BatchWriterSkipItemSupport in platform-lib; GenericListenerV3 delegates; DPI mapper peels List only; ntest dpic.batch.force_async_modes | novopay-platform-lib/infra-batch, GenericListenerV3.java, DpiBatchWriterSkipItemSupport.java, scripts/dpic/run_dpi_force_async_modes.sh
[2026-07-02] | FIX | DPI matrix E2E: purge clears DPI dues + batch_failure_audit; async DB settle poll in db_assertions + post_eod_verify; cross_eod fresh baseline fixture | purge_dpi_accruals_for_loan.sql, prepare_dpi_fixture_for_batch.sh, db_assertions.py, run_dpi_cross_eod_replay_guard.sh, run_dpi_post_eod_verify.sh
[2026-07-02] | BUG_FIX | Push gate: GATE_PASSED outbox short-circuit, bounded workspace-close timeout, SHIP_PUSH_LOCK_PATH; kg-hot-swap duplicate kg-switch eliminated (flock pile-up); ntest validate_registry import | push-origin.sh, pre-push-checklist.sh, ship_push_gate.py, ship_push_lock.py, kg-hot-swap.sh, kg-session-sync.sh, ntest.py
[2026-07-02] | BUG_FIX | GenericListenerV3 async write-skip: unwrap Future before fromWriter (fixes dpiAccrualBooking ClassCastException with force_async) | novopay-platform-lib/infra-batch/.../GenericListenerV3.java, accounting DpiAccrualCalculationFailureEntityMapper
[2026-07-02] | FEATURE | DPI batch QA matrix — parameterized fixtures (DPI_SCENARIO), 6 matrix flows + 12 scenario batch cases with db_assertions; grace/multi-EMI JOB_TIME alignment; verify_grace_dpi_batch.sql | scripts/dpic/prepare_dpi_fixture_for_batch.sh, registry.json, scripts/dpic/sql/helpers/
[2026-07-02] | FEATURE | ntest db_assertions lifecycle for DPI batch jobs — pre/post ledger snapshot + verify_dpi_* SQL hooks; fixture fixes (sync_demo_past_due, dpi_evict_go_live_cache, seed_calc_window) | scripts/testing/lib/db_assertions.py, ntest.py, registry.json, scripts/dpic/

- 2026-07-08 | accounting-v2 `bb699aa69` | DPI booking posts closed slices on next posting day (due/month-end), preventing dangling unposted rows for grace-overlap end_date (e.g. 2026-06-18).
- 2026-07-08 | accounting-v2 `3a0eae411` | DPI booking anchor condition widened: post when business day **or** slice end_date is due/month-end (handles month-end booking job_time after midnight).
[2026-07-02] | REFACTOR | Demote branch-train to soft log; kgd silent fallback + KG_DAEMON_DISABLED | workspace-health.sh, ship-loop-gate.sh, kg_client.py, kg.py, branch_topology.py

[2026-07-02] | FEATURE | Sprint 4 L3: kgd query daemon, ship state outbox (branch mix = soft log only) | kgd.py, kg_client.py, kg.py, ship_outbox.py, branch_topology.py, workspace-health.sh, ship-loop-gate.sh

[2026-07-02] | FEATURE | Sprint 3 baseline modernization: hub lessons block, ntest smoke --tier workspace, requires_batch + run-guarded docs, verify 21 checks | intelligence_hub.py, ntest.py, workspace_lessons.py, workspace_autopilot.py, registry.json, ship-loop-gate.sh, enrichment-audit.sh, skills

[2026-07-02] | REFACTOR | Sprint 2: parallel Phase 2b feeders, java_index_gc LRU purge, kg orient mixed-train warning, coordinator live_composite_key fix, drift-unified entrypoints, removed after-money-path-edit.sh | build.sh, java_index_gc.py, kg.py, session_coordinator.py
[2026-07-02] | REFACTOR | Sprint 1: incremental Java index (feeder_hooks freshness), kg_build_lock shared flock, run-guarded on kg-switch/ship-loop/sync-intelligence/platform_scan, fork-base watermark cache | build_java_index.py, build.sh, kg_build_lock.sh, kg-hot-swap.sh
[2026-07-02] | FEATURE | Native multi-branch intelligence: kg_composite all-repo HEAD fingerprint, kg-hot-swap + post-checkout hook, session_coordinator branch_drift, intelligence_hub Branch Topology section, branch_topology.py | workspace-intelligence-state.md
[2026-07-02] | REFACTOR | Phase 1–3 workspace upgrade: build_java_index parallel feeders (52s full build), WAL PRAGMAs, run-guarded.sh, lessons roundtrip verify, ship_push_lock on post-ntest background push | cursor-bundle/kg/bin/build.sh, build_java_index.py, build_db.py
[2026-07-02] | REFACTOR | Extreme workspace upgrade: session_coordinator (dedupe KG sync), after-ship-path-edit hook, pending-ship flock, sync-intelligence single kg-switch, intel/close path dedupe | hooks.json
[2026-07-02] | REFACTOR | Workspace infra upgrade: KG path fixes (211 doc nodes), parallel build feeders, cache validate, KG_STRICT/drift cache, workspace_lessons self-learning, agent-ops preflight fix | none (scripts + cursor-bundle/kg)

[2026-07-02] | WORKSPACE | Minimal-fix skill + SDCP-10590 precedent: one root-cause layer, no stacked dedupe; interest accrual ships reader LPAC + batch save(List) only | .cursor/skills/minimal-fix/SKILL.md, feedback_minimal_fix_impact_gate.md, minimal-fix-impact-gate.mdc, jira-fix-update/SKILL.md, skills-manifest.json

[2026-06-29] | WORKSPACE | Ship-loop fix: `expand_path_cases` required path match for PATH_TRIGGERED cases (was pulling foreclosure + DPI e2e on read-only overview edits); cross_eod default JOB_TIME=1782563400000 | resolve_ship_cases.py, test_resolve_ship_cases.py, run_dpi_cross_eod_replay_guard.sh

[2026-06-25] | FEATURE | Collections DPI split: exclude DPI from EMI due / total overdue / emi_overdue in `getLoanAccountOverviewDetails` + `loanRecurringPaymentBatchApi`; separate `dpi_due` / `dpi_overdue` / `dpi_due_amount` unchanged | GetLoanAccountOverviewDetailsProcessor.java, LoanRecurringPaymentBatchProcessor.java

[2026-06-26] | BUG_FIX | SDCP-10497 DPI accrual posting — gate on businessDate; pushed 6ec669b0e3 feature/delayed_payment_interest | DpiAccrualBookingBatchService.java

[2026-06-26] | WORKSPACE | DPI ship-gap hardening (SDCP-10497): `dpic.posting_calendar_regression` + `cross_eod_replay_134497` mandatory in `resolve_dpi_cases` / money impact; `ship_auto` on guard cases; `dpi-booking-posting-guard.sh` in ship-loop; release phase always includes posting guards; `test_resolve_ship_cases.py`; gaps + edge case doc | resolve_ship_cases.py, ship_test_plan.py, ship-loop-gate.sh, resolve_ship_impact.py, registry.json, gaps-and-risks.md, system_brain/edge_cases/dpi_posting_calendar_ship_gap_sdcp10497.md

[2026-06-26] | WORKSPACE | DPI money-proof upgrade: `verify_dpi_billing_ud.sql` wired via `run_dpi_billing_ud_verify.sh` + `dpic.billing_ud_next_emi`; `dpi-money-proof.sh`; EOD auto post-verify; `dpi-money-proof-gate.mdc`; backlog WS-016..020 | scripts/dpic/*, scripts/bin/dpi-money-proof.sh, agent-ops.sh, MEMORY.md, workspace-backlog.json

[2026-06-26] | WORKSPACE | Accounting ALL-flow coverage (not money-only): `accounting_flow_domains.json` (18 domains / ~358 apis); ship-loop service+money domain guards; `accounting-flow-coverage.sh`, `accounting-flow-proof.sh`, core EOD batch registry, read smoke; rule `accounting-full-flow-gate.mdc` | scripts/lib/accounting_flow_domains.*, resolve_ship_cases.py, ship_test_plan.py, registry.json

[2026-06-26] | BUG_FIX | SDCP-10199 last-child SHG DCF: waive future parent dues, settle installments, close parent account; overdue waiver pending BA | DeathForeclosureInsuranceWriter.java, brain CHANGELOG kg-flow

[2026-06-25] | REFACTOR | DPI batch L1 perf — precomputeDaySnapshots (calc), dueDayKeys set (booking); batch-hot-path gate updated | DpiAccrualCalculationBatchService, DpiAccrualBookingBatchService, batch-hot-path-perf.mdc

[2026-06-25] | FEATURE | Super machine full test automation — ship_test_plan (impact/deep/release), post-commit ship-test-auto, money close auto release phase, agent-ops verify-dpi wired | ship_test_plan.py, ship-loop-gate.sh, workspace-close.sh, hooks, feedback_super_machine_automation.md

[2026-06-25] | REFACTOR | Workspace-wide impact-scoped ship tests — resolve_ship_cases.py; no smoke-tier sweep | resolve_ship_cases.py, infer_ship_apis.py

[2026-06-25] | REFACTOR | DPI ship-loop: impact-scoped ntest (path→batch.dpi_* + dpic.go_live/grace/multi); removed blanket dpic.ud_compliance; full profile only dpi-sanity/verify-dpi | infer_ship_apis.py, kg_ship_resolve.py, run_dpi_ud_compliance.sh, feedback_impact_scoped_ship_tests.md

[2026-06-25] | GAP_RESOLVED | DPI UD compliance gate: go-live base, maturity skip, posting calendar fixes + `dpic.ud_compliance` wired in registry, dpi-sanity, ship-loop, gap matrix | gaps-and-risks, dpi-feature-branch-gate, reference_dpi_ud_test_matrix, system_brain/edge_cases/dpi_go_live_ud_qa1

[2026-06-24] | BUG_FIX | DCF L0-L2: death-cycle PINT+FEE credit, INT waived alignment, billing sync anchored to death date; scenarios S11-S15 + reconcile SQL; acct 60c8d0f74 | death_foreclosure.md, dcf_sanity, brain CHANGELOG kg-flow

[2026-06-24] | BUG_FIX | DCF death-on-due-date settled EMI: credit death-cycle PINT paid to outstanding (LAN 6007564726 → 5158/4842); acct dfcd270a3 | accounting-flows, brain CHANGELOG kg-flow

[2026-06-24] | FEATURE | Plain-English-only user contract — AGENTS.md, autopilot skill/mdc, effective-prompts; agents run super-machine handle, user never runs commands | AGENTS.md, workspace-autopilot.mdc, skills

[2026-06-24] | FEATURE | super-machine-smoke.sh — 31-check verification suite | scripts/bin/super-machine-smoke.sh

[2026-06-24] | FEATURE | Super machine complete: corroborate.py, orch_api_index cache, super-machine.sh loop/handle/weekly, autopilot trace-first, hub corroboration, session 6h cadence | scripts/testing/, hooks, skills-manifest, WORKSPACE.md

[2026-06-24] | FEATURE | Super-machine tooling: flow_trace.py, flow_scaffold.py, flow-onboard.sh, super-agent trace/onboard, ftg registry-gaps (orch vs ntest) | scripts/testing/, scripts/bin/, super-agent SKILL, CANONICAL-MAP, WORKSPACE.md

[2026-06-24] | FEATURE | DPI workspace hardening: shared verify_gl_legs.sql, dpi_gl_verify.sh, regression preflight, phased restore+health on failure, extended_regression timing | scripts/dpic/, WORKSPACE.md, registry.json

[2026-06-24] | FEATURE | DPI write-path harness: loanAccountPartPrepayment TRIAL + ICF REAL GL legs; cat-10 seed for product 6367 | scripts/dpic/, registry.json, DPI_TEST_COVERAGE.md

[2026-06-24] | FEATURE | DPI suite extended: part-prepayment BPI/details, childLoanRepayment, NPA REGULAR_TO_NPA movement; presentation+writeoff excluded | scripts/dpic/, registry.json, accounting-v2 childLoanRepayment templates+orch

[2026-06-24] | FEATURE | DPI extended test suite — consumer flows (repayment, FC details, reversal), fixture lib, registry correlators fixed to 6004044425 | scripts/dpic/, scripts/testing/registry.json

[2026-06-23] | REFACTOR | DPI batch scale: unbilled partial-index billing reader, chunk bulk installment preload (no per-row next-EMI SQL), booking due-date set per loan; acct 76e1f70fb | dpibilling, dpiaccrualbooking, LoanInstallmentDetailsDAOService

[2026-06-23] | REFACTOR | DPI billing reader slim SQL (DISTINCT anchor rows); next-EMI gate + NPA as-of inlined in Java; removed DpiBatchNpaSupport; acct 44c8e15cd | dpibilling, dpibilling cache, dpiaccrualbooking

[2026-06-23] | BUG_FIX | DPI billing UD §5.4: next-EMI due_date/value_date, gate billing on next installment, NPA leg as-of date (DpiBatchNpaSupport); acct 8053210a5 | accounting-v2 dpibilling, brain CHANGELOG kg-flow

[2026-06-23] | FEATURE | Universal ship-test gate: post-commit pending registration, batch COMPLETED wait, registry prefers batch.* over certify flows, service-tier health/smoke minimum | register_pending_ship.py, infer_ship_apis.py, ntest.py, registry.json, post-commit-kg-flag.sh, pre-push-checklist.sh, ship-loop-gate.sh, ship-test-mandatory.mdc

[2026-06-23] | BUG_FIX | Cross-flow self-learn: test-learn import fix, post-ntest FAIL hook, disburse script-bank schedule gate, DPI 6367 GST bypass + certify dates + DSBR account | disburse_loan_sanity.py, learn_cli.py, certify_dpi_scenarios.sh, run_disburse_demo.sh, flow-cross-learn.mdc, learnings.jsonl

[2026-06-23] | FEATURE | WS backlog closed: cross-EOD 134497 registry test, death FC DPI waiver smoke, incremental KG case DB upsert | registry.json, run_dpi_cross_eod_replay_guard.sh, run_dfc_dpi_waiver_smoke.sh, build_db.py

[2026-06-23] | FEATURE | DPI certification harness: fresh LAN per scenario, certified_fixtures.json, registry dpic.certify_scenarios | certify_dpi_scenarios.sh, disburse_fresh_dpi_loan.sh, job_times_from_loan.py

[2026-06-23] | REFACTOR | Autopilot hardening: verify subcommand, ship lock, continuation skip, light preflight, queue stale expiry, smoke integration | workspace_autopilot.py, ship_push_queue.py, ship_push_lock.py, workspace-smoke.sh

[2026-06-23] | FEATURE | Autopilot task-shift (mid-tab re-preflight) + ship-and-continue (post-test push, cooldown, push-origin --repo) | workspace_autopilot.py, ship_push_queue.py, post-ntest-intel-sync.sh, push-origin.sh

[2026-06-23] | FEATURE | Workspace autopilot: task classify+execute preflight, session/stop hooks, auto-close on stop, mandatory agent rule (user runs nothing) | workspace-autopilot.py, workspace-autopilot.mdc, hooks.json, stop-ship-nudge.sh, always-on.mdc

[2026-06-23] | FEATURE | Workspace self-improve loop: backlog JSON, health/max-pass scripts, fast session KG (--fast when fresh), orch mtime cache, smoke skips close when satisfied, kg-flow→fix_shipped bus | workspace-backlog.json, workspace-health.sh, workspace-max-pass.sh, kg-session-watermark.sh, sync_engine.py, workspace-self-improve/SKILL.md

[2026-06-23] | REFACTOR | Workspace-wide hardening: workspace-smoke.sh, resolve_ship_impact (single Python), fingerprint gates in enrichment-audit/pre-push/checkout, learnings loop (lesson→text, flow→bus), tier knowledge profiles | workspace-smoke.sh, ship-loop-gate.sh, enrichment-audit.sh, hooks, learnings.jsonl, sync_engine.py, ntest.py

[2026-06-23] | REFACTOR | Workspace-close perf: fingerprint skip, tier knowledge-gate profiles, dedupe KG/gate, --force | workspace-close.sh, ship-loop-gate.sh, ship-knowledge-gate.sh, ship_push_gate.py, after-ship-path-edit.sh, stop-ship-nudge.sh

[2026-06-23] | FEATURE | DPI EOD batch accounting rules seed SQL (4 catalogue+TAR rows for dpiAccrualBooking/dpiBilling) | scripts/sql/seed/local_dpi_eod_batch_accounting_rules.sql

[2026-06-23] | BUG_FIX | Disburse-quick PASS (~11s): JLG MFT payload, DSBR_ACCT account_number injection, MFT script mock + intermediate wait | disburse_loan_sanity.py, disburse-quick.sh, edge_cases/disburse_quick_script_mode_acctwb.md

[2026-06-23] | BUG_FIX | Disburse-quick: ACCTWB MFT script mock + intermediate wait; fixes LOAN_BOOKED stall on OTHBACCT/NEFT script path | disburse_loan_sanity.py, disburse-quick.sh, system_brain/edge_cases/disburse_quick_script_mode_acctwb.md, learnings.jsonl

[2026-06-23] | BUG_FIX | Disburse suite: `disburse-quick.sh`, preflight in sanity runner, fixed root matrix wrapper paths, ntest `disbursement.quick`; gaps GAP DPI client ref RESOLVED | scripts/bin/disburse-quick.sh, disburse_loan_sanity.py, gaps-and-risks.md, registry.json, learnings.jsonl

[2026-06-23] | BUG_FIX | DPI batch client_ref aligned with interest jobs (numeric loanAccountId + millis; billing adds installmentId) — fixes QA dpiBilling 134497 on cross-EOD replay | accounting-v2 `346d9efe6` dpiBilling dpiAccrualBooking

[2026-06-23] | BUG_FIX | Death FC: `calculateLossDpiWaived` + `waiveFutureDpiPastReporting` (was `LOSSES_DPI_WAIVED=0`); childLoanRepayment NPA leg aligned with parent (`PAID_BILLED_DPI_INT_AMT`, `npa_suspense_total_amount`) | accounting-v2 `bfd172d86` on `feature/delayed_payment_interest`

[2026-04-06] | INITIAL_SCAN | Full deep scan — 12 services, 146 events (44 consumers / 7 services), 166 accounting entities, 11 gaps (6 High, 5 Medium, 0 Low), 20/20 knowledge verified | architecture.md, platform-lib.md, accounting-flows.md, event-registry.md, service-contracts.md, gaps-and-risks.md, conventions.md, onboarding.md, changelog.md, .cursorrules

[2026-04-07] | FEATURE | Principal-architect pack: session bootstrap rule, proactive intelligence rules, architecture.mmd + accounting-flow.mmd, test-coverage-map, dependency-map, runbooks; gaps expanded (+Gradle drift +3 test-absence High) | session-bootstrap.mdc, architecture.mmd, accounting-flow.mmd, test-coverage-map.md, dependency-map.md, runbooks.md, gaps-and-risks.md, changelog.md, .cursorrules

[2026-04-07] | BUG_FIX | Portfolio `doGLTransfer`: stamp `transaction_master` / `transaction_details` `business_date` and `value_date` from platform business date (`getBusinessDateInLong()`), not system time; align `portfolio_transfer_details` completion/audit timestamps with same business date | changelog.md, accounting-module-knowledge.mdc

[2026-04-07] | BUG_FIX | Death-foreclosure billing sync: align cutoff to reporting date and allow billing job to process `DEATH_FORECLOSURE_FREEZE` accounts when invoked from death-foreclosure flows (via explicit sync mode), so `NORMAL_BILLING` rows can be generated before closure | changelog.md, accounting-module-knowledge.mdc

[2026-04-07] | BRANCH_ANALYSIS | multinode_v3.2.8.2 analyzed — multi-node batch framework mapped | multinode-batch.md created, architecture.md updated, gaps-and-risks.md updated, event-registry.md updated, runbooks.md updated | architecture.md, event-registry.md, gaps-and-risks.md, runbooks.md, multinode-batch.md, changelog.md

[2026-04-07] | FEATURE | Batch manager/worker flag semantics captured: documented DB-driven `batch_job_parameter` force_* flags (`force_async`, `force_task_executor`, `force_msg_driven`, etc.) and clarified scheduler multi-instance vs Spring Batch remote-partitioning multi-node | multinode-batch.md, architecture.md, changelog.md

[2026-04-07] | REFACTOR | Centralize bank external reference leg prefixes (01/02/03/04/06) into `BankExternalRefPrefixes` and use across disbursement + GL-CBS processors to avoid drift | changelog.md

[2026-04-07] | BUG_FIX | Child-loan NEFT v2 CLMT persistence: set `loan_account_events_queue.event_status='C'` only when the embedded `disbursement_status` is `COMPLETED` (previously compared disbursement status to `"C"` and could leave CLMT rows pending even after completion) | changelog.md, accounting-module-knowledge.mdc

[2026-04-09] | REFACTOR | Agent rules: replace `debugging-production-issues.mdc` with evidence-based RCA + adversarial check + manual verification plan + human gate; remove `accounting-134207-placeholder-iad.mdc` (runbook remains in `system_brain/edge_cases/`); sync `system_brain/rules/rule_inventory.md` | debugging-production-issues.mdc, accounting-134207-placeholder-iad.mdc (deleted), rule_inventory.md, accounting_134207_placeholder_iad.md, changelog.md

[2026-04-09] | FEATURE | Knowledge base: document death-foreclosure insurance reverse-feed `Pending for FR` partial-progress + batch-blocking gap (cross-service txn + chunk failure) and add system_brain edge-case note for quick RCA next time | accounting-module-knowledge.mdc, gaps-and-risks.md, death_foreclosure_insurance_pending_fr_partial_progress_blocks_batch.md, changelog.md

[2026-04-09] | FEATURE | System brain: add runbook for time-based `client_reference_number` replay/double-post risk across batch posting flows; add gaps for additional batch flows + auto-closure writer log-and-continue behavior | gaps-and-risks.md, batch_time_based_client_reference_number_replay_risk.md, changelog.md

[2026-04-10] | FEATURE | Gap mining bootstrap: add `mining-progress.md` wave tracker (waves 1–6, session gap counter, files-written log) | mining-progress.md, changelog.md

[2026-04-10] | FEATURE | Wave 1 gap mining: platform-lib + accounting-v2 lens scan — GAP-031..037 (4H/2M/1L), runbooks, `platform-lib-edge-cases.md`, `accounting-edge-cases.md`, mining-progress | gaps-and-risks.md, runbooks.md, platform-lib-edge-cases.md, accounting-edge-cases.md, mining-progress.md, changelog.md

[2026-04-10] | FEATURE | Wave 2 gap mining: novopay-mfi-los + novopay-platform-payments — GAP-038..045 (5H/3M/0L), runbooks for new High gaps, `los-edge-cases.md`, `payments-edge-cases.md`, mining-progress totals | gaps-and-risks.md, runbooks.md, los-edge-cases.md, payments-edge-cases.md, mining-progress.md, changelog.md

[2026-04-10] | FEATURE | Wave 3 gap mining: novopay-platform-task + actor + batch — GAP-046..053 (5H/3M/0L), runbooks for new High gaps, `scheduler-registry.md`, task/actor/batch edge-case notes, mining-progress | gaps-and-risks.md, runbooks.md, scheduler-registry.md, task-edge-cases.md, actor-edge-cases.md, batch-edge-cases.md, mining-progress.md, changelog.md

[2026-04-10] | FEATURE | Wave 4 gap mining: masterdata + authorization + approval + audit + notifications + api-gateway + dms — GAP-054..058 (2H/3M/0L), runbooks for new High gaps, `redis-key-registry.md`, seven edge-case files, scheduler-registry gateway row, mining-progress | gaps-and-risks.md, runbooks.md, redis-key-registry.md, scheduler-registry.md, masterdata-edge-cases.md, authorization-edge-cases.md, approval-edge-cases.md, audit-edge-cases.md, notifications-edge-cases.md, api-gateway-edge-cases.md, dms-edge-cases.md, mining-progress.md, changelog.md

[2026-04-10] | FEATURE | Mining closure (waves 5–6): orchestration-map (60 XML / ~1892 requests), service-dependency-graph, config-drift-map, test-coverage-map Waves 1–4 matrix; **GAP-059..060** High (no `src/test` for `AuthorizationCheckFilter` / `RequestForward*`); mining-progress ALL WAVES COMPLETE; `.cursorrules` agent summary counts | orchestration-map.md, service-dependency-graph.md, config-drift-map.md, test-coverage-map.md, gaps-and-risks.md, mining-progress.md, .cursorrules, changelog.md

[2026-04-10] | REFACTOR | Rebuilt knowledge artifacts: `service-dependency-graph.md` (HTTP matrix, Kafka edges, SPOF blast radius, circular deps, longest sync chain, Mermaid); `test-coverage-map.md` (money paths, 48 Kafka consumers test scan, 101+103 batch beans, orchestration XML IT=NO, per-service %); `config-drift-map.md` (timeout matrix, MessageBroker consumer poll/threads/maxPoll, Redis TTL props, pool hints, URL drift) | service-dependency-graph.md, test-coverage-map.md, config-drift-map.md, changelog.md

[2026-04-10] | FEATURE | Add `MASTER-BRAIN-SYNC.md` — phased loader (core brain, risk, edge cases, rules, weekly sync, task gate checklist) for session bootstrap | MASTER-BRAIN-SYNC.md, changelog.md

[2026-04-10] | FEATURE | Cursor intelligence layer: scoped `.mdc` rules (accounting, platform-lib, batch, events, los, payments, gateway, always-on) + `.cursorrules` INTELLIGENT CONTEXT ROUTING + auto-log checklist; `rule_inventory.md` updated | rules/*.mdc, .cursorrules, system_brain/rules/rule_inventory.md, changelog.md

[2026-04-10] | BUG_FIX | `LmsMessageBrokerConsumer`: allow `disburseLoan` Kafka processing when loan is ACTIVE+COMPLETED only if `REINITIATE_BANK` + `request.payment_reinitiation_update=true`; add JTF field on mfi/product `disburseLoan_requestTemplate.json` (LOS supplies flag, no LOS code in this workspace) | changelog.md, accounting-module-knowledge.mdc

[2026-04-11] | FEATURE | Ops SQL: `scripts/task_undelete_unassign_mfi_task.sql` — set `current_status='UN_ASSIGNED'`, `is_deleted=false` for tasks `322923907` / `333456310` / `347622802` (death-foreclosure insurance recovery; edit id list as needed) | changelog.md

[2026-04-11] | FEATURE | Add **PROMPT SELF-EXPANSION RULE** to `00-workspace-core.mdc` — classify request (bug/feature/investigation/review/refactor/question), expand task (services, flows, gaps, files, risk, blast radius), confirm with user before code/config changes; exceptions: simple questions, read-only traces, brain/weekly sync | always-on.mdc, changelog.md

[2026-04-11] | REFACTOR | Consolidate `.cursor/rules/*.mdc` from 44 → **20** files; merge accounting/sync/preflight/signoff/module-knowledge into `accounting.mdc`; session/brain/debugging/maintenance into `00-workspace-core.mdc`; architect/framework/tiered/bank/DB/finance/repo-style into `architect-thinking.mdc`; local DB + disburse resets into `local-dev-workflows.mdc`; git + fork + sync phrase into `git-workflow.mdc`; Kafka consumer patterns into `events.mdc`; docs maintenance into `docs-outside-service-repos.mdc`; disbursement multi-path into `multi-path-state-persistence-safety.mdc`; **only** `00-workspace-core.mdc` + `10-quality-gates.mdc` remain `alwaysApply: true`; update `rule_inventory.md`, cross-links in `AGENTS.md`, `.cursorrules`, `architecture.md`, `accounting-flows.md`, `conventions.md`, `index.mdc`, `system_brain/**` refs | accounting.mdc, always-on.mdc, architect-thinking.mdc, local-dev-workflows.mdc, git-workflow.mdc, events.mdc, docs-outside-service-repos.mdc, multi-path-state-persistence-safety.mdc, platform-lib.mdc, batch.mdc, los.mdc, payments.mdc, gateway.mdc, execution-context-discipline.mdc, no-flow-break-impact-check.mdc, api-contract-safety.mdc, multi-agent-spawning.mdc, disburse-loan-sanity-suite.mdc, effective-prompts-and-issue-triage.mdc, discuss-before-updating.mdc, rule_inventory.md, AGENTS.md, .cursorrules, architecture.md, accounting-flows.md, conventions.md, index.mdc, posting_engine.md, rule_improvements_applied.md, changelog.md

[2026-04-10] | BUG_FIX | `executeLMSPortfolioTransfer`: expand loan `account_id` scope to include ACTIVE child loans (`parent_loan_account_id` in seed set) for GL detail build, `doGLTransfer` office updates, and `servicing_emp_id` updates | changelog.md, accounting-module-knowledge.mdc

[2026-04-11] | REFACTOR | **`00-workspace-core.mdc`**: stricter **session bootstrap** (mandatory before logs/repo reads for substantive work); **prompt self-expansion** + confirm before investigation tools **or** edits for high-blast-radius read-only (prod logs, money, multi-service, contracts, DB/cluster); narrow exceptions; dedupe duplicate bootstrap block; **`multi-agent-spawning.mdc`**: point accounting rail to merged **`accounting.mdc`**; **`rule_inventory.md`** row sync | always-on.mdc, multi-agent-spawning.mdc, rule_inventory.md, changelog.md
[2026-04-13] | BUG_FIX | Payment reinitiation lane in parent disbursement bank processor now uses dedicated `*_REINIT` CRR transaction types for MFT/NEFT v1/NEFT v2 while preserving loan `disbursement_status` on reinit, `REINITIATE_BANK` disables child bank flow in `mfi_orc.xml`, and child NEFT callback failure handling no longer regresses CLMT status to `DTFC_SUCCESS` on duplicate ST_NEF (`*0004`) failures | changelog.md, accounting.mdc
[2026-04-13] | BUG_FIX | Child NEFT callback L1 hardening: ST_NEI duplicate-like failures now use queue+CRR evidence gating in `DoGenericSyncSTPBankNeftCallBackProcessor` (keep `NEFT_STAGE_2_PENDING` when success not proven; mark `COMPLETED` + parent sync only when stage-2 success evidence exists) | changelog.md, accounting.mdc

[2026-04-13] | BUG_FIX | Portfolio transfer account expansion: fix `findAccountIdsForPortfolioTransferIncludingActiveChildLoans` — do not apply global `is_deleted` on seeds (parent could be excluded while children matched); add explicit parent ids for child seeds via `parent_loan_account_id` subquery | changelog.md, accounting-module-knowledge.mdc

[2026-04-13] | REFACTOR | Portfolio transfer: replace bulk SQL expansion with explicit per-seed `getChildLoanAccountListForParentAccountId` in `LoanAccountDAOService` (request account_ids always kept; children added only when returned for that parent) | changelog.md, accounting-module-knowledge.mdc

[2026-04-13] | REFACTOR | Git workflow: document rebasing fork **integration** branches onto **upstream** (same branch name) with `--force-with-lease`, separate `fetch` invocations, and realigning child feature branches so fork-only commits stay on the latest production line | git-workflow.mdc, changelog.md

[2026-04-13] | FEATURE | Payment reinitiation development plan (business flow, Accounting vs LOS work split, gap register, QA/regression scope) + short stakeholder email draft under `docs/features/payment-reinitiation/`; renamed detailed doc to `payment-reinitiation-development-plan.md` (readable wording, no internal phase codes) | changelog.md, docs/features/payment-reinitiation/payment-reinitiation-development-plan.md, docs/features/payment-reinitiation/email-stakeholder-short.md

[2026-04-13] | REFACTOR | Payment reinitiation docs: drop “runbook” wording; plain ops/support phrasing; remove `.cursor/runbooks.md` pointer from plan references | changelog.md, docs/features/payment-reinitiation/email-stakeholder-short.md, docs/features/payment-reinitiation/payment-reinitiation-development-plan.md

[2026-04-13] | REFACTOR | Payment reinitiation detailed plan tightened (v1.2): fewer sections, merged tables, same decisions and paths | changelog.md, docs/features/payment-reinitiation/payment-reinitiation-development-plan.md

[2026-04-13] | REFACTOR | Payment reinitiation plan v1.3: Problem section as prose (no table), clearer narrative | changelog.md, docs/features/payment-reinitiation/payment-reinitiation-development-plan.md

[2026-04-13] | REFACTOR | Payment reinitiation plan v2.0: full rewrite — fixed broken markdown, no tables, clear Why/Done/Accounting/LOS/Gaps/QA/Rollback/File index | changelog.md, docs/features/payment-reinitiation/payment-reinitiation-development-plan.md

[2026-04-13] | FEATURE | Payment reinitiation plan v2.1: DB/QA section for `client_request_response_log` — columns, `transaction_type` patterns (MFT / NEFT NEF·NEI), illustrative reinit rows, sample SQL, pass/fail; schema note from accounting dump | changelog.md, docs/features/payment-reinitiation/payment-reinitiation-development-plan.md

[2026-04-13] | REFACTOR | Payment reinitiation email draft: fix markdown, one-line CRR/table pointer, link to detailed plan DB section | changelog.md, docs/features/payment-reinitiation/email-stakeholder-short.md

[2026-04-13] | REFACTOR | Payment reinitiation plan: Markdown preview fixes -- no backticks inside headings, `### How transaction_type...` renamed, file fence `text`, straight quotes, email nested bold/backtick cleanup | changelog.md, docs/features/payment-reinitiation/payment-reinitiation-development-plan.md, docs/features/payment-reinitiation/email-stakeholder-short.md

[2026-04-13] | REFACTOR | Payment reinitiation detailed doc replaced with **CRR-only** note: local Yugabyte `\\d` + empty sample query, column meanings, before/after `transaction_type`, illustrative sample rows, local SQL | changelog.md, docs/features/payment-reinitiation/payment-reinitiation-development-plan.md

[2026-04-13] | BUG_FIX | Payment reinitiation CRR doc: correct persisted `transaction_type` base to **DISBURSEMENT**_* (from `mfi_orc.xml` bank processor param), not LOAN_DISBURSEMENT_*; explain dual `transaction_type` in same request | changelog.md, docs/features/payment-reinitiation/payment-reinitiation-development-plan.md

[2026-04-13] | REFACTOR | Payment reinitiation CRR doc + email: **NEFT-only** scope (MFT synchronous / out of scope); **`03`** NEFT ref series via `BankExternalRefPrefixes` + `ExternalReferenceNoUtil`; sample rows + SQL | changelog.md, docs/features/payment-reinitiation/payment-reinitiation-development-plan.md, docs/features/payment-reinitiation/email-stakeholder-short.md

[2026-04-13] | FEATURE | **Payment reinit (NEFT) implemented in accounting-v2**: `LmsMessageBrokerConsumer` skips `ACTIVE`+`COMPLETED` only when not `REINITIATE_BANK`; `CallBankAPIForDisbursementProcessor` — inquiry list + `_REINIT` CRR types, multi-type `03` counter via `ExternalReferenceNoUtil`, NEI idempotency keyed to `DISBURSEMENT_NEFT_NEI_REINIT` when reinit, failure-log `transaction_type` aligned; `DoGenericSyncSTPBankNeftCallBackProcessor` resolves NEF parent by `DISBURSEMENT_NEFT_NEF` or `..._REINIT`; fix `ExternalReferenceNoUtil` 5-arg overload delegation to 9-arg | changelog.md, accounting-flows.md, `novopay-platform-accounting-v2` (consumer, processors, util)

[2026-04-13] | REFACTOR | `CallBankAPIForDisbursementProcessor`: readability-only — extract inquiry `transaction_type` list builder, main `try` failure handler, MFT inquiry transport-failure handler, split NEFT v2 inquiry into stage-1-pending vs not (no behaviour change; child processor left unchanged per existing comment) | changelog.md

[2026-04-13] | REFACTOR | Disbursement bank-call extraction: `DisbursementBankCallSupport` (Spring `@Component`) holds parent MFT / NEFT v1+v2 bank + inquiry implementation; `DisbursementBankCallTypeUtil` (pure) inquiry/reinit type lists; `DisbursementCustomerNameHelper` + `DisbursementBankCrrLogHelper` shared by parent + child processors; slim `CallBankAPIForDisbursementProcessor` (orchestration + `saveBankErrorResponseCode` + external-ref compute only); `CallBankAPIForDisbursementProcessorTest` mocks updated | changelog.md, accounting-flows.md, `novopay-platform-accounting-v2`

[2026-04-13] | REFACTOR | Parent disbursement bank calls: replace monolithic `DisbursementBankCallSupport` with `ParentDisbursementBankCallService` façade + `ParentDisbursementMftBankCall`, `ParentDisbursementNeftV1BankCall`, `ParentDisbursementNeftV2BankCall` (`loan.disbursement.bank.parent`); `CallBankAPIForDisbursementProcessor` injects façade only; delete `DisbursementBankCallSupport` | changelog.md, accounting-flows.md, `novopay-platform-accounting-v2`

[2026-04-13] | REFACTOR | Child individual disbursement bank calls: extract `ChildDisbursementBankCallService` + `ChildDisbursementMftBankCall` / `ChildDisbursementNeftV1BankCall` / `ChildDisbursementNeftV2BankCall`, `ChildDisbursementUtrPersistence`, `ChildDisbursementLoanEventsQueueSync` (`loan.disbursement.bank.child`); slim `CallBankAPIForIndividualChildLoanDisbursementProcessor` to orchestration; widen `REQUEST`/`RESPONSE`/`LOAN_DISB_NARRATION`/`TO_ACCOUNT_NUMBER`/`NARRATION` + `PostNEFTChildLoanBankDisbursementProcessor#updateChildClmtQueueAfterNeftV1` to `public` for cross-package use | changelog.md, accounting-flows.md, `novopay-platform-accounting-v2`

[2026-04-13] | REFACTOR | Disbursement bank-call literals: remove static-field re-exports from `CallBankAPIForDisbursementProcessor` / `CallBankAPIForIndividualChildLoanDisbursementProcessor`; use `import static …DisbursementBankCallConstants.*` (or explicit imports); migrate child/parent services, post-processors, `DoGenericSyncSTPBankNeftCallBackProcessor`, CLMT/grouploan helpers, `GetLoanAccountDetailsProcessor`, `LoanAccountEntity` to `DisbursementBankCallConstants`; qualify `DisbursementBankCallConstants.ACCOUNT_NUMBER` where `AccountingConstants.*` collides | changelog.md, `DisbursementBankCallConstants.java`, `novopay-platform-accounting-v2`

[2026-04-14] | BUG_FIX | Child NEFT v2 `performNEFTTransactionInquiry` aligned with parent: null inquiry response, `normalizeNeftResponseInContext` + type-tolerant `errorCode`, `NeftV2ResponseParser` for PROCESSED / enquiry replyCode gating, and **else** branch sets `DO_TRANSACTION=false` when `disbursement_status` is still `DTFC_SUCCESS` (NEF log already exists) so batch replay does not re-fire duplicate `ST_NEF` with the same deterministic ref | changelog.md, accounting.mdc, `CallBankAPIForIndividualChildLoanDisbursementProcessor.java` (`mfi_integration_v3.2.8.4.1`)

[2026-04-14] | BUG_FIX | Child NEFT v2 ST_NEI idempotency: `shouldSkipChildNeftStage2Initiation` now runs for both `NEFT_STAGE_1_SUCCESS` and `NEFT_STAGE_2_PENDING` (not only stage-2-pending), so a successful child-scoped `..._NEFT_NEI` CRR blocks duplicate `ST_NEI` when queue JSON still shows stage-1 success | changelog.md, accounting.mdc, `CallBankAPIForIndividualChildLoanDisbursementProcessor.java`
[2026-04-14] | BUG_FIX | CLB child-loan creation payload now propagates parent-shared `loan_details` fields `vtc_id`, `sourcing_emp_id`, and `servicing_emp_id` so child `createOrUpdateLoanAccount` persists `filler_11` and employee ids same as parent for shared attributes | changelog.md, accounting-flows.md, accounting.mdc, `ChildLoanBookingEventsQueueDataPopulator.java`
[2026-04-14] | BUG_FIX | CLB payload field sourcing corrected to member-first for child-specific data: `vtc_id`/`sourcing_emp_id`/`servicing_emp_id` now read from each `member_details` entry with fallback to parent context, preventing wrong parent-level stamping on child accounts when member values are provided | changelog.md, accounting-flows.md, accounting.mdc, `ChildLoanBookingEventsQueueDataPopulator.java`
[2026-04-14] | BUG_FIX | Child NEFT post-processor CRR logging hardened (L0): `PostNEFTChildLoanBankDisbursementProcessor` now persists CRR `response` from post-processor `apiResponse` only; when callback receives null response (webclient error path), stores explicit error envelope instead of stale `ExecutionContext.response`; request capture made null-safe | changelog.md, `PostNEFTChildLoanBankDisbursementProcessor.java`
[2026-04-14] | FEATURE | Gap/risk registry expanded after cross-module scan (accounting + platform-lib callback dependency): add **GAP-061** for child MFT CRR response-fidelity mismatch (status from callback `apiResponse` but body from shared `ExecutionContext.response` under webclient null-callback transport errors), plus 2am runbook entry for detection/mitigation | gaps-and-risks.md, runbooks.md, changelog.md
[2026-04-14] | FEATURE | Brain sync refresh (accounting + dependencies): add explicit CRR response-fidelity invariant to accounting flow/rule memory (WebClient callback discipline, NEFT fixed path, MFT open risk `GAP-061`, and callback scan focus files) | accounting-flows.md, accounting.mdc, changelog.md
[2026-04-14] | FEATURE | Persist incident response-signature memory for CRR RCA: NEFT-v2 STP vs MFT payload shape markers, mismatch detection rule, and child-NEFT retry-time expected CRR progression template for fast future forensic responses | accounting-flows.md, changelog.md
[2026-04-15] | BUG_FIX | Child NEFT L1 recovery on retry: when CLMT is still `DTFC_SUCCESS` but prior child-scoped `..._NEFT_NEF` CRR is non-success, `CallBankAPIForIndividualChildLoanDisbursementProcessor.performNEFTTransactionInquiry` now executes stage-1 inquiry (`ST_NEF`) instead of hard-skip (`DO_TRANSACTION=false`), enabling inquiry-led state progression without duplicate NEF transfer re-fire | CallBankAPIForIndividualChildLoanDisbursementProcessor.java, accounting-flows.md, accounting.mdc, gaps-and-risks.md, changelog.md
[2026-04-15] | BUG_FIX | Child disbursement retry L0 stabilization: `CallBankAPIForIndividualChildLoanDisbursementProcessor` now resolves prior CRR deterministically by lane/type (MFT type only, or child `..._NEFT_NEF` first with `..._NEFT_NEI` fallback) instead of a mixed latest-row query; this prevents timing-driven inquiry path variance during callback + `PARENT_SUCCESS` overlap | CallBankAPIForIndividualChildLoanDisbursementProcessor.java, accounting-flows.md, changelog.md
[2026-04-15] | REFACTOR | Knowledge sync correction: mark `GAP-061` resolved based on existing child-MFT fix commit (`1a789b6c7`), refresh accounting flow/rule note from “open risk” to resolved status, and annotate runbook as resolved | gaps-and-risks.md, accounting-flows.md, rules/accounting.mdc, runbooks.md, changelog.md

[2026-04-15] | BUG_FIX | NEFT v2 inquiry loop recovery (L0): when ST_NEF status inquiry returns non-definitive failure (not `PROCESSED`, `errorCode != 0` e.g. `NDF`), set `DO_TRANSACTION=true` and force `disbursement_status=DTFC_SUCCESS` so replay re-initiates ST_NEF instead of getting stuck repeatedly in inquiry; applied to both child and normal loan processors | changelog.md, `CallBankAPIForIndividualChildLoanDisbursementProcessor.java`, `CallBankAPIForDisbursementProcessor.java`
[2026-04-16] | BUG_FIX | NEFT v2 inquiry exception guard (L0): wrap `neftTransactionStatusInquiryV2` in try/catch so HDFC inquiry parser exceptions (e.g. `paymentlist` NPE on `NDF` response shape) are logged as `NEFT_TRANSACTION_INQUIRY` with correct CRR `transaction_type`, and replay switches to `DTFC_SUCCESS + DO_TRANSACTION=true` to re-initiate ST_NEF instead of repeatedly re-entering inquiry via outer disbursement catch | changelog.md, `CallBankAPIForIndividualChildLoanDisbursementProcessor.java`, `CallBankAPIForDisbursementProcessor.java`

[2026-04-16] | BUG_FIX | NEFT v2 parent/child parity + double-debit guards: shared `NeftStage1InquiryGate` for `DTFC_SUCCESS` + non-success NEF CRR stage-1 inquiry; parent `CallBankAPIForDisbursementProcessor` matches child; both skip ST_NEF initiation when a **SUCCESS** NEF CRR already exists for the same `transaction_type`; `PostNEFTChildLoanBankDisbursementProcessor` derives child-scoped `…_NEFT_NEF` / `…_NEFT_NEI` for CRR when WebClient callback omits `transactionIdentifier` | changelog.md, accounting-flows.md, rules/accounting.mdc, `NeftStage1InquiryGate.java`, `CallBankAPIForDisbursementProcessor.java`, `CallBankAPIForIndividualChildLoanDisbursementProcessor.java`, `PostNEFTChildLoanBankDisbursementProcessor.java` (`novopay-platform-accounting-v2`)

[2026-04-16] | GAP_RESOLVED | Parent NEFT v2 ST_NEI idempotency (P0): `shouldSkipNeftStage2Initiation` now skips duplicate ST_NEI when SUCCESS CRR exists for orchestration-scoped `…_NEFT_NEI` for **both** `NEFT_STAGE_1_SUCCESS` and `NEFT_STAGE_2_PENDING` (child parity); `doNEFTTransaction` re-checks before `neftPaymentV2Stage2`. Summary-table row “NEFT stage-2 idempotency gate…” marked RESOLVED | gaps-and-risks.md, changelog.md, accounting-flows.md, rules/accounting.mdc, `CallBankAPIForDisbursementProcessor.java` (`novopay-platform-accounting-v2`)

[2026-04-17] | FEATURE | Flow Sync Wave 0 pre-flight: add `.cursor/flow-sync-progress.md` tracker (waves 1–6 + counters); no new gaps or flows mined | flow-sync-progress.md, changelog.md

[2026-04-17] | FEATURE | Flow Sync Wave 1 — accounting: ENTRY POINT REGISTRY + full orchestration Request index (362 nodes / 348 unique apiNames), `loanWriteoff` flow deep-dive, DB registry scaffold (entity/repo/DAO counts), `DefaultExecutionContext` local-first note; **GAP-062** (High) for `loanWriteoff` vs `PrepaymentApproppriationProcessor` EC key mismatch + runbook; Wave 1 Java “read every file” scoped honestly in `accounting-flows.md` | accounting-flows.md, gaps-and-risks.md, runbooks.md, flow-sync-progress.md, changelog.md

[2026-04-17] | FEATURE | Flow Sync Wave 2 — service contracts + EC: `service-contracts.md` HTTP registry (NovopayInternalAPIClient / HttpAPIClient behaviour, ~100+ `callInternalAPI` inventory), `event-registry.md` expanded schemas for accounting Kafka paths (`bulk_collection_data_*`, `disburse_loan_api_`, `los_lms_*`), NEW `execution-context-contracts.md` (`postTransaction` + `loanWriteoff` + risk taxonomy), **GAP-063** (Medium) NPE risk on missing `account_details`; flow-sync Wave 2 COMPLETE | service-contracts.md, event-registry.md, execution-context-contracts.md, gaps-and-risks.md, flow-sync-progress.md, changelog.md

[2026-04-17] | FEATURE | Flow Sync Wave 3 — LOS + Payments deep contracts: `accounting-flows.md` sections **LOS ↔ Accounting** + **Payments ↔ Accounting** (HTTP/Kafka maps, disbursement spine, bulk_collection field alignment); `service-contracts.md` Wave 3 registry; `event-registry.md` Wave 3 re-verify notes; **GAP-064** (Medium) `collection_list` null NPE in `CreateOrUpdateBulkCollectionConsumer`; **`entity_type`** disburse sync mismatch **CONFIRMED OPEN** | accounting-flows.md, service-contracts.md, event-registry.md, gaps-and-risks.md, flow-sync-progress.md, changelog.md

[2026-04-17] | FEATURE | Flow Sync Wave 4 — Batch + Actor + Masterdata: `accounting-flows.md` **Batch → Accounting** (scheduler shell vs 71 accounting batch configs, `interestAccrualPosting` CRR evidence, `loanAccountClosure` reader ACTIVE guard); `service-contracts.md` Actor + Masterdata tables; **NEW** `cross-service-transactions.md` (10 multi-service flows); `gaps-and-risks.md` synthesis note (no new gap IDs); `runbooks.md` cross-service pointer; Wave 4 COMPLETE in `flow-sync-progress.md` | accounting-flows.md, service-contracts.md, cross-service-transactions.md, gaps-and-risks.md, runbooks.md, flow-sync-progress.md, changelog.md

[2026-04-17] | FEATURE | Flow Sync Wave 5 — Knowledge graph + API catalogue: **NEW** `api-catalogue.md` (1797 unique orchestration `apiName` across 14 repos + Kafka/batch/scheduler sections); **NEW** `knowledge-graph.md` (node/edge registry,6 money paths, SPOFs, contract health); **NEW** `knowledge-graph.mmd` (Mermaid); Wave 5 COMPLETE in `flow-sync-progress.md` | api-catalogue.md, knowledge-graph.md, knowledge-graph.mmd, flow-sync-progress.md, changelog.md

[2026-04-17] | FEATURE | Align full agent setup with Flow Sync knowledge graph: `.cursorrules` (bootstrap step 4, routing table, checklist), `onboarding.md` (read order + knowledge file list + graph-tied quartet), `00-workspace-core.mdc` (bootstrap 4–5, consultation order, expansion template, efficiency), `architecture.md` §10 layer row, `system_brain/system_overview.md`, `index.mdc`, `multi-agent-spawning.mdc` (partition naming), `AGENTS.md` bootstrap pointer | those files + changelog.md

[2026-04-17] | FEATURE | `AGENTS.md`: knowledge-graph-first navigation, parallel read-only agent spawn recipe, multi-angle fix checklist (contracts, gaps, idempotency, observability); links `execution-context-contracts.md`, `api-catalogue.md`, `cross-service-transactions.md` | AGENTS.md, changelog.md

[2026-04-17] | FLOW_SYNC_COMPLETE | Waves 0–6 complete | Accounting flows: 6 money paths + 362 `<Request>` (see `accounting-flows.md`) | APIs catalogued: 1797 HTTP + 146 Kafka | EC keys: spine in `execution-context-contracts.md` | Contracts (rep. 16 edges): 2 aligned / 11 drift / 2 mismatch | New gaps: 5 Medium (**GAP-065..069**); summary table **High:17 Medium:10** | Cross-service compensation: none automated (10 txns mapped) | Files touched Wave 6: `gaps-and-risks.md`, `accounting-flows.md`, `service-contracts.md`, `event-registry.md`, `cross-service-transactions.md`, `knowledge-graph.md`, `flow-sync-progress.md`, `.cursorrules`, `changelog.md`; reference corpus from Waves 2–5: `execution-context-contracts.md`, `cross-service-transactions.md`, `api-catalogue.md`, `knowledge-graph.mmd` | flow-sync-progress.md: **ALL WAVES COMPLETE**

[2026-04-17] | GAP_RESOLVED | Disburse async path: `los_lms_disbursement_sync` carries **`stan`** and **`entity_type`** from `ExecutionContext`; JTF `disburseLoan_requestTemplate.json` (mfi + product) serializes `entity_type` into disburse request so EC has it for sync; consumer refactor (parse-once, richer logs). **GAP-066** + summary-table **entity_type** producer row closed. Branch `fix/disburse-sync-stan-entity-type` from `mfi_integration_v3.2.8.4.1` | `LmsMessageBrokerConsumer.java`, deploy templates, `gaps-and-risks.md`, `.cursorrules`, `changelog.md` (`novopay-platform-accounting-v2` + workspace `.cursor/`)

[2026-04-17] | BUG_FIX | Manual disburse rail switch: `CallBankAPIForDisbursementProcessor` gates MFT vs NEFT **status inquiry** on `disbursement_mode` matching the latest CRR leg (avoid MFT inquiry when current mode is `OTHBACCT` but latest row is still `…_MFT`) | `CallBankAPIForDisbursementProcessor.java` (`novopay-platform-accounting-v2`), `rules/accounting.mdc`, `changelog.md`
[2026-04-22] | FEATURE | Disbursement 100% audit revalidation (cross-service): reconciled code vs knowledge docs; reopened disbursement sync drift rows (`entity_type`, `stan`) and added **GAP-070..073** (sync payload contract, skip-without-sync branch, pre-guard consumer parse brittleness, NEFT callback UTR map key mismatch). Updated audit/state-machine notes and runbooks across `.cursor` + `system_brain` for replay/idempotency and DB-state convergence visibility. | gaps-and-risks.md, accounting-flows.md, event-registry.md, knowledge-graph.md, cross-service-transactions.md, flow-sync-progress.md, runbooks.md, system_brain/flows/disbursement.md, system_brain/debugging/runbooks_disbursement.md, changelog.md

[2026-04-22] | FEATURE | Parent payment reinitiation implementation sync: updated knowledge graph and disbursement flow memory with execution-validated behavior (parent MFT/NEFT `_REINIT` lane typing, forward reference progression, explicit second reinit acceptance after fresh mode update) and added resolved risk note for execution-path validation. | knowledge-graph.md, accounting-flows.md, gaps-and-risks.md, system_brain/flows/disbursement.md, changelog.md
[2026-04-22] | BUG_FIX | Death-foreclosure insurance RE_UPLOAD flow now defers `updateTaskWorkflow` to transaction `afterCommit` in `DeathForeclosureInsuranceWriter` so Task workflow is updated only after accounting chunk commit; accounting rollback no longer advances task state. | changelog.md, `trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/deathforeclosure/writer/DeathForeclosureInsuranceWriter.java`
[2026-04-22] | BUG_FIX | Death-foreclosure insurance RE_UPLOAD post-commit task sync hardened: bounded retry for `updateTaskWorkflow`; if all attempts fail, writer compensates accounting staging by restoring prior `claim_status` and tagging reason `TASK_WORKFLOW_SYNC_FAILED_AFTER_COMMIT` to keep accounting/task state aligned for safe reprocessing. | changelog.md, `trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/deathforeclosure/writer/DeathForeclosureInsuranceWriter.java`
[2026-04-23] | FEATURE | Disbursement sanity process locked for repeatable Kafka-entry full-flavour testing: default two-customer env strategy (`KAFKA_ENTRY_TEST_CUSTOMER_ID` + `...SECONDARY...`) documented in playbook/rules and process doc with one-command run + customer-picker SQL; added explicit local git hygiene guidance to avoid staging/pushing system artifacts from local runs. | .cursor/rules/disburse-loan-sanity-suite.mdc, .cursor/rules/disbursement-testing-playbook.mdc, docs/disbursement-sanity/PROCESS.md, changelog.md
[2026-04-23] | FEATURE | Disbursement playbook matrix updated for one-shot all-flavour runs: explicit JLG/INDL/SHG Kafka-entry commands, product-mode constraints (JLG `ACCTWB`), mandatory secondary-customer S7 lane, and SHG CLMT queue evidence requirement; customer picker generalized to `:product_id`. | .cursor/rules/disburse-loan-sanity-suite.mdc, .cursor/rules/disbursement-testing-playbook.mdc, docs/disbursement-sanity/PROCESS.md, changelog.md
[2026-06-25] | WORKSPACE | Hot-path perf gate workspace-wide: `10-quality-gates.mdc` (alwaysApply) — processors/services/consumers/APIs, not batch globs only; `scripts/lib/hot_path_scan.py` + `hot-path-scan.sh` (DAO-in-loop, helper-from-loop, stream-in-loop); wired autopilot FIX+SHIP/FEATURE/CODE+DAO + money `ship-loop-gate` WARN (`HOT_PATH_SCAN_STRICT=1` to block). | hot-path-perf-gate.mdc, batch-hot-path-perf.mdc, minimal-fix-impact-gate.mdc, hot_path_scan.py, workspace_autopilot.py, ship-loop-gate.sh, rule_inventory.md

[2026-06-29] | BUG_FIX | DCF GL billed/unbilled principal split when reporting date follows death: run reporting-date billing sync before `getUnpaidBilledPrincipalForDeathForeClosure` and BLD_PRIN/UNBLD_PRIN split; death-date billing before outstanding unchanged (SDCP-10494). accounting-v2 `b0a3757f3` on `mfi_integration_v3.3.1.2` | changelog.md

[2026-04-23] | FEATURE | Disbursement demo setup improved for direct asks: wrapper now supports product-scoped runs (`JLG`/`INDL`/`SHG`/`ALL`) while preserving DB-backed verification summary; rules/process docs updated to make this the default execution path when user asks to run disbursement by product. | scripts/run_disbursement_full_matrix.sh, .cursor/rules/disburse-loan-sanity-suite.mdc, .cursor/rules/disbursement-testing-playbook.mdc, docs/disbursement-sanity/PROCESS.md, changelog.md

[2026-07-07] | CONFIG | Enable NEFT v2 on `mfi_integration_v3.4.2.3` by flipping `DisbursementBankCallConstants.USE_NEFT_V1=false` (accounting-v2 routing flag; lib already contains NEFT v2 implementation). | `novopay-platform-accounting-v2/.../DisbursementBankCallConstants.java`, changelog.md

[2026-07-09] | FIX | loanPrepayment APPROVE 132268: `ValidateFinalPrepaymentProcessor.fetchForeclosureAmount()` now adds persisted `billed_dpi_amount_to_be_paid` and `bpd_amount_to_be_paid` (aligned with `CreatePrepaymentDetailsProcessor` + simulation total). QA1 `prepayment_details_id=262057` / `total_foreclosure_amount=16069.00`. | `novopay-platform-accounting-v2/.../ValidateFinalPrepaymentProcessor.java`, changelog.md

- 2026-07-09 acct e175b78cb pushed to origin (SDCP-11016); brain kg-flow fetchLoanForeclosureSimulationDetails; push-origin failed dpic.ship_close post_maturity, git push succeeded.
## 2026-07-10 | accounting-v2 `77921d275f` | mfi_integration_v3.7.1 | dpiAccrualBooking EMI-due posting anchor (sealed_unposted audit)

- 2026-07-15 | accounting-v2 `59e9686a80` mfi_integration_v3.4.2.4 | SDCP-11085/TDPQA-127 SHG child CLB copies member/parent sanction_date into loan_details (forward only; INDL LOS; stock backfill ops)
- 2026-07-16 | workspace | infra | workspace-disk-clean.sh + super-agent clean — purge rotated service logs (~371MB reclaimed); wired max-pass + autopilot end; active bootRun logs preserved when service UP

## 2026-07-17 | acct b256efd054 | DCF force-bill client_ref → accountId||valueDateMs (no DFC_PRTL_BILL_); e2e PASS parent=6003896527

- 2026-07-17 | workspace | PR review L1 — added a read-only GitHub evidence collector, strict branch/environment/SHA verdict contract, fintech review lenses, dual report/developer-response output, and canonical router/skill-index integration.

## 2026-07-17 | accounting `8a1a7cd07` | mfi_integration_v3.7.1 | DPI BPD util: loanPrepayment create uses same calculateTillForeclosureDate as foreclosure sim; approve ValidateFinal unchanged.

- 2026-07-17 | workspace | initial-setup 3.7.1 local schema sync: documented bundled Flyway 5.2.4 `localhost.sh` workflow, safe history reconciliation, local-only setup vs release migration boundary; accounting/LOS local histories current. Fresh upstream `e4ade8c3f8` still has no migration for `loan_account.dpi_suspense_amount`.

## 2026-07-17 | workspace | DPI harness 8/8 PASS serialized (TDPQA-83 ready for QA retest)
- Product on `mfi_integration_v3.7.1` @ `8a1a7cd077` (unify) + day-window `e2789d5f0` + booking `77921d275f` — no new product code this turn.
- Prior never-green = orphan full-portfolio calc backlog (~29k unposted), not product bugs. `sealed_unbilled` was harness FP (settle race + audit scope) — fixed via isolate/purge/settle-poll + refined billing-eligible rule.
- Matrix PASS: three_job, posting, grace, grace_overlap (audit 0), booking_anchor, two_emi, SHG parity, bpd_sim ₹29. TDPQA-83 handoff refreshed; SDCP-11012/11016/11030/11048 left untouched (already released).

- 2026-07-17 | workspace | initial-setup hardening — added dependency-led `scripts/bin/initial-setup-local.sh` around untouched Flyway 5.2.4 runner; documented legacy per-schema history, safe reconciliation, and GAP-077 duplicate versions; refreshed mixed-train workspace state. Initial-setup repo remained clean at upstream `e4ade8c3f8` and was not pushed.
## 2026-07-19 | platform-lib `793ebabbcd` + accounting `d982430d1d` | HTTP wire INFO / CRR JSON unchanged
- EC `http_wire_request`/`http_wire_response` + INFO; CRR columns stay pre-wire JSON; companion CRR helper INFO. NeftV2BankReferenceUtil JSON-safe.

- 2026-07-20: CLB ChildLoanBookingEventsQueueDataPopulator fail-closed blank/missing member REP (130142), no parent REP copy — acct ac87585a2 mfi_integration_v3.4.2.5
- 2026-07-20 | WORKSPACE | JIRA skills sync-up: master `jira-fix-update` template + stricter `jira-fix-adf.py` scans (never_mention, strict ticket scope, GitHub + comment-handoff SQL ban) and updated TDPQA ADF sections (Summary/Root Cause/Fix/Dev Verification/QA Retest/Notes) | .cursor/skills/jira-fix-update/SKILL.md, .cursor/skills/jira-fix-update/mentions.json, .cursor/skills/jira-fix-update/fields-reference.md, scripts/bin/jira-fix-adf.py, scripts/bin/jira-enrich.sh, changelog.md

- 2026-07-20 | BUG_FIX | TDPQA-54 disbursement Redis in-flight locks: LOS producer and Accounting consumer now use atomic owner-token acquire with configurable 600000 ms TTL; platform-lib adds Lua compare-and-delete; ambiguous intermediate `DEFAULT` replay fails closed. Builds PASS; `disbursement.redis_inflight_lock_sim` PROCESSOR_MIRROR_SIM + LOCAL_REDIS_RUNTIME PASS; live INDL fixture blocked before loan creation by existing mandate validation. | lib `9c5c82d2d8`, LOS `0e4a0be2bd`, accounting `f9d803c4e`; `scripts/testing/registry.json`

- 2026-07-21 | OPS | TDPQA-54 V000125 masterdata seed (disburse Redis in-flight TTL props) + prod pre-deploy pack for manual Flyway/DBA | initial-setup `53aadb49`, `scripts/sql/deploy/prod_pre_V000125_tdpqa54_disburse_redis_ttl_config.sql`

## 2026-07-22 | acct `935c52743` | mfi_integration_v3.4.2.4 | DCF force-bill CRN uniqueness (134497)
DeathForeclosureInsuranceWriter.buildForceBillClientReference now includes deathForeclosureDetailsId so non-last then last-child parent force-bill on same reporting date do not collide.

## 2026-07-23 | SP-329 | accounting | nestloop/BNL off on EOD batch readers (b3478a1a6)
