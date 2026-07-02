# Workspace Changelog

# Format: [DATE] | [TYPE] | [Summary] | [.cursor/ files updated]
# Types: INITIAL_SCAN | BUG_FIX | FEATURE | SCHEMA | EVENT | GAP_RESOLVED | REFACTOR

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

[2026-04-11] | FEATURE | Add **PROMPT SELF-EXPANSION RULE** to `always-on.mdc` — classify request (bug/feature/investigation/review/refactor/question), expand task (services, flows, gaps, files, risk, blast radius), confirm with user before code/config changes; exceptions: simple questions, read-only traces, brain/weekly sync | always-on.mdc, changelog.md

[2026-04-11] | REFACTOR | Consolidate `.cursor/rules/*.mdc` from 44 → **20** files; merge accounting/sync/preflight/signoff/module-knowledge into `accounting.mdc`; session/brain/debugging/maintenance into `always-on.mdc`; architect/framework/tiered/bank/DB/finance/repo-style into `architect-thinking.mdc`; local DB + disburse resets into `local-dev-workflows.mdc`; git + fork + sync phrase into `git-workflow.mdc`; Kafka consumer patterns into `events.mdc`; docs maintenance into `docs-outside-service-repos.mdc`; disbursement multi-path into `multi-path-state-persistence-safety.mdc`; **only** `always-on.mdc` + `discuss-before-updating.mdc` remain `alwaysApply: true`; update `rule_inventory.md`, cross-links in `AGENTS.md`, `.cursorrules`, `architecture.md`, `accounting-flows.md`, `conventions.md`, `index.mdc`, `system_brain/**` refs | accounting.mdc, always-on.mdc, architect-thinking.mdc, local-dev-workflows.mdc, git-workflow.mdc, events.mdc, docs-outside-service-repos.mdc, multi-path-state-persistence-safety.mdc, platform-lib.mdc, batch.mdc, los.mdc, payments.mdc, gateway.mdc, execution-context-discipline.mdc, no-flow-break-impact-check.mdc, api-contract-safety.mdc, multi-agent-spawning.mdc, disburse-loan-sanity-suite.mdc, effective-prompts-and-issue-triage.mdc, discuss-before-updating.mdc, rule_inventory.md, AGENTS.md, .cursorrules, architecture.md, accounting-flows.md, conventions.md, index.mdc, posting_engine.md, rule_improvements_applied.md, changelog.md

[2026-04-10] | BUG_FIX | `executeLMSPortfolioTransfer`: expand loan `account_id` scope to include ACTIVE child loans (`parent_loan_account_id` in seed set) for GL detail build, `doGLTransfer` office updates, and `servicing_emp_id` updates | changelog.md, accounting-module-knowledge.mdc

[2026-04-11] | REFACTOR | **`always-on.mdc`**: stricter **session bootstrap** (mandatory before logs/repo reads for substantive work); **prompt self-expansion** + confirm before investigation tools **or** edits for high-blast-radius read-only (prod logs, money, multi-service, contracts, DB/cluster); narrow exceptions; dedupe duplicate bootstrap block; **`multi-agent-spawning.mdc`**: point accounting rail to merged **`accounting.mdc`**; **`rule_inventory.md`** row sync | always-on.mdc, multi-agent-spawning.mdc, rule_inventory.md, changelog.md
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

[2026-04-17] | FEATURE | Align full agent setup with Flow Sync knowledge graph: `.cursorrules` (bootstrap step 4, routing table, checklist), `onboarding.md` (read order + knowledge file list + graph-tied quartet), `always-on.mdc` (bootstrap 4–5, consultation order, expansion template, efficiency), `architecture.md` §10 layer row, `system_brain/system_overview.md`, `index.mdc`, `multi-agent-spawning.mdc` (partition naming), `AGENTS.md` bootstrap pointer | those files + changelog.md

[2026-04-17] | FEATURE | `AGENTS.md`: knowledge-graph-first navigation, parallel read-only agent spawn recipe, multi-angle fix checklist (contracts, gaps, idempotency, observability); links `execution-context-contracts.md`, `api-catalogue.md`, `cross-service-transactions.md` | AGENTS.md, changelog.md

[2026-04-17] | FLOW_SYNC_COMPLETE | Waves 0–6 complete | Accounting flows: 6 money paths + 362 `<Request>` (see `accounting-flows.md`) | APIs catalogued: 1797 HTTP + 146 Kafka | EC keys: spine in `execution-context-contracts.md` | Contracts (rep. 16 edges): 2 aligned / 11 drift / 2 mismatch | New gaps: 5 Medium (**GAP-065..069**); summary table **High:17 Medium:10** | Cross-service compensation: none automated (10 txns mapped) | Files touched Wave 6: `gaps-and-risks.md`, `accounting-flows.md`, `service-contracts.md`, `event-registry.md`, `cross-service-transactions.md`, `knowledge-graph.md`, `flow-sync-progress.md`, `.cursorrules`, `changelog.md`; reference corpus from Waves 2–5: `execution-context-contracts.md`, `cross-service-transactions.md`, `api-catalogue.md`, `knowledge-graph.mmd` | flow-sync-progress.md: **ALL WAVES COMPLETE**

[2026-04-17] | GAP_RESOLVED | Disburse async path: `los_lms_disbursement_sync` carries **`stan`** and **`entity_type`** from `ExecutionContext`; JTF `disburseLoan_requestTemplate.json` (mfi + product) serializes `entity_type` into disburse request so EC has it for sync; consumer refactor (parse-once, richer logs). **GAP-066** + summary-table **entity_type** producer row closed. Branch `fix/disburse-sync-stan-entity-type` from `mfi_integration_v3.2.8.4.1` | `LmsMessageBrokerConsumer.java`, deploy templates, `gaps-and-risks.md`, `.cursorrules`, `changelog.md` (`novopay-platform-accounting-v2` + workspace `.cursor/`)

