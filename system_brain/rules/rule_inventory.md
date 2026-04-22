# Cursor Rules Inventory (classification + intent)

**2026-04-11 refresh**: rules consolidated to **20** files. Only **`always-on.mdc`** and **`discuss-before-updating.mdc`** use `alwaysApply: true`; all others load via **globs**.

Classification meaning:
- **Strong**: clear, complete, low ambiguity; keep as-is (maybe minor wording only).
- **Useful but incomplete**: correct direction but missing a few code-verified constraints; refine over time.

## Inventory

| Rule file | alwaysApply | Globs (summary) | Classification | Summary |
|---|---|---|---|---|
| `.cursor/rules/always-on.mdc` | true | — | Strong | **Session bootstrap first** (onboarding → gaps-and-risks High → architecture) before logs/search/code reads; **prompt self-expansion** + user confirm before investigation tools **or** edits on money/incidents/contracts/multi-service; narrow exceptions; `system_brain` map; RCA; `system_brain` maintenance. |
| `.cursor/rules/discuss-before-updating.mdc` | true | — | Strong | No code/config edits without explicit user approval. |
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

## Maintainer note

When adding or removing `.cursor/rules/*.mdc` files, update this table and keep **`alwaysApply: true` count at exactly 2** unless the workspace explicitly changes that policy.
