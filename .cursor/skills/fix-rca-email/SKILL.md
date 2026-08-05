---
name: fix-rca-email
description: >-
  Paste-ready RCA / fix email for team or QA: RCA, permanent fix, impact analysis,
  dev scenarios tested. Same format as release-details; adds email wrapper.
  Triggers: RCA mail, RCA email, write mail for fix, issue RCA, mail response for issue.
requires:
  - release-details
reads:
  - cursor-bundle/memory/feedback_fix_rca_email.md
  - cursor-bundle/memory/feedback_release_details_final.md
  - cursor-bundle/memory/feedback_minimal_fix_impact_gate.md
writes: []
---

## Routing metadata

<!-- ported from Cursor skill frontmatter -->

- **requires:** `release-details`
- **reads:** `cursor-bundle/memory/feedback_fix_rca_email.md`, `cursor-bundle/memory/feedback_release_details_final.md`, `cursor-bundle/memory/feedback_minimal_fix_impact_gate.md`
- **writes:** []

# Fix RCA email

Read **`cursor-bundle/memory/feedback_fix_rca_email.md`** — canonical paste format.

For **release details / QA handoff with auto-push**, use **`.cursor/skills/release-details/SKILL.md`** instead.

## When to use

- User asks for **RCA mail**, **email response**, **mail for the issue**, **explain to team**
- Production incident explanation with **permanent fix** and **dev scenarios**
- Same fix already documented — user needs **communicable** version, not code dump

## Workflow

1. **Evidence** — logs, LAN, ext ref, error code, code path (agent-only); pinpoint primary vs secondary failure
2. **Impact gate** (agent-only) — same as `feedback_release_details_final.md` § Full impact gate when money/flow/schema touched
3. **Paste body** — Fix / JIRA / LANs / branch → RCA → **Permanent fix** → Impact → Dev scenarios
4. **Email wrapper** — Subject + Hi Team + paste body + Thanks
5. **Do not** append KG, grep lists, or SQL scripts to mail unless user asks for DBA appendix

## Permanent fix section (required when change ships)

Include:

- What changes (one line)
- Repo + branch + migration id (if schema)
- Pre-deploy order (DDL manual → Flyway history register → app deploy) when applicable
- Backward compatibility (one line)

## Dev scenarios — minimum set for disbursement/schema fixes

1. Prod sample / log match (reported LAN)
2. Primary failure path (what broke first)
3. Secondary failure path (if masked error)
4. Regression / happy path not broken
5. Build or migration review

Use **Pass (logic review)** when runtime replay was not executed locally.

## Output to user

Deliver **one copy-paste block**: Subject line, then full email body. No markdown tables.

Optional second block: **DBA pre-deploy SQL** only if user asked or fix includes manual migration register.

## Cross-links

- Release paste format: `release-details` skill
- Short professional mails without RCA: `concise-email` skill