[2026-04-17] | BUG_FIX | Manual disburse rail switch: `CallBankAPIForDisbursementProcessor` gates MFT vs NEFT **status inquiry** on `disbursement_mode` matching the latest CRR leg (avoid MFT inquiry when current mode is `OTHBACCT` but latest row is still `…_MFT`) | `CallBankAPIForDisbursementProcessor.java` (`novopay-platform-accounting-v2`), `rules/accounting.mdc`, `changelog.md`
[2026-04-22] | FEATURE | Disbursement 100% audit revalidation (cross-service): reconciled code vs knowledge docs; reopened disbursement sync drift rows (`entity_type`, `stan`) and added **GAP-070..073** (sync payload contract, skip-without-sync branch, pre-guard consumer parse brittleness, NEFT callback UTR map key mismatch). Updated audit/state-machine notes and runbooks across `.cursor` + `system_brain` for replay/idempotency and DB-state convergence visibility. | gaps-and-risks.md, accounting-flows.md, event-registry.md, knowledge-graph.md, cross-service-transactions.md, flow-sync-progress.md, runbooks.md, system_brain/flows/disbursement.md, system_brain/debugging/runbooks_disbursement.md, changelog.md

[2026-04-22] | FEATURE | Parent payment reinitiation implementation sync: updated knowledge graph and disbursement flow memory with execution-validated behavior (parent MFT/NEFT `_REINIT` lane typing, forward reference progression, explicit second reinit acceptance after fresh mode update) and added resolved risk note for execution-path validation. | knowledge-graph.md, accounting-flows.md, gaps-and-risks.md, system_brain/flows/disbursement.md, changelog.md
[2026-04-22] | BUG_FIX | Death-foreclosure insurance RE_UPLOAD flow now defers `updateTaskWorkflow` to transaction `afterCommit` in `DeathForeclosureInsuranceWriter` so Task workflow is updated only after accounting chunk commit; accounting rollback no longer advances task state. | changelog.md, `novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/deathforeclosure/writer/DeathForeclosureInsuranceWriter.java`
[2026-04-22] | BUG_FIX | Death-foreclosure insurance RE_UPLOAD post-commit task sync hardened: bounded retry for `updateTaskWorkflow`; if all attempts fail, writer compensates accounting staging by restoring prior `claim_status` and tagging reason `TASK_WORKFLOW_SYNC_FAILED_AFTER_COMMIT` to keep accounting/task state aligned for safe reprocessing. | changelog.md, `novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/deathforeclosure/writer/DeathForeclosureInsuranceWriter.java`
[2026-04-23] | FEATURE | Disbursement sanity process locked for repeatable Kafka-entry full-flavour testing: default two-customer env strategy (`KAFKA_ENTRY_TEST_CUSTOMER_ID` + `...SECONDARY...`) documented in playbook/rules and process doc with one-command run + customer-picker SQL; added explicit local git hygiene guidance to avoid staging/pushing system artifacts from local runs. | .cursor/rules/disburse-loan-sanity-suite.mdc, .cursor/rules/disbursement-testing-playbook.mdc, docs/disbursement-sanity/PROCESS.md, changelog.md
[2026-04-23] | FEATURE | Disbursement playbook matrix updated for one-shot all-flavour runs: explicit JLG/INDL/SHG Kafka-entry commands, product-mode constraints (JLG `ACCTWB`), mandatory secondary-customer S7 lane, and SHG CLMT queue evidence requirement; customer picker generalized to `:product_id`. | .cursor/rules/disburse-loan-sanity-suite.mdc, .cursor/rules/disbursement-testing-playbook.mdc, docs/disbursement-sanity/PROCESS.md, changelog.md
[2026-06-25] | WORKSPACE | Hot-path perf gate workspace-wide: `hot-path-perf-gate.mdc` (alwaysApply) — processors/services/consumers/APIs, not batch globs only; `scripts/lib/hot_path_scan.py` + `hot-path-scan.sh` (DAO-in-loop, helper-from-loop, stream-in-loop); wired autopilot FIX+SHIP/FEATURE/CODE+DAO + money `ship-loop-gate` WARN (`HOT_PATH_SCAN_STRICT=1` to block). | hot-path-perf-gate.mdc, batch-hot-path-perf.mdc, minimal-fix-impact-gate.mdc, hot_path_scan.py, workspace_autopilot.py, ship-loop-gate.sh, rule_inventory.md

[2026-06-29] | BUG_FIX | DCF GL billed/unbilled principal split when reporting date follows death: run reporting-date billing sync before `getUnpaidBilledPrincipalForDeathForeClosure` and BLD_PRIN/UNBLD_PRIN split; death-date billing before outstanding unchanged (SDCP-10494). accounting-v2 `b0a3757f3` on `mfi_integration_v3.3.1.2` | changelog.md

[2026-04-23] | FEATURE | Disbursement demo setup improved for direct asks: wrapper now supports product-scoped runs (`JLG`/`INDL`/`SHG`/`ALL`) while preserving DB-backed verification summary; rules/process docs updated to make this the default execution path when user asks to run disbursement by product. | scripts/run_disbursement_full_matrix.sh, .cursor/rules/disburse-loan-sanity-suite.mdc, .cursor/rules/disbursement-testing-playbook.mdc, docs/disbursement-sanity/PROCESS.md, changelog.md
