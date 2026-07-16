# Cursor Rules Inventory (classification + intent)

**2026-07-02**: **`batch-write-skip-contract.mdc`** added — `force_async` write-skip: Future resolve only in `GenericListenerV3`; Vo DPI mappers must not duplicate unwrap; gate `audit-batch-skip-mappers.sh` in ship-loop.

**2026-06-25**: **`hot-path-perf-gate.mdc`** added — workspace-wide perf (processors, services, consumers, APIs), not batch-only. Automation: `scripts/bin/hot-path-scan.sh` + autopilot FIX+SHIP / ship-loop money tier.

**2026-04-11 refresh**: rules consolidated. Core **`alwaysApply: true`**: `always-on.mdc`, `discuss-before-updating.mdc`, `minimal-fix-impact-gate.mdc`, `hot-path-perf-gate.mdc`, plus workspace ops rules (`internal-api-local-test-harness`, `workspace-developer-tester`, …); domain rules load via **globs**.

Classification meaning:
- **Strong**: clear, complete, low ambiguity; keep as-is (maybe minor wording only).
- **Useful but incomplete**: correct direction but missing a few code-verified constraints; refine over time.

## Inventory

| Rule file | alwaysApply | Globs (summary) | Classification | Summary |
|---|---|---|---|---|
| `.cursor/rules/always-on.mdc` | true | — | Strong | **Session bootstrap first** (onboarding → gaps-and-risks High → architecture) before logs/search/code reads; **prompt self-expansion** + user confirm before investigation tools **or** edits on money/incidents/contracts/multi-service; narrow exceptions; `system_brain` map; RCA; `system_brain` maintenance. |
| `.cursor/rules/hot-path-perf-gate.mdc` | true | `**/*.java`, orchestration XML | Strong | Workspace-wide hot-path perf — N+1, precompute-before-loop; `hot-path-scan.sh` on autopilot + money ship-loop. |
| `.cursor/rules/batch-hot-path-perf.mdc` | false | batch services/processors/readers/writers | Strong | Batch precedents; defers to `hot-path-perf-gate.mdc` for always-on gate. |
| `.cursor/rules/minimal-fix-impact-gate.mdc` | true | — | Strong | Minimal write-path first; significant perf + hot-path scan in ship note. |
| `.cursor/rules/accounting.mdc` | false | `novopay-platform-accounting-v2/**` | Strong | Active intelligence + knowledge sync + financial preflight/signoff + full module reference (~4.9k lines). |
| `.cursor/rules/architect-thinking.mdc` | false | `**/*.{java,xml,gradle}` | Strong | Architect mindset, framework internals, tiered solutions, bank/DB/finance patterns, repository no-comments. |
| `.cursor/rules/local-dev-workflows.mdc` | false | `scripts/**`, `docs/disbursement-sanity/**` | Strong | Local DB investigation, MFI reset scripts, disburseLoan replay reset. |
| `.cursor/rules/git-workflow.mdc` | false | `sync_branches_v2.sh`, Gradle roots | Strong | Commit hygiene, fork/upstream PRs, sync-branch phrase. |
| `.cursor/rules/events.mdc` | false | MessageBroker, Kafka consumer/producer | Strong | Event registry hygiene + merged Kafka consumer patterns (incl. disbursement sync contract). |
| `.cursor/rules/docs-outside-service-repos.mdc` | false | `docs/**/*` | Strong | Docs live under workspace `docs/`; merged workspace `docs/` maintenance section. |
| `.cursor/rules/multi-path-state-persistence-safety.mdc` | false | `**/*.{java,xml}` | Strong | General multi-path persistence + disbursement queue vs embedded JSON checklist. |
| `.cursor/rules/platform-lib.mdc` | false | `novopay-platform-lib/**` | Strong | Framework blast radius and global injections. |
| `.cursor/rules/batch.mdc` | false | batch service + Batch/* beans | Strong | Multinode batch themes, scheduler registry, idempotency. |
| `.cursor/rules/los.mdc` | false | `novopay-mfi-los/**` | Strong | Disburse originator, sync/`entity_type`, Redis. |
| `.cursor/rules/payments.mdc` | false | `novopay-platform-payments/**` | Strong | Collections hub, contracts with accounting. |
| `.cursor/rules/gateway.mdc` | false | `novopay-platform-api-gateway/**` | Strong | Ingress / GAP-054..060 hot zones. |
| `.cursor/rules/execution-context-discipline.mdc` | false | `**/*.{java,xml}` | Strong | `put` vs `putLocal`, key safety. |
| `.cursor/rules/no-flow-break-impact-check.mdc` | false | `**/*.{java,xml}` | Strong | Mandatory impact analysis; production lessons. |
| `.cursor/rules/api-contract-safety.mdc` | false | `**/*.{java,xml}` | Useful but incomplete | Additive-only API/Kafka contracts. |
| `.cursor/rules/multi-agent-spawning.mdc` | false | `**/*.{md,java}` | Strong | When to parallelize agents; money stays single-owner. |
| `.cursor/rules/disburse-loan-sanity-suite.mdc` | false | sanity scripts + reports | Useful but incomplete | Local disburseLoan sanity commands and log path. |
| `.cursor/rules/effective-prompts-and-issue-triage.mdc` | false | `.cursorrules`, `AGENTS.md`, `**/*.md` | Strong | Rich prompts; thin-prompt triage. |
| `.cursor/rules/internal-api-local-test-harness.mdc` | true | — | Strong | Internal-only APIs: local JTF templates + ntest flow for gateway tests; do not push to service/cursor remotes. |
| `.cursor/rules/workspace-developer-tester.mdc` | true | — | Strong | Unified dev+test loop: KG orient → `ntest` registry → fix → smoke; one row per API in `registry.json`. |
| `.cursor/rules/workspace-contract.mdc` | true | — | Strong | Once-and-for-all contract; machine gates not daily re-setup; ship-discipline fail-closed. |

## Maintainer note

When adding or removing `.cursor/rules/*.mdc` files, update this table. **`hot-path-perf-gate.mdc`** is intentionally **always-on** (workspace-wide perf, not batch globs only).
