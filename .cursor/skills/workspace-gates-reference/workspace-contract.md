<!-- VERBATIM archive of former alwaysApply `.cursor/rules/workspace-contract.mdc`. Do not soften. Edit thematic rules; keep this as mandate proof. -->

# Workspace contract (once — do not re-litigate daily)

**User stance:** Setup is done. Agents **self-heal** via scripts. Do not ask Darpan to re-configure the workspace after each ticket.

## What is machine-enforced (fail closed)

| Gate | Script |
|------|--------|
| Autopilot classify + preflight | `workspace-autopilot.sh task "…"` |
| Ship test by tier | `ship-loop-gate.sh --from-pending` |
| Minimal fix · no guesses · hot-path · verify_mode · KG honest | `ship-discipline.sh` → `.cursor/.ship-discipline.json` |
| Reuse-query proof on any `*Repository/*DAOService` query change | `reuse_query_gate.py` (in `ship_discipline_gate`) → `.ship-discipline.json` `reuse_query` block |
| Real-flow value-level DB asserts on money ships | `acceptance_coverage.py` `db_asserts` vs `domain_money_tables` (manifest) — presence-only fails closed |
| Knowledge / KG enrichment | `ship-knowledge-gate.sh` + `enrichment-audit.sh` |
| Hooks | `.cursor/hooks.json` + `install-user-cursor-gates.sh` |
| Health / smoke / hygiene | `workspace-max-pass.sh` / `workspace-smoke.sh` |
| Multi-branch KG | `kg-switch.sh` / watermark LRU — never invent branch state |

## Agent laws (permanent)

1. **Minimal permanent fix** — one root-cause layer; no stacked guards; ops patch for poison rows.
2. **No assumptions** — every claim cites code/DB/API this turn; empty `assumptions: []` or `{claim, evidence}`.
3. **No overengineering** — mirror sibling orch/processor; reuse-queries step 1 first.
4. **Performance** — hot-path scan before money ship (`PASS`/`WARN`/`N/A` recorded in discipline).
5. **Test** — **real-flow only**: drive the actual orch/API/job and assert **exact column values** on every touched money table (not presence, not SQL-only, not status-200/COMPLETED) — `feedback_real_flow_db_write_validate.md`, machine gate `acceptance_coverage.py` db_asserts. If a stage is blocked → code-backed sim in registry (`verify_mode`), not invent expects, still citing expected writes. **QA acceptance is the bar, not a passing subset** — asserts must FAIL on the exact QA fail mode (amount==principal OR documented components; dedicated force-bill labd / no EMI hijack; parent scope Pass|Out-of-scope). Never mark RESOLVED/Pass when the assert allows the QA fail mode (`feedback_qa_acceptance_not_subset_verify.md`, agent-quality-gates Gate D-acceptance).
6. **KG** — money ship: changelog + enrich; discipline `kg_enrichment` = FULL|CASES|SKIP (honest).
7. **Parallel** — multi-repo/branch: sync train gate + mixed-train matrix; never cross-conclude from mismatched trains.

## Self-heal (agent runs — user never)

```bash
bash scripts/bin/workspace-max-pass.sh          # smoke + hygiene
bash scripts/bin/install-user-cursor-gates.sh   # hooks (once per machine)
bash scripts/bin/enrichment-sync.sh             # if CHANGELOG newer than kg.db
bash scripts/bin/ship-discipline.sh write ...   # before money close
```

## Broken soft-rule pattern (why gaps returned)

Rules without **hard exit codes** were skipped. Discipline gate + path-absolute smoke/enrichment close that hole. If something still drifts: **fix the gate**, do not add another alwaysApply essay.

Pairs: `code-backed-simulation-testing.mdc`, `minimal-fix-impact-gate.mdc`, `hot-path-perf-gate.mdc`, `ship-test-mandatory.mdc`, `post-ship-knowledge-gate.mdc`.
