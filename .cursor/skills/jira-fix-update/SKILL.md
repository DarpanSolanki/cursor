---
name: jira-fix-update
description: >-
  Update SDCP JIRA tickets after a fix — RCA, Impact, Dev tests, MICRO Service,
  Pre/Post deployment (NA default), ADF formatting. Use when user asks to update
  JIRA, fill RCA/impact/dev test on a ticket, or hand off SDCP-* after a ship.
requires:
  - release-details
reads:
  - cursor-bundle/memory/feedback_release_details_final.md
  - .cursor/skills/jira-fix-update/fields-reference.md
  - scripts/bin/jira-fix-adf.py
writes: []
triggers:
  - update jira
  - update JIRA
  - fill RCA on ticket
  - SDCP handoff
  - jira fix update
---

# JIRA fix update (SDCP)

After a code fix is shipped (or ready for QA), update the JIRA ticket with **business-language** handoff fields via **Atlassian MCP** (`plugin-atlassian-atlassian`).

**Content source:** Draft from `.cursor/skills/release-details/SKILL.md` sections 1–3 (RCA, Impact, Dev scenarios). **Do not** paste apiNames, class names, processor names, or commit SHA into JIRA fields. Release branch name in RCA is OK once.

**Do not** duplicate release mail Special notes (SQL, masterdata) into RCA/Impact/Dev unless the user asks.

## When to run

- User says update JIRA / fill RCA / hand off ticket
- After `release-details` block is ready and fix is on a branch
- Ticket key like `SDCP-xxxxx` on `novopay.atlassian.net`

## Workflow

1. **Read ticket** — `getJiraIssue(issueIdOrKey, fields=["*all"])` if unsure which fields are empty.
2. **Draft content** — release-details tone (crisp, complete, no code jargon).
3. **Map services** — grep changed repos; set **MICRO Service** checkboxes (see [fields-reference.md](fields-reference.md)).
4. **Pre/Post** — always set `customfield_11336`; use `NA` for both when no scripts (default).
5. **Build ADF** — use `scripts/bin/jira-fix-adf.py` or equivalent; **no empty paragraphs**.
6. **Update** — `editJiraIssue(cloudId=novopay.atlassian.net, contentFormat=adf, fields={...})`.
7. **Verify** — `getJiraIssue` with the custom field keys; confirm spacing and MICRO checks.

Optional: add a short comment only if the user asks — **fields are canonical**; comments often duplicate and go stale.

## Fields to update (every fix handoff)

| Field | Key | Content rules |
|-------|-----|----------------|
| RCA | `customfield_11137` | 3 paragraphs: situation → cause → what was updated (plain language) |
| Impact Analysis Details | `customfield_11138` | 4 bullets: in scope, settlement alignment, not changed, edge/regression note |
| Dev Test Details | `customfield_11901` | Ordered dev scenarios only; each ends with `Result: Pass` or `Result: Fail` |
| Test scenarios executed | `customfield_11937` | Short scenario titles (mirror dev list) |
| Test results (Pass/Fail) | `customfield_11938` | One line, e.g. `All N dev scenarios: Pass.` |
| MICRO Service | `customfield_11337` | Multicheckbox option ids for touched services |
| Pre Deploymenet and Post Deployment Script | `customfield_11336` | See Pre/Post section below |

**Dev Test Details must not include:** QA ticket LANs, pending QA, UAT sign-off, or scenarios not run by dev.

## Pre deployment / Post deployment

Single JIRA field (`customfield_11336`). **Always populate** on update:

```text
Pre deployment: NA
Post deployment: NA
```

When applicable:

```text
Pre deployment: <one-line purpose — e.g. masterdata upsert for product X>
Post deployment: NA
```

SQL and scripts go in this field only, not RCA/Impact/Dev.

ADF via helper:

```bash
python3 scripts/bin/jira-fix-adf.py prepost
python3 scripts/bin/jira-fix-adf.py prepost "Flyway V000122 on accounting DB" NA
```

## MICRO Service

Set every service whose **repo had committed fix code**:

```json
"customfield_11337": [{"id": "11843"}]
```

Accounting = `11843`, LOS = `11844`, Lib = `11848`, etc. — full table in [fields-reference.md](fields-reference.md).

```bash
python3 scripts/bin/jira-fix-adf.py micro accounting
python3 scripts/bin/jira-fix-adf.py micro accounting los
```

## ADF formatting (fixes JIRA spacing bugs)

| Do | Don't |
|----|-------|
| `bulletList` for Impact | Empty `paragraph` nodes between lines |
| `orderedList` for Dev scenarios | `contentFormat: markdown` on edit |
| 3 tight `paragraph` nodes for RCA | Blank lines via empty paragraphs |
| `hardBreak` only if truly needed | Code identifiers in user-visible text |

**API:** `editJiraIssue` with `contentFormat: "adf"`.

## Content templates (business language)

### RCA (3 paragraphs)

1. **Situation** — what users/ops saw (symptom on which flow).
2. **Cause** — why the system behaved that way (scheme/config vs loan state — no class names).
3. **Resolution** — what behaviour changed after the fix; mention release branch if helpful.

### Impact (4 bullets)

- What customer-facing / ops flow is fixed
- Consistency at settlement/closure if relevant
- What is explicitly **not** changed (part prepayment, other products, etc.)
- Edge case or “unchanged when X” guard

### Dev scenarios (ordered)

Format each item:

`Precondition + action in plain language. Result: Pass.`

Example:

1. Product with CBC on scheme and no outstanding CBC on loan — foreclosure quote shows zero CBC. Result: Pass.
2. Product without CBC on scheme but outstanding CBC on loan — quote includes CBC amount. Result: Pass.

## MCP example (minimal)

```text
editJiraIssue(
  cloudId = novopay.atlassian.net,
  issueIdOrKey = SDCP-10427,
  contentFormat = adf,
  fields = {
    customfield_11137: <rca ADF doc>,
    customfield_11138: <impact bulletList doc>,
    customfield_11901: <dev orderedList doc>,
    customfield_11937: <scenario titles orderedList>,
    customfield_11938: <single paragraph Pass/Fail>,
    customfield_11337: [{"id": "11843"}],
    customfield_11336: <pre_post_doc NA/NA>
  }
)
```

## Checklist before closing

- [ ] No apiNames / Java class / processor names in fields
- [ ] No empty ADF paragraphs
- [ ] Dev Test Details = dev-only scenarios with Result
- [ ] MICRO Service matches repos changed
- [ ] Pre deployment and Post deployment set (NA if none)
- [ ] `getJiraIssue` verify read-back

## Related

- Release mail paste: `.cursor/skills/release-details/SKILL.md`
- RCA email (Subject + body): `.cursor/skills/fix-rca-email/SKILL.md`
- Field ids + repo map: [fields-reference.md](fields-reference.md)
