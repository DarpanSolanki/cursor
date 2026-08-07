---
name: feedback_jira_tdpqa_qa_test_fix_quality_mandatory
description: >-
  QA Test transition requires AiTDP Fix Quality Grade (12002) + Score (12003)
  plus full RCA/Impact/Micro/PrePost/Dev AITDP set. 2026-07-31 TDPQA-227.
---

# TDPQA QA Test — Fix Quality + full field set (STANDING)

## Incident

Moving TDPQA-227 to QA Test failed with mandatory list including RCA, Impact,
Micro, Pre/Post, Dev Accuracy, Dev Improvement Remarks, and truncated
**AiTDP Fix…** — which is **Fix Quality Grade** (`12002`) + **Score** (`12003`).
Those two were null even though other enrich fields were set.

## Evidence (prior tickets)

- TDPQA-207 (Darpan): Grade=`A`, Score=`85` (with Dev Accuracy 85)
- TDPQA-195: Grade=`B`, Score=`60`
- TDPQA-170: Grade=`na`, Score=`0`

## Enrich rule

Every TDPQA pack **must** write:

| Field | Key | Default |
|-------|-----|---------|
| RCA / Impact / PrePost / Micro | 11999 / 12008 / 12007 / 12006 | required |
| Dev Accuracy / Dev Remarks / Yes | 12001 / 12000 / 12009 | from `aitdp_*` |
| **Fix Quality Grade** | **12002** | `aitdp_fix_grade` or **`A`** |
| **Fix Quality Score** | **12003** | `aitdp_fix_score` or Dev Accuracy |
| Lead Accuracy / Lead Remarks | 12004 / 12005 | default from Dev AITDP |

Helper: `jira-fix-adf.py` · rule `jira-tdpqa-qa-test-fields.md` · skill `jira-fix-update`.
