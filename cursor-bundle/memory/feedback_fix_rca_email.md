---
name: feedback_fix_rca_email
description: "Canonical RCA / fix email format — paste-ready for mail or JIRA. Triggers: RCA mail, RCA email, write mail for fix, issue RCA. Skill: .cursor/skills/fix-rca-email/SKILL.md"
metadata:
  node_type: memory
  type: feedback
---

When the user asks for an **RCA mail**, **fix email**, or **issue RCA response**, produce a **paste-ready** block — same discipline as release details, with an extra **Permanent fix** section when a code/schema change ships.

## Relationship to release details

| Ask | Skill | Output |
|-----|-------|--------|
| release details / QA handoff | `release-details` | Paste block + auto-push |
| RCA mail / fix email / explain issue to team | `fix-rca-email` | Email subject + paste body (no auto-push unless user also shipped code) |

Both use the **same paste body sections** below. Fix-rca-email adds email wrapper (Subject, greeting, sign-off).

## User detail level (always apply)

- **RCA** — 3–5 lines: symptom, primary cause, secondary cause (if any), correlators (LAN, ext ref), what was **not** the cause
- **Permanent fix** — what ships, which repo/branch, migration id if any, pre-deploy vs app deploy order, backward compatibility in one line
- **Impact analysis** — 3–6 bullets: Affected / Not affected / Pre-deploy note / What fix does **not** do
- **Dev testing scenarios done** — 4–5 items: Setup / Action / Expected / Result; honest Result (Pass | Pass (logic review) | Not run in UAT)

RCA and impact stay concise. Dev scenarios carry replay detail. **No markdown tables** — bullets and numbered lists only.

## Paste body (copy directly)

```text
Fix: <one line>
JIRA: <keys or TBD>
Reported LANs: <comma-separated>
Reported ext refs: <if known>
Release branch: <branch> (<repo/service>)

RCA
<3–5 lines plain language>

Permanent fix
<bullets: migration, code path, pre-deploy steps summary — no full SQL unless user asks>

Impact analysis
- Affected: ...
- Not affected: ...
- Backward compatible: ...
- Note: ...

Dev testing scenarios done
1. <title>
   Setup: ...
   Action: ...
   Expected: ...
   Result: ...

Thanks,
<name>
```

## Email wrapper (outside paste body)

```text
Subject: RCA — <short symptom> (<LAN or ext ref>)

Hi Team,

<optional 1-line intro>

<paste body sections>

Thanks,
<name>
```

## Agent-only gate (NOT in email)

Before writing the email, run the same checks as `feedback_release_details_final.md` § Full impact gate when the fix touches money/flow/schema:

- Verify RCA from log + code + DB evidence
- Callers / blast radius for schema or code change
- State what fix does not heal (existing stuck loans, bank-side failure)

Translate findings into business language in Impact and Dev scenarios only.

## Paste rules

- **No tables** in mail/JIRA body
- **Minimal code jargon** — use app words (disbursement, CBS GL, bank error message, loan filler field); mention migration version (e.g. V000196) and column name when relevant for DBA
- **No file paths or line numbers** in paste body unless user explicitly asks for technical appendix
- **Never write to Jira** — user copies and sends

Skill: `.cursor/skills/fix-rca-email/SKILL.md`
