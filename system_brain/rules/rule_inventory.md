# Cursor Rules Inventory (classification + intent)

**2026-07-19**: **`prod-ops-sql-impact-gate.mdc`** + skill `prod-ops-sql-impact` — prod/adhoc money SQL must impact-analyze CRR status/LAN callers; prefer `LOCAL_RESET_ARCHIVED` + `~` soft-archive; no invented status literals.

**2026-07-20**: **`00-workspace-core.mdc`** flipped to **path-only default** (no auto IDE open); `--open` / `OPEN_FINAL=1` / explicit user ask only. Memory: `feedback_no_auto_open_documents.md`.
**2026-07-19**: **`00-workspace-core.mdc`** + skill `open-final-file` — originally preferred IDE final buffer; later default flipped to path-only (see 2026-07-20).

**2026-07-15**: **`00-workspace-core.mdc`** + **`ship_discipline_gate.py`** — once-and-for-all; soft rules failed; fail-closed minimal-fix/hot-path/verify_mode/KG/assumptions. Path-absolute smoke/enrichment.

**2026-07-15**: **`20-ship-gates.mdc`** — prefer realtime ntest; if stage blocked enrich registry with orch sibling / processor mirror sims (never guesses).

**2026-07-02**: **`batch-write-skip-contract.mdc`** added — `force_async` write-skip: Future resolve only in `GenericListenerV3`; Vo DPI mappers must not duplicate unwrap; gate `audit-batch-skip-mappers.sh` in ship-loop.

**2026-06-25**: **`10-quality-gates.mdc`** added — workspace-wide perf (processors, services, consumers, APIs), not batch-only. Automation: `scripts/bin/hot-path-scan.sh` + autopilot FIX+SHIP / ship-loop money tier.

**2026-04-11 refresh**: rules consolidated. Core **`alwaysApply: true`**: `00-workspace-core.mdc`, `10-quality-gates.mdc`, `10-quality-gates.mdc`, `10-quality-gates.mdc`, plus workspace ops rules (`internal-api-local-test-harness`, `workspace-developer-tester`, …); domain rules load via **globs**.

Classification meaning:
- **Strong**: clear, complete, low ambiguity; keep as-is (maybe minor wording only).
- **Useful but incomplete**: correct direction but missing a few code-verified constraints; refine over time.

## Inventory

