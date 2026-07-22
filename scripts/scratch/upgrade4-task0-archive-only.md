# Upgrade 4 / TASK 0 — archive-only mandate audit

Baseline: `scripts/scratch/mandate-checklist.txt` (153 lines).
Heuristic found **27** lines whose probe matched archives but not thematic alwaysApply text.

## Fixed into thematic rules (imperative one-liners)

| Source | Action |
|--------|--------|
| always-on RCA: Never jump straight to writing code / Do not guess / no unrelated refactor | Added to `00-workspace-core.mdc` expansion section |
| always-on: No deferred push / sync must remain current | Strengthened in `00` knowledge-sync |
| reuse-queries: do not widen WHERE / hot-path step-2 | Added to `10-quality-gates.mdc` |
| upstream: Hard stop conditions / push checklist | Added to `10-quality-gates.mdc` |
| ship-test: never bypass with raw git push | Added to `20-ship-gates.mdc` |
| post-ship: Mandatory checklist / Hard stop phrases | Added to `20-ship-gates.mdc` |
| enhancement: always present L0 + L1 | Strengthened in `20-ship-gates.mdc` |
| code-backed: cite exact DB writes | Already in `20` (kept) |

## Justified archive-only (safe — not load-bearing standalone)

| Kind | Examples | Why archive-only is safe |
|------|----------|---------------------------|
| Heading-only / section titles | `# Always-On…`, `## Do not`, `## Agent workflow` | Not imperatives; content under them already promoted or covered |
| Mid-sentence checklist fragments | partial “cite the exact” / “must read the” | Covered by fuller `20` sim ladder line |
| Precedent / example rows | TDPQA-102 childLoanReopening processor list | Historical example, not a standing gate |
| Explanatory table cells | Flyway pre vs post timing cell; NEFT stage bullet | Guidance already summarized in `20` Flyway / ship sections |
| Narrative API examples | internal-api foreclosure API names paragraph | Covered by `20` Internal API harness gate |
| Meta commentary | workspace-contract “hard exit codes were skipped” | Historical rationale; fail-closed gates listed in `00` contract |

**Count:** 27 flagged → **~12 fixed/strengthened** into thematic rules · **~15 justified archive-only**.
