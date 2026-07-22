# Agent guide — Novopay sliProd

Thin map (Upgrade 3). Load-bearing gates live in thematic alwaysApply rules.

## Always-on rules (thematic)

| File | Role |
|------|------|
| `.cursor/rules/00-workspace-core.mdc` | Bootstrap, autopilot, contract, ops, hygiene, open-final |
| `.cursor/rules/10-quality-gates.mdc` | Discuss-before, minimal-fix, reuse-queries, hot-path, upstream, gates A–E |
| `.cursor/rules/20-ship-gates.mdc` | Ship-loop, ship-test, enrichment, post-ship, sim, flyway, internal-api |
| `.cursor/rules/30-kg-discipline.mdc` | KG safety, self-learning, flow-cross-learn, DPI branch |
| `.cursor/rules/darpan.mdc` | Personal boundary / identity (standalone) |

Verbatim pre-merge bodies: `.cursor/skills/workspace-gates-reference/`. Mapping: `scripts/scratch/upgrade3-mapping.md`.

## How to ask for a fix

Symptom + error code + correlator (`external_ref_number`, LAN, `stan`) + env + service guess. Template: `effective-prompts-and-issue-triage.mdc`.

## Knowledge graph first

Money / Kafka / multi-service: `.cursor/knowledge-graph.md` → edge registry → `.cursor/cross-service-transactions.md` → gaps-digest (escalate to full `gaps-and-risks.md` when flagged) → code.

## Read first (by task)

1. Money → `system_brain/` flow + knowledge-graph + gaps-digest + `accounting.mdc` gates + `.cursor/skills/accounting-knowledge/`
2. Standards → thematic rules above + `.cursorrules` (self-knowledge + Java/XML)
3. Framework → `.cursor/index.mdc` / codegen paths
4. Verify in orch XML + processors + DB

## Multi-agent

Policy: `multi-agent-spawning.mdc`. Parallel read-only OK; serialize money writes.

## Git

Multi-repo: run `git` inside the correct `trustt-*` / `novopay-*` directory.
