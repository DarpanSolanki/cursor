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

**Content source:** Draft from `.cursor/skills/release-details/SKILL.md` sections 1–3 (RCA, Impact, Dev scenarios).

**Do not** duplicate release mail Special notes (SQL, masterdata) into RCA/Impact/Dev unless the user asks.

## NEVER put internal information in JIRA (hard rule — repeated feedback)

JIRA is read by QA, product, and client-facing folks. Keep it **functional and business-level**. **Never** write any of these in RCA / Impact / Dev Test / comments:

| Forbidden | Say instead (functional) |
|-----------|--------------------------|
| Branch names (`mfi_release_v3.4.2.1`, `feature/*`) | "the latest build" / "the build shared for QA" — no version at all unless user asks |
| Table names (`loan_due_details`, `loan_installment_details`) | "outstanding dues", "the repayment schedule" |
| Column names (`paid_amount`, `waived_amount`, `is_deleted`) | "amount paid", "amount waived" |
| Transaction type / event codes (`RSCH_DEATH_FORECLOSURE`, error `134xxx`) | "the reschedule entry", "the closure posting" |
| apiName / class / processor / job names | "the death-foreclosure process", "loan closure" |
| Commit SHA, PR numbers, file paths | (omit entirely) |
| Internal test fixtures / LAN numbers we created | describe the scenario, not the LAN — **except** Dev Test **evidence block** (see below) |
| "local e2e", "simulation", "registry case", "fixture", "poisoned rows" | "developer testing", "verified the scenario end to end" |

**Environment config** the QA team must set (e.g. an accounting rule must be present) is OK to mention in **functional** terms, because it affects their retest — but name it as a business config, not an internal code identifier.

## Tone (developer-to-developer / QA, human)

Write like a developer explaining to a teammate — natural, direct, confident. **Not** like an agent:

- No bold-label tables mapping "Observation → Fix outcome" unless genuinely clearer
- No emoji, no "✓/→", no marketing words ("permanent fix", "no hacks", "100%")
- No robotic scaffolding ("Ready for QA on", boiler headings on every line)
- Short paragraphs and a simple numbered retest list are fine
- State what was wrong, what changed functionally, and what to retest — plainly

## Comment style (human — reply, don't report)

A JIRA **comment** is a chat reply on a thread, not a status report. Keep it to **2–4 sentences / a short paragraph or two**. Answer the last person, say what you did, give one number if it helps, tag who needs to retest. That's it.

Hard limits for comments:

- **No section headers** (`Root Cause`, `Impact`, `Example:`), no bold field-labels, no numbered "1. Original… 2. Accrued…" restatements of what someone already wrote.
- **Don't repeat the spec back** — the reader wrote it; just confirm you followed it.
- **No tables, no bullet lists** unless you're genuinely listing 3+ retest items.
- **One inline example max**, written as a sentence ("billed 2,65,816 with 900 paid → 2,64,916"), not a labelled block.
- Reference the person's last message naturally ("done as per your last comment", "as you confirmed").
- Detailed testing/RCA belongs in the **fields** (Dev Test Details, RCA), never duplicated into the comment.

<bad-example>
Robotic report — reads like an agent:
```
Confirming both parts of this fix:
**1. Group 360 Total Outstanding** (already in QA build): ...
**2. Loan 360 Summary — Interest row**: **Original** = total billed interest; **Outstanding** = Original − (Paid + Waived + Written Off) ...
**Example:** billed interest Original = ₹2,65,816; Paid = ₹900 → Outstanding = ₹2,64,916
Dev tested both parts locally — all 8 scenarios Pass ...
```
</bad-example>

<good-example>
Human reply — short, answers the thread:
```
@Sudheer @Srikant done as per your last comment. Interest Original now shows total billed interest and Outstanding = Original − (Paid + Waived + Written Off), Accrued kept separate. Checked a few loans locally — e.g. billed 2,65,816 with 900 paid gives 2,64,916, so no more 0.

Group 360 part was already in the earlier build; only accounting changed. @Reema pls retest once I share the tag.
```
</good-example>

**Minimal fix (mandatory):** Read `.cursor/skills/minimal-fix/SKILL.md`. Impact Analysis **must** include: what is **not** changed, whether read-path dedupe was **rejected**, and post-deploy SQL for existing poison rows (not code guards for dirty data).

## Mentions / tagging (@ — mandatory for comments)

**Markdown `@Name` does NOT tag anyone** — it posts as plain grey text. Real tagging needs ADF `mention` nodes with the person's `accountId`:

```json
{"type": "mention", "attrs": {"id": "<accountId>", "text": "@Sudheer Pandey"}}
```

Name → accountId map: **`.cursor/skills/jira-fix-update/mentions.json`** (matched case-insensitively, longest name first; aliases like `Sudheer` / `Reema` included).

Build a comment with real mentions via the helper (turns `@Name` tokens into mention nodes automatically):

```bash
python3 scripts/bin/jira-fix-adf.py comment "@Sudheer Pandey done as per your last comment. @Reema pls retest." 
# → ADF doc; post with addCommentToJiraIssue(contentFormat="adf", commentBody=<that json string>)
```

Rules:

- Always post comments with `contentFormat: "adf"` when they contain mentions — never markdown `@`.
- If a name is missing from `mentions.json`, resolve it with `lookupJiraAccountId(cloudId=novopay.atlassian.net, searchString="<name>")` and **add it to the map** (name + first-name alias) so the next run works offline.
- Verify the update/create response body shows `data-type="mention"` for each tagged person; plain `@Name` text means the tag failed.

