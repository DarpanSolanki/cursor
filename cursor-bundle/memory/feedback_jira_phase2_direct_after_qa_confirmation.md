---
name: jira-phase2-direct-after-qa-confirmation
description: Once the agent has confirmed testing done and good-to-release-to-QA, enrich JIRA straight to phase 2 — mentions and transition included
metadata:
  type: feedback
---

Once the agent has confirmed testing done and good-to-release-to-QA, enrich JIRA straight to phase 2 — mentions and transition included

**Why:** Darpan 2026-08-06 on TDPQA-241. The two-phase split existed so nobody gets tagged on text he had not reviewed. When the agent has already certified the release in conversation — fix proven on `origin/<reported-train>`, red→green evidence cited, QA-release YES given — that review has happened. Holding a second approval gate after it is dead ceremony.

**How to apply:** verified QA-release YES → one pass: fields + Dev Test Details comment + real ADF mention nodes + transition toward QA Test. Any other enrich ask (draft, work in progress, no certification given) stays phase 1: fields and Dev Test Details only, no `ping_comment`, no mentions, no transition. Rule: `.cursor/rules/jira-tdpqa-qa-test-fields.md`; skill: `jira-fix-update` § Two-phase handoff.
