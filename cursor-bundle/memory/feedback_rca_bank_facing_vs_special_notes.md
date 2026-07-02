---
name: feedback_rca_bank_facing_vs_special_notes
description: "RCA = bank-forwardable institutional prose (JIRA + release §1). Deploy order, DDL, coordinated services = Special notes only (release §4) + JIRA Pre/Post field — never in RCA."
metadata:
  node_type: memory
  type: feedback
---

## Split (mandatory)

| Audience | Where | Content |
|----------|-------|---------|
| **Bank / external** | **RCA** only (JIRA `customfield_11137` + release mail section 1) | Symptom, cause, resolution in **institutional business language** |
| **Release / TechOps / DBA** | **Special notes** (release mail §4) + JIRA **Pre/Post** (`customfield_11336`) | Deploy order, pre/post SQL.accounting scripts, coordinated microservices, verify steps |

**RCA must never mention:** Flyway, checksum, CREATE INDEX, migration version, branch names, microservice names, batch job class names, SQL scripts, "Pre deployment script", skip flags, index names, schema history INSERT.

**Special notes must include (when applicable):** numbered release steps — what runs first, what deploys together, what to verify after cutover. SQL lives here (release mail) or Pre/Post field (JIRA internal).

## RCA voice — bank-forwardable

Write so **TechOps can paste RCA to the bank** without editing.

- Formal, process-oriented, slightly dense — **not** casual internal tone
- Describe **observed operational outcome** (pending status, incomplete closure, service unavailability during window)
- Cause: **overlapping lifecycle / concurrent reconciliation / extended processing interval** — not locks, callbacks, REQUIRES_NEW
- Resolution: **realigned processing / decoupled workflow / enhanced handling for edge correspondence state** — not "we added skip_api_execution"
- No blame, no "bug", no "gap", no QA names
- 3 short paragraphs (JIRA ADF) or 4–6 line-broken facts (release mail)

## Special notes voice — release effective

Numbered steps an release manager can execute:

1. **Pre deployment** — one-line purpose, then SQL block (or "see attached script path" in agent chat only; paste includes SQL)
2. **Application deploy** — which services, same window, order if any
3. **Post cutover verification** — batch/cycle to run, LAN or backlog check, success criteria
4. Optional: **does not apply to** — unrelated flows

Do **not** repeat RCA narrative in Special notes — only actionable release steps.

Skills: `.cursor/skills/jira-fix-update/SKILL.md`, `.cursor/skills/release-details/SKILL.md`, `.cursor/skills/fix-rca-email/SKILL.md`
