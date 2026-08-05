# Rule index — sliProd

Ported from Cursor `.mdc` frontmatter. `alwaysApply` rules are @imported by `AGENTS.mdc`.
Glob-scoped rules attach via Cursor `globs:` frontmatter.

## Always-on (alwaysApply: true)

| Rule | Purpose |
|------|---------|
| [00-workspace-core](00-workspace-core.mdc) | Workspace core — bootstrap, autopilot, contract, ops, hygiene, open-final |
| [10-quality-gates](10-quality-gates.mdc) | Quality gates — discuss-before, minimal-fix, reuse-queries, hot-path, upstream-sync, gates A–E |
| [20-ship-gates](20-ship-gates.mdc) | Ship gates — ship-loop, ship-test, enrichment, post-ship, enhancement fronts, code-backed sim, internal-api, flyway |
| [30-kg-discipline](30-kg-discipline.mdc) | KG discipline — safety, self-learning, flow-cross-learn, DPI branch gate |
| [40-knowledge-upkeep](40-knowledge-upkeep.mdc) | Knowledge upkeep — every change updates KG, testing suite and reference docs |
| [darpan](darpan.mdc) | Trustt LMS pinpoint-RCA discipline — cursor-bundle brain, KG, db-tools, memory (sliProd) |
| [run-the-real-thing-locally](run-the-real-thing-locally.mdc) | Real local flow over sim-only for money evidence |
| [agent-parallelism-and-token-budget](agent-parallelism-and-token-budget.mdc) | Parallel agents as exception; token budget |
| [upstream-mainline-push-sync](upstream-mainline-push-sync.mdc) | Before push to origin on mfi_integration/mfi_release mainline — fetch upstream, sync tip, never push stale origin-behind-upstream |

## Path-scoped (globs frontmatter)

