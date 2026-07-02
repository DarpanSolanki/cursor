---
name: concise-email
description: Draft concise, professional emails. Use when the user asks to "create an email/mail" or "draft a mail". For RCA/fix/issue mails with impact and dev scenarios, use fix-rca-email skill instead. Keep it minimal, avoid code-level details unless necessary for clarity, and avoid tier labels like L0/L1—use neutral headings like "Immediate actions" and "Follow-up".
---

# Concise Email Drafting

## Route first

| User ask | Use skill |
|----------|-----------|
| RCA mail, fix email, issue RCA, mail response for production issue | **`.cursor/skills/fix-rca-email/SKILL.md`** |
| release details, QA handoff, paste for JIRA after fix | **`.cursor/skills/release-details/SKILL.md`** |
| Short status / approval / general note | This skill |

## Rules (must follow)

- **Proof-backed only (non-negotiable):** Do not state anything as fact unless verified via log/code/DB. Label runtime-only facts as **needs ops confirmation**.
- Keep general mails short (~120–200 words) unless user asks for more.
- **No markdown tables** in paste body for mail/JIRA.
- Do **not** use labels like **L0/L1**. Use **Immediate actions** / **Follow-up** / **Verification**.
- Always include a clear **ask** when appropriate.

## Default structure (general mail only)

Subject: <clear outcome-focused subject>

Hi Team,

<1–2 lines context + impact>

**Immediate actions**
- ...

**Follow-up**
- ...

**Verification**
- ...

Thanks,
<name>

For RCA + permanent fix + impact + dev scenarios, use **`fix-rca-email`** paste format in `cursor-bundle/memory/feedback_fix_rca_email.md`.
