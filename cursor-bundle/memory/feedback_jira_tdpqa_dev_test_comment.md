---
name: feedback_jira_tdpqa_dev_test_comment
description: >-
  TDPQA has no Dev Test custom field — always pack `dev[]` and post companion
  comment headed Dev Test Details (2026-07-29 TDPQA-192 correction).
---

# TDPQA Dev Test Details = companion comment (2026-07-29)

## Problem

TDPQA Bug mandatory fields cover RCA / Impact / PrePost / AITDP only.
There is **no** Dev Test Details field (SDCP has `customfield_11901`).
Leaving only a short ping → QA cannot see developer retest steps.

## Rule

1. `tdpqa_field_handoff` pack **requires** `dev[]` (fail closed).
2. Helper posts companion comment: lead-in (`ping_comment`) + **Dev Test Details**
   (ordered list) + optional **How to retest** (`qa_retest`).
3. Do **not** invent an SDCP ticket to host Dev Test.
4. Functional language only — same forbidden-token scan as fields.

## Machine

`scripts/bin/jira-fix-adf.py` → `tdpqa_dev_test_comment_doc` + pack require.
Tests: `scripts/lib/test_jira_fix_adf.py` (`test_tdpqa_pack_requires_dev`).

Skill / rule: `jira-fix-update` + `.cursor/rules/jira-tdpqa-qa-test-fields.mdc`.
Triggered by TDPQA-192 missing Dev Test after field enrich.