**Editing a comment in place:** `addCommentToJiraIssue(commentId=<id>, contentFormat="adf", commentBody=<adf json string>)`. This works once the comment is committed; a just-created comment can briefly return "not found" (replica lag) — retry after a few seconds rather than re-posting (avoids duplicates).

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

**QA data caveat (add when the bug left dirty rows on existing test loans):** if loans used in earlier QA rounds are already in a bad state from previous builds, add a short "Note for QA on retest" comment: those loans can still look broken even with the fix because their data is already off, so QA should validate on freshly created loans and check for pre-existing inconsistency before raising a defect. Functional language only — no table/column names.

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
| JIRA As per AI TDP Temp | `customfield_11477` | Multicheckbox: Yes `12039` / No `12040` / Not Applicable `12709`. Set **Yes** when an AI coding tool was used |
| AITDP Effectiveness as % | `customfield_11676` | Float (0–100). Honest estimate of how much the AI tool actually accelerated this fix. **Never leave the `1` placeholder** |
| AITDP Remarks | `customfield_11677` | Textarea → ADF. **Describe how the AI tool was used** across RCA/implementation/testing. **Never just "Used Cursor"** |

**Dev Test Details must not include:** QA ticket LANs, pending QA, UAT sign-off, or scenarios not run by dev.

## Dev test evidence (concrete proof — mandatory for money / closure fixes)

After a dev test **Pass**, add a **post-test database check** item in Dev Test Details with numbers QA can re-verify. Do not claim Pass from code review or compile alone.

**Workflow**

1. Run the dev test (`ntest run <case>` or flow script) — must exit 0 **this session**.
2. Run proof SQL on the same DB/env (local or named QA) and capture rows.
3. Add one ordered-list item **Post-test database check** with outcomes in plain language.

**What to include (functional labels — no table/column names in JIRA)**

| Check | Example wording |
|-------|-----------------|
| Loan account number | Dev test loan used (OK in evidence block only) |
| Loan status | Closed / Active |
| Closing date | Set yes/no (parent) |
| Principal paid / waived / pending | Amounts per parent and each member |
| Total outstanding | Must be 0 on parent after last-child closure |
| Settlement postings | Death foreclosure amount per member; group closure amount on parent |

**What to omit everywhere (RCA / Impact / comments too):** table names, column names, transaction type codes, apiNames, branch/SHA.

**DCF group last-child example** — after `ntest run dcf.group_parent_last_child_e2e`:

```bash
psql -h localhost -p 5433 -U yugabyte -d yugabyte \
  -v parent_lan='6000137433' -v child1_lan='6000137440' -v child2_lan='6000137441' \
  -f scripts/dcf_sanity/group_dfc_dev_proof.sql
```

**JIRA evidence item template (paste into Dev Test Details):**

```text
Post-test database check (dev env, <date>, synced parent/child group):
Parent loan <LAN> — Closed, closing date set. Principal paid: X | Waived: 0 | Pending: 0 | Total outstanding: 0. Group closure posting: Y.
Member loan <LAN> — Closed. Principal paid: … | Waived: 0 | Pending: 0. Death foreclosure settlement: Z.
(same for each member)
Result: Pass.
```

For non-DCF fixes: define 2–4 observable DB fields that prove the bug is fixed (status, amount, count) and query them the same way before updating JIRA.

## AITDP fields (AI Tool Development Productivity — mandatory, do not leave defaults)

Every SDCP fix handoff must set all three honestly. These are audited productivity metrics — a bare "Used Cursor" or the `1` placeholder is treated as not filled.

- **`customfield_11477`** — `[{"id": "12039"}]` (Yes) when an AI tool was used; `12040` (No) / `12709` (Not Applicable) otherwise.
- **`customfield_11676`** — realistic effectiveness percentage (0–100), not a token value. Base it on how much of RCA + code + testing the tool genuinely drove; the developer still owns review/validation.
- **`customfield_11677`** — a real remark: what the tool did (e.g. traced the flow to find the cause, implemented the change, built and ran the scenarios, prepared handoff) and what the developer verified manually. Business/dev language, no internal identifiers, no emoji.

**The effectiveness percentage is the developer's call.** If unset by the user, ask for the number (recommend one) rather than guessing — a wrong value here is exactly the complaint this rule prevents.

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

- [ ] **Dev test evidence** — post-test DB check with loan status + amounts (money/closure fixes); numbers from query run **this session**
- [ ] **No internal info in RCA/Impact/comments** — no branch/tag, table/column names, txn codes, apiNames, SHA (loan account numbers OK **only** in Dev Test evidence block)
- [ ] **Human tone** — reads developer-to-QA, not agent-generated (no emoji, no "permanent fix/no hacks/100%", no label-heavy tables)
- [ ] **Comment is a reply, not a report** — 2–4 sentences, no section headers/bold labels, doesn't restate the spec back, detail stays in fields
- [ ] No empty ADF paragraphs
- [ ] **Dev Test Details = `customfield_11901`** — not `customfield_11139` (QA field)
- [ ] MICRO Service matches repos changed
- [ ] Pre deployment and Post deployment set (NA if none)
- [ ] `getJiraIssue` verify read-back

## Related

- Release mail paste: `.cursor/skills/release-details/SKILL.md`
- RCA email (Subject + body): `.cursor/skills/fix-rca-email/SKILL.md`
- Field ids + repo map: [fields-reference.md](fields-reference.md)
