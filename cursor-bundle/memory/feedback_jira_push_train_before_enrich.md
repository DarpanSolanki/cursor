---
name: feedback_jira_push_train_before_enrich
description: >-
  QA handoff must wait until the fix is on origin/<reported-train>
  (e.g. mfi_integration_v3.5.2.2), not only origin/fix/*. TDPQA-207 2026-07-29.
---

# Push reported train to origin before JIRA enrich

## Failure mode (TDPQA-207)

Agent confirmed “pushed” after `origin/fix/tdpqa-207-foreclosure-by-latest` only.
Ticket train was **`mfi_integration_v3.5.2.2`**. That branch did **not** exist on origin —
fix was absent from the train QA builds from. JIRA was enriched / moved to QA:Test too early.

## Standing rule

1. Resolve **reported train** from ticket / user (integration branch name).
2. `git fetch origin` + prove tip of **`origin/<train>`** includes the fix commit.
3. If missing: base on `upstream/<train>` → cherry-pick/rebase → **`git push -u origin <train>`** (never upstream).
4. **Only then** run `jira-enrich` / QA Test transition.

`origin/fix/…` is WIP only. Do not say “code is pushed for QA” until the train branch is on origin.

Skill: `.cursor/skills/jira-fix-update/SKILL.md` (§ Push gate)  
Rule: `.cursor/rules/jira-tdpqa-qa-test-fields.mdc`
