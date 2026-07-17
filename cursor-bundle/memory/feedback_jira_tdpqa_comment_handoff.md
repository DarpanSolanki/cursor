---
name: feedback_jira_tdpqa_comment_handoff
description: TDPQA (and non-SDCP) JIRAs have no RCA/Impact/Dev fields — put full QA handoff in one structured comment; never invent companion SDCP tickets for fields
---

# TDPQA JIRA = comment handoff (2026-07-15)

## Mistake that triggered this

On TDPQA-102 agents either (a) tried SDCP custom fields that do not exist, or (b) created an extra SDCP bug just to fill RCA/Impact/Dev, while the QA ticket only got a one-line “ready for QA” comment. That makes releasing to QA harder, not easier.

## Standing rule

1. `python3 scripts/bin/jira-fix-adf.py project_mode <KEY>` first.
2. **SDCP** → `field_handoff` (customfield_11137 / 11138 / 11901 + short ping).
3. **TDPQA** (and other non-SDCP) → `comment_handoff`: one `handoff_comment` ADF with RCA + Impact + Dev + Pre/Post + **AITDP % + remarks**; set `owners_tdpqa` only. Helper **fail-closes** without `aitdp_percent` + `aitdp_remarks`.
4. Never invent a companion SDCP ticket unless the user asks.
5. Edit the handoff comment in place only while it is still the latest relevant comment.
6. If QA has posted newer observations, delete the stale developer handoff and POST a new structured handoff so it appears after the latest QA evidence.
7. Rework fixes move to the exact **QA Retest** status, never **QA:Traige**. If Jira does not expose a QA Retest transition, report the available transitions and do not guess or chain through another status.

Skill: `.cursor/skills/jira-fix-update/SKILL.md` Step 0  
Helper: `jira-fix-adf.py project_mode | owners_tdpqa | handoff_comment`
