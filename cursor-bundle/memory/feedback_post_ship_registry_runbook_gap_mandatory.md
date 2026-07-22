# Post-ship: registry + runbook + gap MUST ship with money fix

**Standing (user escalated multiple times — 2026-07-15 A2+B DCF was the triggering miss).**

## What went wrong

Accounting fix `5b1b928ed` + workspace changelog/e2e scripts shipped (`7d22003`), but **post-ship knowledge DoD was incomplete**:

| Artifact | Status at ship |
|----------|----------------|
| brain CHANGELOG kg-flow | Present |
| `.cursor/changelog.md` | Present |
| KG cases | Present after enrich |
| **`scripts/testing/registry.json` note/expects for new asserts** | **Excluded** (dirty unrelated WIP) — e2e Python had A2 EXTRA + B labd asserts, registry still described only closure/PRIN |
| **Runbook `sdcp-10199-…` A2/B section** | Missing |
| **Gaps RESOLVED (GAP-075)** | Missing |
| Flow / edge / scenarios A2+B fields | Partial / missing |

**Honest root cause:** agents treated `compile + changelog-add + push code` as done. Gate scripts only enforced changelog pending / kg-flow presence — **not** companion testing-suite + runbook + gaps.

## Mandatory companion set (money fix with new behaviour / asserts)

Same ship window as the service commit (workspace commit OK if same task turn):

1. **Registry / ntest** — `scripts/testing/registry.json` case note (and defaults) must name the **strong path** asserts (not a stale closure-only blurb). Surgical edit if file has unrelated WIP — never leave the money case stale.
2. **Runbook** — symptom → fix SHA → retest command (`ntest run …`).
3. **Gaps** — RESOLVED row (+ GAP narrative) or explicit “no new gap / already tracked”.
4. Brain CHANGELOG kg-flow + `.cursor/changelog.md` (existing gate).
5. Edge / scenarios / flow one-liner when behaviour differs.

**Compile / changelog alone is NOT DoD.** User will ask “was KG and docs/scripts/testing updated?” — answer must be yes with evidence.

## Automation

- Rule: `.cursor/rules/20-ship-gates.mdc` rows 9–11 (registry, runbook, gaps).
- `scripts/bin/ship-knowledge-gate.sh --full` WARNs when top kg-flow mentions DeathForeclosure / DCF and companions lack EXTRA/labd or registry note lag.
- Memory index: this file.

## Pair with

`feedback_keep_knowledge_current.md`, `20-ship-gates.mdc`, `30-kg-discipline.mdc`, `20-ship-gates.mdc`.
