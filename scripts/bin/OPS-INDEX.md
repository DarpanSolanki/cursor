# OPS-INDEX — scripts/bin (auto-generated)

Regenerate: `bash scripts/bin/build-ops-index.sh` (also via intel-session-sync hook).

| Name | Purpose | Called-by |
|------|---------|-----------|
| `accounting-flow-coverage.sh` | Accounting flow coverage report — ALL domains (read, write, batch, money). | scripts/bin/accounting-flow-proof.sh |
| `accounting-flow-proof.sh` | Accounting flow proof — routes by detected domain (ALL flows, not money-only). | — |
| `agent-ops.sh` | Autonomous workspace ops — agents call this; do not re-decide manually. | scripts/bin/disburse-indl-kafka-quick.sh, scripts/bin/disburse-indl-quick.sh, scripts/bin/disburse-quick.sh, scripts/bin/disburse-shg-quick.sh, scripts/bin/ship-loop-gate.sh, scripts/lib/agent-ops-lib.sh, scripts/lib/pipeline_chain_audit.py, scripts/testing/agent_router.py |
| `agent-probe.sh` | Agent probe entry — EVERY timed probe must go through with-budget (never bare sleep/hang). | scripts/bin/run-guarded.sh |
| `agent-router.sh` | Classify user task → skill chain + consultation order (proof-backed routing). | scripts/bin/workspace-sanity.sh, scripts/testing/super_agent.py |
| `assert-build-current.sh` | Fail closed when the RUNNING JVM predates the compiled classes or the source. | scripts/lib/agent-ops-lib.sh |
| `assert-notification-sms-throughput.sh` | Report notification_sms_ consumer throughput (SP-308 L0) for the checked-out | scripts/lib/test_kg_ship_resolve_notification.py |
| `audit-batch-skip-mappers.sh` | Enforce batch write-skip contract (platform-lib + job mappers stay aligned). | scripts/bin/ship-loop-gate.sh |
| `brain-gap-capture.sh` | Record a gap/risk discovered during analysis or implementation (self-learning inbox). | — |
| `brain-triage.sh` | Triage discovery inbox → promote to gaps or dismiss. | scripts/bin/workspace-sanity.sh |
| `build-architecture-digest.sh` | Build .cursor/architecture-digest.md from .cursor/architecture.md (≤8KB). | .cursor/hooks/intel-session-sync.sh |
| `build-gaps-digest.sh` | Build .cursor/gaps-and-risks-digest.md from .cursor/gaps-and-risks.md (≤14KB). | .cursor/hooks/intel-session-sync.sh |
| `build-ops-index.sh` | Regenerate scripts/bin/OPS-INDEX.md from script headers + caller scan. | .cursor/hooks/intel-session-sync.sh, scripts/bin/ops-bin-hygiene.sh |
| `capture-flow.sh` | After a fix + test on a money path — capture full API footprint for the suite. | scripts/bin/workspace-close.sh, scripts/lib/footprint_evidence_gate.py, scripts/testing/agent_router.py, scripts/testing/run_evidence.py |
| `contract-sync.sh` | Scan cross-service contracts (orchestration XML + Kafka) and refresh contracts.jsonl | scripts/testing/ftg.py |
| `db-local-hygiene.sh` | Local Yugabyte hygiene — orphan pg_temp / pg_toast_temp schemas. | scripts/bin/workspace-hygiene.sh |
| `db-local-write.sh` | Local Yugabyte writes only (127.0.0.1:5433). Agents use this instead of raw psql to remote | scripts/bin/disburse-indl-kafka-quick.sh, scripts/bin/disburse-indl-quick.sh, scripts/bin/purge-local-dpi.sh, scripts/lib/local_parity_gate.py |
| `disburse-any-quick.sh` | Unified local disburseLoan entry — PRODUCT_TYPE=INDL/JLG/SHG (default JLG). | — |
| `disburse-indl-kafka-quick.sh` | Fast local disburseLoan — INDL via Kafka (TDPQA-54): LOS-shaped message + Redis producer N | — |
| `disburse-indl-quick.sh` | Fast local disburseLoan — INDL minimal stage suite (flat payload, member_details null, NEF | scripts/bin/disburse-any-quick.sh, scripts/lib/test_ship_push_workspace_safe.py |
| `disburse-quick.sh` | Fast local disburseLoan — JLG minimal stage suite (flat payload, member_details null). | scripts/bin/disburse-any-quick.sh, scripts/bin/disburse-indl-quick.sh, scripts/bin/workspace-smoke.sh, scripts/lib/ship_change_scope.py |
| `disburse-shg-quick.sh` | Fast local SHG disburseLoan — minimal stage suite (parent + member_details[] / CLMT path). | scripts/bin/disburse-any-quick.sh |
| `dpi-booking-posting-guard.sh` | Static guard: DPI accrual booking posts on month-end OR any EMI INT/PRIN due seal. | scripts/bin/dpi-money-proof.sh, scripts/lib/ship_change_scope.py |
| `dpi-june-slice-proof.sh` | Job-first proof: 8060160 June month-end slice via real dpiAccrualCalculation + booking. | — |
| `dpi-money-proof.sh` | DPI money-path SQL proof chain — run after EOD or before declaring DPI ship done. | — |
| `dpi-sanity.sh` | DPI batch sanity: grace-chain E2E + multi-EMI + fixture EOD chain. | scripts/bin/agent-ops.sh |
| `enrichment-audit.sh` | Audit self-learning pipeline: commit ↔ changelog ↔ KG. | .cursor/hooks/pre-push-checklist.sh, scripts/bin/smoke-workspace.sh, scripts/bin/workspace-smoke.sh, scripts/lib/registry_companion_gate.py, scripts/testing/workspace_autopilot.py |
| `enrichment-sync.sh` | Tiered KG enrichment — rebuild only when the graph must change. | .cursor/hooks/post-commit-kg-flag.sh, .cursor/hooks/post-ntest-intel-sync.sh, .cursor/hooks/post-push-enrichment.sh, scripts/bin/enrichment-audit.sh, scripts/bin/kg-enrich.sh, scripts/bin/smoke-workspace.sh, scripts/bin/workspace-max-pass.sh |
| `ensure-dpi-branches.sh` | Verify DPI feature repos are on feature/delayed_payment_interest | — |
| `env-smoke.sh` | Env connectivity smoke — ping configured wrappers; write results into workspace-ops-state. | scripts/bin/agent-ops.sh, scripts/bin/workspace-doctor.sh |
| `flow-onboard.sh` | Onboard a new orchestration apiName into local test harness. | scripts/bin/super-machine-smoke.sh, scripts/testing/flow_trace.py |
| `flowtest-lock-status.sh` | Print flowtest e2e lock status: held Y/N + owner metadata. | scripts/bin/stack-doctor.sh |
| `flyway-checksum.sh` | Compute Flyway 5.2.4 migration checksum (matches mfi_accounting.flyway_schema_history). | — |
| `flyway-prod-deploy-pack.sh` | Generate production deploy SQL: DDL + flyway_schema_history INSERT (manual prod path). | — |
| `foreclosure-local-setup.sh` | One-shot local setup for foreclosure E2E (accounting + payments schema + service endpoints | — |
| `ftg-enrich.sh` | Merge sources.jsonl + ntest registry + unit test scan into flows.jsonl | — |
| `ftg.sh` | (no header) | — |
| `fwd-port.sh` | Read-only release-train fix discovery and forward-port analysis. | scripts/bin/workspace-smoke.sh, scripts/testing/corroborate.py |
| `git-fetch-all.sh` | Fetch origin + upstream for all service repos (no checkout/rebase). Updates workspace stat | scripts/bin/sync-branches.sh |
| `git-workspace-status.sh` | Refresh cross-session git workspace state (local only, no fetch — fast). | scripts/lib/train_banner.py |
| `hot-path-scan.sh` | Workspace hot-path perf heuristic (DAO-in-loop, stream-in-loop). Agents only. | scripts/bin/ship-loop-gate.sh, scripts/testing/workspace_autopilot.py |
| `impact-tests.sh` | Dynamic impact-tests — git diff → KG blast radius → registry cases + WHY. | .cursor/hooks/kg-session-watermark.sh, scripts/bin/ship-loop-gate.sh, scripts/lib/pipeline_chain_audit.py |
| `initial-setup-local.sh` | (no header) | — |
| `install-kg-git-hooks.sh` | Install post-checkout hook in each service repo → kg-session-sync on branch change. | scripts/bin/install-user-claude-gates.sh, scripts/bin/new-machine-setup.sh |
| `install-user-claude-gates.sh` | Install / verify Cursor hooks + git gates for sliProdClaude. | scripts/bin/new-machine-setup.sh, scripts/bin/workspace-max-pass.sh |
| `intel-automation.sh` | Local + cron entrypoints for intelligence automations (fast by default). | scripts/bin/super-machine.sh |
| `java-comment-lint.sh` | Fail-closed Java comment verbosity lint (DPI paths). Agents only. | scripts/bin/ship-loop-gate.sh |
| `jira-enrich.sh` | Fast JIRA handoff: one pack build + optional REST apply (single OAuth decrypt). | — |
| `jira-fix-handoff.sh` | Build ADF JSON for SDCP fix handoff fields. No API calls — pipe into editJiraIssue. | — |
| `jira-handoff.sh` | Jira handoff bridge — validates Dev-Test ADF BEFORE any post (Upgrade 7). | scripts/bin/capture-flow.sh |
| `kg-align.sh` | Fail-closed: sync KG then assert watermark matches a train (branch-wise impact hygiene). | .cursor/hooks/post-checkout-kg.sh, scripts/lib/test_kg_knowledge_ship_routing.py |
| `kg-enrich.sh` | Tiered KG enrich — see scripts/bin/enrichment-sync.sh and 20-ship-gates.md. | .cursor/hooks/kg-write-state.sh, .cursor/hooks/pre-commit-kg-reminder.sh, scripts/bin/enrichment-audit.sh, scripts/bin/kg-switch.sh, scripts/bin/smoke-workspace.sh, scripts/bin/workspace-close.sh |
| `kg-ensure-fresh.sh` | Ensure KG matches live multi-repo branch-set before money-path analysis. | .cursor/hooks/kg-session-watermark.sh, .cursor/hooks/kg-write-state.sh, scripts/bin/enrichment-audit.sh, scripts/bin/setup-local.sh, scripts/bin/ship-knowledge-gate.sh, scripts/bin/workspace-close.sh, scripts/bin/workspace-doctor.sh, scripts/bin/workspace-health.sh |
| `kg-mcp-smoke.sh` | Smoke-test trustt-kg MCP: all 17 tools, JSON-RPC hygiene, semantic needles, align isError. | scripts/bin/ship-loop-gate.sh, scripts/bin/workspace-doctor.sh, scripts/lib/test_kg_mcp_e2e.py |
| `kg-quick-check.sh` | Cheap branch-set check — no sync. Exit 0=fresh, 1=stale/missing. | scripts/bin/kg-ensure-fresh.sh, scripts/bin/workspace-doctor.sh, scripts/bin/workspace-health.sh, scripts/testing/workspace_autopilot.py |
| `kg-self-enhance.sh` | Self-enhance trustt-kg after curated/diag/learning edits: | scripts/lib/test_kg_knowledge_ship_routing.py |
| `kg-session-sync.sh` | Cache-first KG sync — multi-repo branch-set aware (LRU cache per composite key). | .cursor/hooks/kg-session-watermark.sh, .cursor/hooks/kg-write-state.sh, scripts/bin/install-kg-git-hooks.sh, scripts/bin/kg-ensure-fresh.sh, scripts/bin/kg-quick-check.sh, scripts/bin/sync-branches.sh, scripts/bin/workspace-close.sh, scripts/bin/workspace-doctor.sh |
| `kg-snapshot.sh` | Ship a built KG with the repo so a new machine has knowledge before cloning 21 repos. | scripts/bin/new-machine-setup.sh |
| `kg-switch.sh` | Sync KG to current multi-repo branch checkout (cache-restore or rebuild). | .cursor/hooks/kg-write-state.sh, .cursor/hooks/post-checkout-kg.sh, scripts/bin/enrichment-audit.sh, scripts/bin/ensure-dpi-branches.sh, scripts/bin/kg-align.sh, scripts/bin/kg-self-enhance.sh, scripts/bin/kg-session-sync.sh, scripts/bin/smoke-workspace.sh |
| `learn.sh` | Capture a durable fact into cursor-bundle/memory + MEMORY.md in one command. | .cursor/hooks/stop-ship-nudge.sh, scripts/bin/test-learn.sh, scripts/bin/workspace-sanity.sh, scripts/testing/intelligence_hub.py, scripts/testing/learn_cli.py |
| `new-machine-setup.sh` | Bring this workspace up on a fresh Claude-enabled machine. | — |
| `novopay-logs.sh` | Local log discovery — agents never guess paths; use on stuck boot/batch/API. | scripts/bin/run-guarded.sh, scripts/bin/workspace-disk-clean.sh, scripts/lib/agent-ops-lib.sh, scripts/lib/novopay-logs-lib.sh, scripts/testing/ntest.py |
| `novopay-service.sh` | Local Novopay microservice lifecycle — stop stale processes, compile, bootRun, wait for pr | scripts/bin/assert-build-current.sh, scripts/bin/foreclosure-local-setup.sh, scripts/bin/stack-doctor.sh, scripts/lib/agent-ops-lib.sh, scripts/lib/infer_ship_apis.py, scripts/lib/kg_ship_resolve.py, scripts/lib/novopay-service-lib.sh, scripts/lib/ship_change_scope.py |
| `ntest.sh` | Canonical ntest entry (SU-STITCH-001): always prefer scripts/bin/ntest.sh over | scripts/bin/accounting-flow-proof.sh, scripts/bin/flow-onboard.sh, scripts/bin/ship-loop-gate.sh, scripts/bin/workspace-smoke.sh, scripts/lib/pipeline_chain_audit.py, scripts/lib/ship_test_plan.py, scripts/testing/agent_router.py, scripts/testing/flow_scaffold.py |
| `open-final.sh` | Resolve workspace path(s) for a forwardable final file. | — |
| `ops-bin-hygiene.sh` | Fail if a NEW scripts/bin/*.sh has zero references (pre-U5 orphans grandfathered). | scripts/bin/ship-loop-gate.sh |
| `pending-ship-gc.sh` | Drop clean+pushed zombie paths from .pending-ship-work.json | scripts/bin/stack-doctor.sh |
| `platform-scan.sh` | Parallel platform scan — map + contracts + chains in one pass. | scripts/bin/intel-automation.sh, scripts/testing/agent_router.py, scripts/testing/intelligence_hub.py |
| `pr-review.sh` | Read-only GitHub PR evidence collector. Never checks out, comments, or mutates a PR. | scripts/lib/pr_review_gate.py, scripts/testing/agent_router.py |
| `purge-local-dpi.sh` | Wipe all local DPI accruals/dues/GL txns + drop agent backup tables. Local only. | — |
| `push-origin.sh` | Push to origin after ship-loop gate (auto workspace-close if pending). | .cursor/hooks/pre-push-checklist.sh, scripts/lib/harness_audit.py, scripts/lib/infer_ship_apis.py, scripts/lib/pipeline_chain_audit.py, scripts/lib/ship_push_gate.py, scripts/testing/workspace_autopilot.py |
| `query-index-perf-audit.sh` | Index + EXPLAIN audit for native @Query / batch reader SQL profiles. | — |
| `query-plan-gate.sh` | Query plan gate — DETECT query_touched → EXPLAIN local YB → PASS/WARN/FAIL. | scripts/bin/ship-loop-gate.sh, scripts/lib/impact_tests.py, scripts/lib/test_harness_audit.py, scripts/lib/test_query_plan_gate.py |
| `route-ledger.sh` | Route ledger — where the current task is, and whether it reached its terminal state. | scripts/testing/workspace_autopilot.py |
| `run-guarded.sh` | Global watchdog wrapper for ship-chain steps — per-step budget + heartbeats. | scripts/bin/ship-loop-gate.sh, scripts/lib/pipeline_chain_audit.py |
| `schema-sync.sh` | Refresh the schema oracle: structure (local DB) → code binding (Java) → train labels (Flyw | scripts/bin/new-machine-setup.sh, scripts/lib/column_binding.py |
| `setup-local.sh` | One-time / periodic local workspace check for sliProd. | scripts/bin/initial-setup-local.sh, scripts/bin/workspace-doctor.sh |
| `setup-qa-db.sh` | Bootstrap / preflight QA DB env profiles (qa1–qa5). | — |
| `ship-discipline.sh` | Ship discipline — write or check machine gate for money/service ships. | scripts/lib/ship_discipline_gate.py |
| `ship-knowledge-gate.sh` | Verify post-ship knowledge closure — run before declaring a money-path fix "done". | scripts/bin/ship-loop-gate.sh, scripts/bin/workspace-close.sh, scripts/lib/infer_ship_apis.py, scripts/lib/pipeline_chain_audit.py, scripts/lib/registry_companion_gate.py, scripts/testing/agent_router.py |
| `ship-loop-gate.sh` | Tiered ship loop: workspace validate / service build+health / money full ntest. | scripts/bin/enrichment-audit.sh, scripts/bin/run-guarded.sh, scripts/bin/workspace-close.sh, scripts/lib/harness_audit.py, scripts/lib/infer_ship_apis.py, scripts/lib/pipeline_chain_audit.py, scripts/lib/test_harness_audit.py |
| `ship-test-auto.sh` | Auto-run ship tests for pending work (impact + deep). Agents/hooks only — not for users. | .cursor/hooks/post-commit-ship-test.sh |
| `smoke-workspace.sh` | End-to-end smoke test: cursor-bundle KG (SQLite), self-learning, hooks, local DB. | scripts/bin/workspace-doctor.sh, scripts/bin/workspace-sanity.sh, scripts/lib/harness_audit.py |
| `stack-doctor.sh` | Stack preflight for ship/test chain — hygiene before any ntest or ship-loop run. | scripts/bin/ship-loop-gate.sh, scripts/bin/workspace-close.sh, scripts/lib/pipeline_chain_audit.py |
| `super-agent.sh` | Super agent — unified KG + test KG + skills orchestrator. | .cursor/hooks/intel-session-sync.sh, scripts/bin/capture-flow.sh, scripts/bin/intel-automation.sh, scripts/bin/ship-knowledge-gate.sh, scripts/bin/super-machine-smoke.sh, scripts/bin/super-machine.sh, scripts/bin/sync-branches.sh, scripts/bin/workspace-close.sh |
| `super-machine-smoke.sh` | Super machine smoke — verify all integration points (no assumptions). | — |
| `super-machine.sh` | Super machine — single entry for the full intelligence stack. | scripts/bin/super-machine-smoke.sh, scripts/testing/corroborate.py |
| `sync-branches.sh` | Multi-repo branch sync — upstream (trusttai) + origin (fork), KG-aware. | scripts/bin/kg-align.sh, scripts/bin/new-machine-setup.sh, scripts/lib/train_banner.py, scripts/lib/train_sync.py, sync_branches_v2.sh |
| `sync-intelligence.sh` | Master intelligence sync — contracts + chains + footprints + FTG + KG gates. | scripts/bin/sync-test-intelligence.sh, scripts/testing/agent_router.py, scripts/testing/sync_engine.py |
| `sync-test-intelligence.sh` | Test intelligence sync — fingerprint-gated (fast default). | scripts/bin/sync-intelligence.sh, scripts/bin/test-map.sh, scripts/testing/corroborate.py, scripts/testing/cross_learn.py, scripts/testing/flow_scaffold.py, scripts/testing/flow_trace.py, scripts/testing/intelligence_hub.py, scripts/testing/sync_engine.py |
| `test-learn.sh` | Capture generic test/flow knowledge for future ntest runs (self-learning). | scripts/bin/workspace-sanity.sh, scripts/testing/intelligence_hub.py, scripts/testing/learn_cli.py |
| `test-map.sh` | Alias kept for muscle-memory: test-map.sh → sync-test-intelligence.sh | scripts/bin/sync-test-intelligence.sh |
| `train-upstream-sync.sh` | Ensure local/origin train tip is not behind upstream before mainline push. | scripts/bin/push-origin.sh |
| `workspace-autopilot.sh` | Workspace autopilot — zero manual ops for agents. | .cursor/hooks/post-ntest-intel-sync.sh, .cursor/hooks/stop-ship-nudge.sh, .cursor/hooks/workspace-autopilot-session.sh, scripts/bin/super-machine-smoke.sh, scripts/lib/infer_ship_apis.py, scripts/testing/corroborate.py, scripts/testing/workspace_autopilot.py |
| `workspace-bootstrap.sh` | Compatibility entry — prefer workspace-verify / workspace-doctor. | — |
| `workspace-close.sh` | Single task-close entry: fresh KG → ship-loop → sync → knowledge gate → hygiene. | .cursor/hooks/pre-push-checklist.sh, scripts/bin/push-origin.sh, scripts/bin/workspace-smoke.sh, scripts/lib/harness_audit.py, scripts/lib/infer_ship_apis.py, scripts/lib/pending_ship_gc.py, scripts/lib/pipeline_chain_audit.py, scripts/lib/register_pending_ship.py |
| `workspace-disk-clean.sh` | Smart disk cleanup for sliProd — service archived logs, scratch, pycache, large ops logs. | scripts/bin/workspace-max-pass.sh, scripts/testing/super_agent.py, scripts/testing/workspace_autopilot.py |
| `workspace-doctor.sh` | Unified workspace health — KG, hooks, DB, registry, optional services. | scripts/bin/new-machine-setup.sh, scripts/bin/workspace-bootstrap.sh, scripts/bin/workspace-sanity.sh, scripts/lib/harness_audit.py |
| `workspace-health.sh` | Fast workspace health (~1–3s) — no ntest, no workspace-close, no full KG rebuild. | scripts/bin/super-machine-smoke.sh, scripts/bin/workspace-max-pass.sh, scripts/testing/workspace_autopilot.py |
| `workspace-hygiene.sh` | Workspace clutter audit + optional cleanup. | scripts/bin/ship-knowledge-gate.sh, scripts/bin/ship-loop-gate.sh, scripts/bin/smoke-workspace.sh, scripts/bin/workspace-close.sh, scripts/bin/workspace-disk-clean.sh, scripts/bin/workspace-doctor.sh, scripts/bin/workspace-max-pass.sh, scripts/bin/workspace-smoke.sh |
| `workspace-max-pass.sh` | Workspace self-improvement pass — drain safe perf fixes + quick smoke (no full KG rebuild) | scripts/bin/super-machine-smoke.sh, scripts/bin/workspace-health.sh, scripts/bin/workspace-verify.sh, scripts/testing/workspace_autopilot.py |
| `workspace-sanity.sh` | Workspace sanity — proof-backed health of intelligence stack + core tools. | scripts/bin/intel-automation.sh, scripts/bin/smoke-workspace.sh, scripts/testing/intelligence_hub.py |
| `workspace-smoke.sh` | Workspace smoke — verify KG, hooks, registry, ship gates, hygiene, optional quick ntest. | scripts/bin/super-machine.sh, scripts/bin/workspace-max-pass.sh, scripts/lib/harness_audit.py |
| `workspace-verify.sh` | Back-compat entrypoint: older rules/tools call `workspace-verify.sh`. | scripts/bin/install-user-claude-gates.sh, scripts/bin/workspace-bootstrap.sh |
| `write-intelligence-hub.sh` | Regenerate session intelligence hub (--fast skips slow kg subprocess). | scripts/bin/ship-knowledge-gate.sh, scripts/bin/smoke-workspace.sh, scripts/bin/sync-intelligence.sh, scripts/bin/sync-test-intelligence.sh, scripts/bin/workspace-close.sh, scripts/bin/workspace-sanity.sh, scripts/testing/agent_router.py, scripts/testing/workspace_autopilot.py |

_Generated 105 entries._

