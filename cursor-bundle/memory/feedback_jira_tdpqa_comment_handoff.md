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
7. Rework fixes move to the exact **QA Retest** status, never **QA:Traige**. If Jira does not expose a QA Retest transition, report the available transitions and do not guess or chain through another status. TDPQA has no QA Retest transition (BA Clarification / To Do / Dev:Rework / QA:Traige / QA Tested→QA:Closed / "QA Tested Issue is Still There"→Dev:Rework / Product Team Validation) — report unavailable, leave status as-is.

## Rework / QA-retest proof block (2026-07-17, TDPQA-72)

On a **reopened** ticket a one-line handoff or prose-only Dev section is not proof. QA needs traceable, re-verifiable evidence that the **exact** scenario they failed was tested before the build shipped. Every rework handoff (comment on TDPQA; Dev Test Details on SDCP) MUST carry a **Dev Test Evidence** block:

- Build line + one commit reference (sanctioned exception to "no build/SHA" on internal QA projects — QA cite builds and demand traceability on reopen; still no branch names / full tag noise).
- Real-flow verify wording (verify_mode intent without `ntest`/`registry`/`e2e` jargon).
- Dataset / fresh LANs actually run (parent + members; last vs non-last member).
- Scenario matrix with **Run / Not-run** + Result — includes the exact QA fail mode; anything not executed is explicit Not-run, never implied Pass.
- **Persisted values expected-vs-actual** for every touched money area (functional labels + numbers, not raw table/column names) — presence-only is not acceptance.
- User-visible webapp views (Summary Accrued/Original, Overview account list, Statement txn-vs-principal) when the fix changes amounts/billing.
- `Result: PASS` + scope note (fresh fixture because old QA LANs already closed) + fresh-retest instruction.

No "Result: Pass" without this block. The developer proof comment must be the latest comment (new comment if QA posted newer observations). Full presentation guidance: SKILL.md § QA retest / rework proof block.

Skill: `.cursor/skills/jira-fix-update/SKILL.md` Step 0 + § QA retest / rework proof block  
Helper: `jira-fix-adf.py project_mode | owners_tdpqa | handoff_comment`