| Rule | Applies to | Purpose |
|------|-----------|---------|
| [accounting-full-flow-gate](accounting-full-flow-gate.mdc) | `trustt-platform-accounting/**`<br>`scripts/accounting/**`<br>`scripts/dpic/**`<br>`scripts/disbursement/**`<br>`scripts/testing/registry.json` | Accounting module — ALL flow domains (read, write, batch, money); not money-only |
| [accounting](accounting.mdc) | `**/trustt-platform-accounting/**/*.java`<br>`**/trustt-platform-accounting/**/*.xml` | Accounting module — financial gates + routing to on-demand accounting-knowledge skill |
| [api-contract-safety](api-contract-safety.mdc) | `**/*.java`<br>`**/*.xml` | API contract safety — backward compatibility, additive changes, response semantics, cross-module impact |
| [architect-thinking](architect-thinking.mdc) | `**/*.java`<br>`**/*.xml`<br>`**/*.gradle`<br>`**/*.gradle.kts` | Architect thinking — tiered solutions, repository comment policy, routing to on-demand skill |
| [batch-hot-path-perf](batch-hot-path-perf.mdc) | `**/batchnew/**/*.java`<br>`**/*BatchService.java`<br>`**/*ItemProcessor.java`<br>`**/*ItemReader.java`<br>`**/*ItemWriter.java` | Batch inner-loop perf — precedents; workspace gate: 10-quality-gates.md (always-on) |
| [batch-write-skip-contract](batch-write-skip-contract.mdc) | `**/GenericListenerV3.java`<br>`**/*FailureEntityMapper.java` | Batch write-skip contract — platform Future resolve vs job mapper responsibilities (force_async) |
| [batch](batch.mdc) | `**/trustt-platform-batch/**/*.java`<br>`**/*BatchConfig*.java`<br>`**/*JobConfig*.java`<br>`**/*Tasklet*.java`<br>`**/*Writer*.java`<br>`**/*Reader*.java`<br>`**/*Processor*.java` | Auto-loads when editing batch service or batch-shaped Spring Batch artifacts |
| [death-foreclosure-sanity-suite](death-foreclosure-sanity-suite.mdc) | `scripts/dcf_sanity.py`<br>`scripts/dcf_sanity/**`<br>`trustt-platform-accounting/**/deathforeclosure/**` | Death foreclosure local test harness and flow entrypoints |
| [debugging-production-issues](debugging-production-issues.mdc) | `**/*.java`<br>`**/*.xml` | Systematic debugging of production issues — evidence-based RCA, adversarial self-review, and manual verification plans. |
| [disburse-loan-sanity-suite](disburse-loan-sanity-suite.mdc) | `scripts/disburse_loan_sanity.py`<br>`scripts/disbursement/payloads/canonical/*.json`<br>`scripts/bin/disburse-quick.sh`<br>`scripts/bin/disburse-shg-quick.sh`<br>`docs/disbursement-sanity/**`<br>`docs/disbursement-reset-recipes/**`<br>`scripts/sql/reset/local_reset_disburse_loan_replay_mfi_yugabyte.sql`<br>`scripts/sql/reset/reset_disburse_loan_replay_mfi_from_json.py` | Run evidence-driven disburseLoan sanity (simulator+DB) |
| [disbursement-testing-playbook](disbursement-testing-playbook.mdc) | `scripts/disburse_loan_sanity.py`<br>`scripts/disburse_loan_sanity_*.json`<br>`docs/disbursement-sanity/**` | Disbursement testing playbook with simulator + CRR proof |
| [docs-outside-service-repos](docs-outside-service-repos.mdc) | `docs/**/*` | Workspace docs/ placement; editorial standards for docs outside service repos |
| [dpi-money-proof-gate](dpi-money-proof-gate.mdc) | `scripts/dpic/**`<br>`scripts/bin/dpi-*.sh`<br>`scripts/testing/registry.json` | DPI money path — mandatory SQL proof chain before ship or QA hand-off |
| [effective-prompts-and-issue-triage](effective-prompts-and-issue-triage.mdc) | `AGENTS.mdc`<br>`AGENTS.mdc`<br>`**/*.md` | How users should frame fix requests; how agents interpret thin prompts and triage before acting. |
| [events](events.mdc) | `**/MessageBroker*.xml`<br>`**/*Consumer*.java`<br>`**/*Producer*.java`<br>`**/*KafkaConfig*.java`<br>`**/*MessageBroker*.java` | Kafka/events hygiene, consumer patterns, idempotency, disbursement sync contract |
| [execution-context-discipline](execution-context-discipline.mdc) | `**/*.java`<br>`**/*.xml` | ExecutionContext discipline — the #1 source of runtime bugs; key management, null safety, scope control |
| [gateway](gateway.mdc) | `**/trustt-platform-api-gateway/**/*.java`<br>`**/trustt-platform-api-gateway/**/*.xml` | Auto-loads when editing trustt-platform-api-gateway |
| [git-workflow](git-workflow.mdc) | `scripts/bin/sync-branches.sh`<br>`sync_branches_v2.sh`<br>`**/build.gradle`<br>`**/build.gradle.kts`<br>`**/settings.gradle`<br>`**/settings.gradle.kts` | Git commit hygiene, fork/upstream PR workflow, multi-repo sync script phrase |
| [local-dev-workflows](local-dev-workflows.mdc) | `scripts/**`<br>`docs/disbursement-sanity/**` | Local DB investigation, MFI disburse reset scripts, disburseLoan replay reset (Yugabyte) |
| [los](los.mdc) | `**/trustt-platform-los/**/*.java`<br>`**/trustt-platform-los/**/*.xml` | Auto-loads when editing trustt-platform-los |
| [multi-agent-spawning](multi-agent-spawning.mdc) | `**/*.md`<br>`**/*.java` | When to spawn multiple agents for speed; how to partition work; when one agent is mandatory (money, contracts). |
| [multi-path-state-persistence-safety](multi-path-state-persistence-safety.mdc) | `**/*.java`<br>`**/*.xml` | Multi-path state persistence safety (general + disbursement queue/JSON layers) |
| [no-flow-break-impact-check](no-flow-break-impact-check.mdc) | `**/*.java`<br>`**/*.xml` | Non-negotiable impact analysis before any change — learned from production incidents |
| [payments](payments.mdc) | `**/trustt-platform-payments/**/*.java`<br>`**/trustt-platform-payments/**/*.xml` | Auto-loads when editing trustt-platform-payments |
| [platform-lib](platform-lib.mdc) | `**/trustt-platform-lib/**/*.java`<br>`**/trustt-platform-lib/**/*.xml` | Auto-loads when editing any file in trustt-platform-lib |
| [prod-ops-sql-impact-gate](prod-ops-sql-impact-gate.mdc) | `scripts/sql/adhoc/**`<br>`scripts/sql/deploy/**`<br>`scripts/sql/setup/**` | Prod/ops SQL impact gate — mandatory caller + status/column blast analysis before adhoc UPDATE scripts (CRR, loan_account money patches) |
| [repository-layer-no-comments](repository-layer-no-comments.mdc) | `**/src/main/java/**/repository/**/*.java` | No comments in persistence/repository layer — use knowledge docs or SQL |

## On-demand (invoke explicitly)

| Rule | Purpose |
|------|---------|
| [accounting-134207-placeholder-iad](accounting-134207-placeholder-iad.mdc) | Fix 134207 on postTransaction/disburseLoan — missing product_transaction_catalogue placeholder→IAD rows (PROC_FEE, GST, STAMP_DUTY_AMT) |
| [harness-push-origin-main-only](harness-push-origin-main-only.mdc) |  |
| [jira-tdpqa-qa-test-fields](jira-tdpqa-qa-test-fields.mdc) |  |
| [release-details](release-details.mdc) | Short release/QA hand-off when user asks for release details — RCA, impact, dev testing in plain language |
