---
name: feedback_jira_discussion_comment_plain
description: >-
  Discussion / clarification JIRA comments must be short plain English for
  product+UI readers — no API names, processors, error codes, or tech dump.
  Triggered by TDPQA-221 bad first comment (2026-07-31).
---

# JIRA discussion comments = plain English (STANDING)

## When

Any comment that asks product / UI / QA to **discuss or decide** (not a finished QA field handoff). Examples: "please confirm", "who owns the fix", "UI vs backend".

## Bar (fail closed)

Write so Sudheer / Himanshu / QA understand in **~30 seconds** without opening code.

**Do:**
- What the user saw on screen (loan, action, message in everyday words)
- Why in product language (e.g. delayed payment interest vs broken-period interest flag)
- Who should change what (Web / Accounting / Product) in one short block
- 2–4 clear questions
- Real ADF `@mentions` via `jira-fix-adf.py comment`

**Do not:**
- API / processor / class / template / orchestration names
- Error codes (scan already rejects `\b134\d{3}\b` — do not work around with jargon dumps)
- Request payload field dumps, SQL, branch/SHA/version, harness language
- Long "## section" engineering RCA pasted as a comment
- "GET already returns X" unless product asked — say "screen can already load this amount from the existing amount API" if needed at all

## Shape (copy)

```
@Name @Name — short ask.

What QA saw
…

What we found
… (business words only)

Who needs to change what
- Web: …
- Accounting: … (or "no change proposed")

Please confirm
1. …
2. …
```

## vs QA handoff

Finished fix → TDPQA **fields** (`tdpqa_field_handoff`) + short ping / Dev Test Details — still plain language.
Discussion before fix → **this** short comment only. Do not fill RCA fields until a fix is agreed/shipped unless the user asks.

## Edit in place

Prefer update existing discussion comment over posting a second dump. OAuth `comment` POST always creates new — use REST PUT `/comment/{id}` or MCP `commentId` to edit.

Skill: `.cursor/skills/jira-fix-update/SKILL.md` § Discussion comments  
Rule: `.cursor/rules/jira-tdpqa-qa-test-fields.mdc` language bar