| Rule file | alwaysApply | Globs (summary) | Classification | Summary |
|---|---|---|---|---|
| `.cursor/rules/00-workspace-core.mdc` | true | — | Strong | **Session bootstrap first** (onboarding → gaps-and-risks-**digest** → architecture-**digest**; escalate to full SoT) before logs/search/code reads; **prompt self-expansion** + user confirm before investigation tools **or** edits on money/incidents/contracts/multi-service; narrow exceptions; `system_brain` map; RCA; `system_brain` maintenance. |
| `.cursor/rules/00-workspace-core.mdc` | true | — | Strong | Forwardable files → print path only; IDE open only if user asks (`--open` / `open_resource`); Review `#changes` = diff only. |
| `.cursor/rules/prod-ops-sql-impact-gate.mdc` | false | `scripts/sql/{adhoc,deploy,setup}/**` | Strong | Prod/ops money SQL: caller matrix for status/LAN; proven soft-archive only; no invented CRR status. |
| `.cursor/rules/10-quality-gates.mdc` | true | `**/*.java`, orchestration XML | Strong | Workspace-wide hot-path perf — N+1, precompute-before-loop; `hot-path-scan.sh` on autopilot + money ship-loop. |
| `.cursor/rules/batch-hot-path-perf.mdc` | false | batch services/processors/readers/writers | Strong | Batch precedents; defers to `10-quality-gates.mdc` for always-on gate. |
| `.cursor/rules/10-quality-gates.mdc` | true | — | Strong | Minimal write-path first; significant perf + hot-path scan in ship note. |
| `.cursor/rules/accounting.mdc` | false | `trustt-platform-accounting/**` | Strong | Thin gates + routing (≤6KB). Deep knowledge: `.cursor/skills/accounting-knowledge/`. Former `accounting-module-knowledge.mdc` deleted (relocated). |
| `.cursor/rules/architect-thinking.mdc` | false | `**/*.{java,xml,gradle}` | Strong | Thin tiered-solutions + repository policy + routing (≤4KB). Deep: `.cursor/skills/architect-thinking/`. |
| `.cursor/rules/local-dev-workflows.mdc` | false | `scripts/**`, `docs/disbursement-sanity/**` | Strong | Local DB investigation, MFI reset scripts, disburseLoan replay reset. |
| `.cursor/rules/git-workflow.mdc` | false | `scripts/bin/sync-branches.sh`, `sync_branches_v2.sh` (deprecated wrapper), Gradle roots | Strong | Commit hygiene, fork/upstream PRs, sync-branch phrase. |
| `.cursor/rules/events.mdc` | false | MessageBroker, Kafka consumer/producer | Strong | Event registry hygiene + merged Kafka consumer patterns (incl. disbursement sync contract). |
| `.cursor/rules/docs-outside-service-repos.mdc` | false | `docs/**/*` | Strong | Docs live under workspace `docs/`; merged workspace `docs/` maintenance section. |
| `.cursor/rules/multi-path-state-persistence-safety.mdc` | false | `**/*.{java,xml}` | Strong | General multi-path persistence + disbursement queue vs embedded JSON checklist. |
| `.cursor/rules/platform-lib.mdc` | false | `trustt-platform-lib/**` | Strong | Framework blast radius and global injections. |
| `.cursor/rules/batch.mdc` | false | batch service + Batch/* beans | Strong | Multinode batch themes, scheduler registry, idempotency. |
| `.cursor/rules/los.mdc` | false | `trustt-platform-los/**` | Strong | Disburse originator, sync/`entity_type`, Redis. |
| `.cursor/rules/payments.mdc` | false | `trustt-platform-payments/**` | Strong | Collections hub, contracts with accounting. |
| `.cursor/rules/gateway.mdc` | false | `trustt-platform-api-gateway/**` | Strong | Ingress / GAP-054..060 hot zones. |
| `.cursor/rules/execution-context-discipline.mdc` | false | `**/*.{java,xml}` | Strong | `put` vs `putLocal`, key safety. |
| `.cursor/rules/no-flow-break-impact-check.mdc` | false | `**/*.{java,xml}` | Strong | Mandatory impact analysis; production lessons. |
| `.cursor/rules/api-contract-safety.mdc` | false | `**/*.{java,xml}` | Useful but incomplete | Additive-only API/Kafka contracts. |
| `.cursor/rules/multi-agent-spawning.mdc` | false | `**/*.{md,java}` | Strong | When to parallelize agents; money stays single-owner. |
| `.cursor/rules/disburse-loan-sanity-suite.mdc` | false | sanity scripts + reports | Useful but incomplete | Local disburseLoan sanity commands and log path. |
| `.cursor/rules/effective-prompts-and-issue-triage.mdc` | false | `.cursorrules`, `AGENTS.md`, `**/*.md` | Strong | Rich prompts; thin-prompt triage. |
| `.cursor/rules/20-ship-gates.mdc` | true | — | Strong | Internal-only APIs: local JTF templates + ntest flow for gateway tests; do not push to service/cursor remotes. |
| `.cursor/rules/00-workspace-core.mdc` | true | — | Strong | Unified dev+test loop: KG orient → `ntest` registry → fix → smoke; one row per API in `registry.json`. |
| `.cursor/rules/20-ship-gates.mdc` | true | — | Strong | Prefer realtime; when stage blocked use orch sibling / processor mirror sims from disk; enrich platform registry. |
| `.cursor/rules/00-workspace-core.mdc` | true | — | Strong | Once-and-for-all contract; machine gates not daily re-setup; ship-discipline fail-closed. |

## Maintainer note

When adding or removing `.cursor/rules/*.mdc` files, update this table. **`10-quality-gates.mdc`** is intentionally **always-on** (workspace-wide perf, not batch globs only).


## Upgrade 3 (2026-07-22) — alwaysApply consolidation

Former 28 alwaysApply `.mdc` files → thematic:
- `00-workspace-core.mdc`, `10-quality-gates.mdc`, `20-ship-gates.mdc`, `30-kg-discipline.mdc`, `darpan.mdc` (standalone)
- Verbatim archives: `.cursor/skills/workspace-gates-reference/`
- Mapping: `scripts/scratch/upgrade3-mapping.md`
