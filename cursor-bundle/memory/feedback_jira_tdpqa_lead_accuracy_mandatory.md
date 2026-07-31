---
name: feedback_jira_tdpqa_lead_accuracy_mandatory
description: >-
  TDPQA transition requires AiTDP Lead Accuracy (12004) + Lead Improvement
  Remarks (12005) in addition to Dev AITDP. 2026-07-31 TDPQA-227.
---

# TDPQA Lead Accuracy + Lead Improvement Remarks (STANDING)

## Incident

Transition failed popup: "Please add Lead Accuracy and AITDP Lead Improvement Remark"
on TDPQA-227 after Dev RCA/Impact/AITDP were already filled.

## Fields

| Display | Key | Write |
|---------|-----|-------|
| AiTDP Lead Accuracy (Number 0–100) | `customfield_12004` | whole percent (`85`) |
| AiTDP Lead Improvement Remarks | `customfield_12005` | ADF textarea |

## Enrich rule

Every TDPQA `tdpqa_field_handoff` pack **must** write `12004` + `12005`.
Payload: `aitdp_lead_percent` + `aitdp_lead_remarks` (optional — defaults to Dev
`aitdp_percent` / `aitdp_remarks` so packs always populate).

Helper: `scripts/bin/jira-fix-adf.py` · Skill + `jira-tdpqa-qa-test-fields.mdc`.
