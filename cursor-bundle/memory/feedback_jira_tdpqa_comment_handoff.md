---
name: feedback_jira_tdpqa_comment_handoff
description: >-
  TDPQA bugs now require RCA/Impact/PrePost/AITDP custom fields for QA Test
  transition; fill those in simple language via tdpqa_field_handoff (2026-07-28).
  Older comment-only pattern is obsolete for TDPQA.
---

# TDPQA JIRA = field handoff for QA Test (2026-07-28)

## What changed

TDPQA Bug (`11014`) gained mandatory custom fields. Transition to **QA Test**
fails with: *"Please ensure add RCA / Impact Analysis / Pre or Post deployment
Script / AI TDP Improvement Remarks"*.

| Field | Key | Scale note |
|-------|-----|------------|
| RCA | `customfield_11999` | ADF |
| Impact Analysis Details | `customfield_12008` | ADF |
| Pre /Post Deployment Scripts | `customfield_12007` | ADF Pre/Post lines |
| AiTDP Dev Improvement Remarks | `customfield_12000` | ADF |
| AiTDP Dev Accuracy | `customfield_12001` | **whole percent** (`80`) — not SDCP's 0–1 fraction |
| JIRA As per AI TDP Temp | `customfield_12009` | Yes=`12785` |
| Micro Service | `customfield_12006` | Accounting=`12770` |
| Dev / QA Owner | `11952` / `11953` | unchanged |

## Standing rule

0. **Push gate first** — fix must be on `origin/<reported-train>` before enrich / QA Test. See `feedback_jira_push_train_before_enrich.md`.
1. `python3 scripts/bin/jira-fix-adf.py project_mode <KEY>` → `tdpqa_field_handoff` for `TDPQA-*`.
2. Fill the fields above in **simple language** (what broke / why / fix; impact bullets; Pre/Post NA; AITDP remarks + %).
3. **Always include `dev[]`** — TDPQA has no Dev Test field; pack posts companion comment **Dev Test Details** (+ optional `qa_retest`). Pack fails closed without `dev[]`. See `feedback_jira_tdpqa_dev_test_comment.md`.
4. Never invent a companion SDCP ticket unless the user asks.
5. Do **not** send SDCP field IDs (`11137` / `11676` fraction, etc.) to TDPQA.
6. Rework: exact **QA Retest** if exposed; never **QA:Traige** as substitute. If unavailable, report transitions and leave status.

## Language bar

QA must understand without opening code. No branch/SHA/processor/harness/SQL.
Proven on TDPQA-180 / 184 / 186 / 187 / 188 (2026-07-28).

## History (obsolete for TDPQA)

Before 2026-07-28, TDPQA had **no** RCA/Impact fields and used one structured
`handoff_comment`. That pattern remains for **HSQA / AUT / unknown** projects
(`comment_handoff`). Do not regress TDPQA to comment-only when fields exist.

Skill: `.cursor/skills/jira-fix-update/SKILL.md`  
Rule: `.cursor/rules/jira-tdpqa-qa-test-fields.mdc`  
Helper: `jira-fix-adf.py` mode `tdpqa_field_handoff`
