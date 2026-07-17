---
name: jira-fix-update
description: >-
  Update JIRA after a fix for QA handoff. SDCP: fill RCA/Impact/Dev custom fields.
  TDPQA (and other projects without those fields): put the same content in ONE
  structured handoff comment. Use when user asks to update/enrich JIRA, fill RCA,
  or release a TDPQA-* / SDCP-* ticket to QA.
requires:
  - release-details
reads:
  - cursor-bundle/memory/feedback_release_details_final.md
  - cursor-bundle/memory/feedback_jira_enrich_forbidden_scan_assignee.md
  - cursor-bundle/memory/feedback_jira_tdpqa_comment_handoff.md
  - .cursor/skills/jira-fix-update/fields-reference.md
  - .cursor/skills/jira-fix-update/owners-defaults.json
  - .cursor/skills/jira-fix-update/mentions.json
  - scripts/bin/jira-fix-adf.py
  - scripts/bin/jira-enrich.sh
writes: []
triggers:
  - update jira
  - update JIRA
  - fill RCA on ticket
  - SDCP handoff
  - TDPQA handoff
  - jira fix update
  - enrich jira for QA
---

# JIRA fix update (SDCP + TDPQA)

After a code fix is shipped (or ready for QA), update the ticket with **business-language** handoff via **Atlassian MCP** (`plugin-atlassian-atlassian`).

**Content source:** Draft from `.cursor/skills/release-details/SKILL.md` sections 1–3 (RCA, Impact, Dev scenarios).

**Do not** duplicate release mail Special notes (SQL, masterdata) into RCA/Impact/Dev unless the user asks.

## Fast path (mandatory — avoids slow multi-step enrich)

**Root causes of slow JIRA updates:** (1) 10+ separate `jira-fix-adf.py` subprocess calls + repeated scans, (2) `getJiraIssueTypeMetaWithFields` on every handoff (skip — use [fields-reference.md](fields-reference.md)), (3) `getJiraIssue` with `*all` fields, (4) shell subagent without MCP (retry loops), (5) OAuth re-decrypt on every REST call (fixed — token cache + `.venv-jira`).

**One pack → one or two MCP writes:**

```bash
# Build everything in one shot (single forbidden scan):
bash scripts/bin/jira-enrich.sh pack SDCP-11085 payload.json > /tmp/pack.json
# Or: cat payload.json | bash scripts/bin/jira-enrich.sh pack TDPQA-127

# Parent agent (preferred):
#   editJiraIssue(fields = pack.edit_fields, contentFormat=adf)
#   addCommentToJiraIssue(commentBody=<pack.comment_adf as json string>, contentFormat=adf)
#   — omit comment call when pack.comment_adf is null (SDCP with fields only)

# Shell fallback (one OAuth decrypt, cached):
bash scripts/bin/jira-enrich.sh post TDPQA-127 payload.json
bash scripts/bin/jira-enrich.sh post TDPQA-127 payload.json --comment-id 388469  # edit in place
```

**Do not** on routine enrich: `getJiraIssueTypeMetaWithFields`, per-field `jira-fix-adf.py rca|impact|dev|…` chain, or assign a shell-only subagent to post JIRA.

First run once per machine: `bash scripts/bin/jira-enrich.sh ensure`

---

```bash
python3 scripts/bin/jira-fix-adf.py project_mode TDPQA-102
# → mode=comment_handoff | field_handoff
```

| Mode | Projects | Where RCA / Impact / Dev Test live |
|------|----------|-------------------------------------|
| **`field_handoff`** | **SDCP** only | Custom fields (`customfield_11137` / `11138` / `11901` …). Comment = short ping only. |
| **`comment_handoff`** | **TDPQA**, HSQA, AUT, and any non-SDCP | **One structured handoff comment** (those fields do not exist). Set only the owners the project has. |

**Hard rules for agents:**

1. Call `project_mode` before drafting. Never assume SDCP fields exist on TDPQA.
2. **Never invent a companion SDCP ticket** just to have somewhere to put RCA fields — enrich the ticket the user named (unless they explicitly ask for an SDCP tracker).
3. On `comment_handoff`, the handoff **comment is the product** (like field values on SDCP). Edit that comment in place on re-handoff; do not leave a vague “ready for QA” one-liner as the only handoff.
4. Still run `jira-fix-adf.py scan` on every draft (same forbidden tokens).

### TDPQA comment handoff (canonical)

TDPQA has: assignee, Dev Owner (`customfield_11952`), QA Owner (`customfield_11953`), Fix Version labels, Bug Track, Environment. It does **not** have RCA / Impact / Dev Test / MICRO / Pre-Post / AITDP custom **fields** — so those go in the handoff **comment**, including **AITDP % + remarks** (mandatory).

```bash
python3 scripts/bin/jira-fix-adf.py owners_tdpqa
# → customfield_11952 Dev Owner (Darpan), customfield_11953 QA Owner (Srikant)

python3 scripts/bin/jira-fix-adf.py handoff_comment <<'EOF'
{
  "lead_in": "@Reema @Srikant Fix is ready for QA retest.",
  "rca": {
    "situation": "...",
    "cause": "...",
    "resolution": "..."
  },
  "impact": ["In scope …", "Unchanged …", "Edge: retest on fresh loans …"],
  "dev": [
    "Fresh … Result: Pass.",
    "Regression … Result: Pass.",
    "Note for QA — ticket LANs … use a fresh group."
  ],
  "result": "Developer scenarios: Pass.",
  "service": "Accounting",
  "pre": "NA",
  "post": "NA",
  "aitdp_percent": 0.75,
  "aitdp_remarks": "AI-assisted RCA using QA screenshots and loan data; traced root cause; implemented the functional fix; developer verified the scenarios."
}
EOF
# → ADF; requires aitdp_percent + aitdp_remarks (exit 2 if missing); scan built-in
```

Then:

1. `editJiraIssue` — `assignee` + `owners_tdpqa` only (do **not** send SDCP customfield_11137 / 11676 etc.).
2. `addCommentToJiraIssue(contentFormat=adf, commentBody=<handoff ADF>)` — or edit existing handoff comment id in place.
3. Transition toward QA when workflow allows.
4. Verify comment has **RCA / Impact / Dev / AITDP** sections and real mentions.

**AITDP in TDPQA comment (mandatory):**

| In comment | How to write |
|------------|--------------|
| JIRA as per AI TDP | `Yes` |
| AITDP effectiveness | Human **percent** in the comment (`75%`). Pass `aitdp_percent` as **0–1 fraction** (`0.75`) to the helper — same as SDCP field scale |
| AITDP remarks | 2–4 sentences: analysis + finding + fix + verify — **never** Cursor / IDE brand |

Helper rejects handoff JSON without `aitdp_percent` + `aitdp_remarks`.

### SDCP field handoff (unchanged)

Fill `customfield_11137` / `11138` / `11901` / … + AITDP fields. Comment stays a **short** human reply (2–4 sentences) that tags QA — do not dump the full RCA again into the comment.

---


## Agent tool routing (hard)

JIRA enrich **requires** Cursor `CallMcpTool` → `plugin-atlassian-atlassian` (`editJiraIssue` / `addCommentToJiraIssue` / `getJiraIssue`).

- **Do not** assign a shell-only / command-execution subagent to *post* JIRA updates — it can only build ADF packs (`jira-fix-adf.py`). The **parent agent** must own MCP writes.
- Auth is Cursor OAuth to `mcp.atlassian.com` (plugin). Shell cannot read encrypted `mcpOAuth.secret` blobs from `state.vscdb`. If tools only show `mcp_auth`, user must re-auth Atlassian in Cursor Settings → MCP.
- cloudId for novopay.atlassian.net: `2f9bec17-0fa3-45d7-8399-209b8a496a61` (or `novopay.atlassian.net` hostname).
- Ready packs (example): `scripts/scratch/jira-sdcp11085-tdpqa127/call_*.json`.
- Shell-only fallback (when CallMcpTool unavailable): `bash scripts/bin/jira-enrich.sh post <KEY> payload.json` — uses cached OAuth via `.venv-jira`. Low-level: `scripts/bin/jira-rest-from-cursor-oauth.py apply-pack`. Prefer CallMcpTool on the parent agent when available.


## NEVER put internal information in JIRA (hard rule — repeated feedback)

JIRA is read by QA, product, and client-facing folks. Keep it **functional and business-level**. **Never** write any of these in RCA / Impact / Dev Test / Test scenarios / Test results / AITDP remarks / comments:

| Forbidden | Say instead (functional) |
|-----------|--------------------------|
| Branch names (`mfi_integration_v3.4.2.1`, `mfi_release_*`, `feature/*`) | "the build shared for QA" / "ready for QA" — **no version at all** unless user explicitly asks |
| Version numbers (`3.4.2.2`, `3.7.1`, `3.4.2.1`) | same — omit; Reported version field already exists on the ticket |
| Table names (`loan_due_details`, `loan_installment_details`) | "outstanding dues", "the repayment schedule" |
| Column names (`paid_amount`, `waived_amount`, `is_deleted`) | "amount paid", "amount waived" |
| Transaction type / event codes (`RSCH_DEATH_FORECLOSURE`, error `134xxx`) | "the reschedule entry", "the closure posting" |
| apiName / class / processor / job names | "the death-foreclosure process", "loan closure" |
| Commit SHA, PR numbers, file paths | (omit entirely) |
| Internal harness (`ntest`, `registry`, `unit`, `e2e`, `fixture`, `N=1..20`, member-count matrix jargon) | functional retest steps QA can follow on the product |
| Internal test fixtures / LAN numbers **we** created | describe the scenario — **except** ticket-reported LANs in an evidence / retest note |
| "local e2e", "simulation", "registry case", "poisoned rows" | "developer testing", "verified the scenario end to end" |
| Product / IDE brand (`Cursor`, `Cursor IDE`) in **any** JIRA field | "AI-assisted RCA…", "assisted analysis and implementation" — name the **help**, not the tool brand |

**Environment config** the QA team must set (e.g. an accounting rule must be present) is OK in **functional** terms — business config name, not an internal code identifier.

### Pre-flight forbidden-token scan (mandatory — fail closed)

**Before** every `editJiraIssue` or comment create/update, concatenate all draft text (RCA, Impact, Dev Test, scenario titles, test results, AITDP remarks, comment) and scan:

```bash
python3 scripts/bin/jira-fix-adf.py scan "<full draft text>"
# exit 2 = FORBIDDEN hits — rewrite until OK
```

Reject and rewrite if any of these appear (case-insensitive):

`mfi_integration`, `mfi_release`, `feature/`, `ntest`, `registry.json`, `registry case`, commit SHA (8+ hex), `Processor`, `DAOService`, `apiName`, `N=1..20`, `member counts 1–20`, `\be2e\b`, `unit test`, `fixture`, `poisoned rows`, version `\b3.x.y(.z)?\b`, table/column names listed above, `RSCH_*`, `134xxx`, **`Cursor` / `Cursor IDE`** (capital-C brand only — verb "cursor" is fine).

`Result: Pass.` at the end of a Dev Test Details item is **allowed** (field convention). Do **not** put harness shouty `PASS` / pass-counts in **comments**.

### BAD vs GOOD — Dev Test Details

<bad-example>
Internal harness dump (forbidden):
```
2. Same distribute check across member counts from 1 through 20 — ntest registry case sdcp_11058. Result: Pass.
3. Full aged live parent/member foreclosure e2e — not run.
4. Post-test distribute proof (unit) on fixture LAN 6000….
```
</bad-example>

<good-example>
Functional QA retest steps:
```
1. Fresh SHG parent with two equal-share members — complete parent foreclosure; parent BPI must equal sum of member BPI (e.g. 79 → 40+39, not 39+39). Result: Pass.
2. Parent with more than two members — after parent foreclosure, parent BPI equals sum of all member BPI. Result: Pass.
3. Solo member foreclosure path — unchanged / out of scope. Result: Pass (regression check).
4. Retest on a fresh parent foreclosure; do not use loans that already closed with the old ₹1 gap. Ticket LANs show historical mismatch only.
```
</good-example>

### BAD vs GOOD — comments

<bad-example>
```
@Srikant fix is in the 3.4.2.2 accounting build / mfi_integration_v3.4.2.2. ntest PASS N=1..20.
```
</bad-example>

<good-example>
```
@Srikant @Reema Fix is ready for QA. Parent SHG foreclosure now splits BPI from the parent total across members so they always add up (e.g. 79 → 40+39). Please retest on a fresh parent foreclosure — older closed loans can still show the old ₹1 gap.
```
</good-example>

## Comment style

### SDCP ping comment (field_handoff) — short reply

On SDCP, details live in custom fields. The **comment** is a chat reply — **2–4 sentences**. Answer the last person, say fix is ready, tag who retests. Do **not** repeat full RCA/Impact/Dev into the comment.

Hard limits for SDCP ping comments:

- **No section headers** (`Root Cause`, `Impact`) — those belong in fields
- **No tables**; no numbered restatement of the ticket description
- **No build/branch/version** unless the user explicitly asked
- Prefer edit-in-place over posting a second status dump

### TDPQA handoff comment (comment_handoff) — structured, complete

On TDPQA there are **no** RCA/Impact/Dev/AITDP fields. The handoff comment **must** carry the same substance SDCP puts in fields, using `jira-fix-adf.py handoff_comment`. Required section headings: **RCA**, **Impact**, **Dev test / QA retest**, **Pre / Post deployment**, **AITDP** (Yes + effectiveness % + remarks). Optional: **Service** / **Test result**.

Still: no harness jargon, no branch/SHA/version in the body, real ADF `@mentions`. One comment — edit in place when content changes.

### Tone (all modes)

Write like a developer explaining to a teammate — natural, direct, confident. **Not** like an agent:

- No emoji, no "✓/→", no marketing words ("permanent fix", "no hacks", "100%")
- State what was wrong, what changed functionally, and what to retest — plainly

<bad-example>
Robotic SDCP ping (or TDPQA one-liner missing handoff):
```
@Reema ready for QA.
```
</bad-example>

<good-example>
SDCP ping (fields already filled):
```
@Sudheer @Srikant done as per your last comment. Interest Original now shows total billed interest and Outstanding = Original − (Paid + Waived + Written Off). @Reema pls retest once the build is shared.
```
</good-example>

<good-example>
TDPQA handoff comment (via handoff_comment helper) — lead-in + RCA + Impact + Dev retest + Pre/Post NA. QA can start without opening another ticket.
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
# → ADF doc; posts with addCommentToJiraIssue(contentFormat="adf", commentBody=<that json string>)
# helper also runs forbidden-token scan and exits 2 if dirty
```

Rules:

- Always post comments with `contentFormat: "adf"` when they contain mentions — never markdown `@`.
- If a name is missing from `mentions.json`, resolve it with `lookupJiraAccountId(cloudId=novopay.atlassian.net, searchString="<name>")` and **add it to the map** (name + first-name alias) so the next run works offline.
- Verify the update/create response body shows `data-type="mention"` for each tagged person; plain `@Name` text means the tag failed.

**Editing a comment in place:** `addCommentToJiraIssue(commentId=<id>, contentFormat="adf", commentBody=<adf json string>)`. This works once the comment is committed; a just-created comment can briefly return "not found" (replica lag) — retry after a few seconds rather than re-posting (avoids duplicates).

## Assignee + owners (mandatory on every enrich)

**On every handoff**, set `assignee` and the **project’s** owner fields (not SDCP owner keys on TDPQA).

### SDCP (`owners`)

| Field | Key | Default |
|-------|-----|---------|
| Assignee | `assignee` | Darpan Solanki |
| Dev Lead | `customfield_11543` | Darpan |
| Dev Owner | `customfield_11898` | Darpan |
| Product Owner | `customfield_11005` | Sudheer Pandey |
| QA Owner | `customfield_11899` | Srikant Sulpule |
| Reviewer | `customfield_10160` | Navaneet Kumar |
| Approvers | `customfield_10003` | Navaneet Kumar |

```bash
python3 scripts/bin/jira-fix-adf.py assignee
python3 scripts/bin/jira-fix-adf.py owners
```

### TDPQA (`owners_tdpqa`)

| Field | Key | Default |
|-------|-----|---------|
| Assignee | `assignee` | Darpan Solanki |
| Dev Owner | `customfield_11952` | Darpan |
| QA Owner | `customfield_11953` | Srikant Sulpule |

```bash
python3 scripts/bin/jira-fix-adf.py assignee
python3 scripts/bin/jira-fix-adf.py owners_tdpqa
```

Do **not** send SDCP `customfield_11898` / `11137` / `11676` / AITDP keys to TDPQA — the edit will fail or silently ignore. Put **AITDP Yes + % + remarks inside the handoff comment** via `aitdp_percent` / `aitdp_remarks` on `handoff_comment` (helper fail-closes if missing).

Override owners only when the user names different people.

## When to run

- User says update JIRA / fill RCA / hand off ticket / enrich for QA retest
- After fix is on origin (or user asked handoff before push)
- Ticket key `SDCP-*` **or** `TDPQA-*` (and similar non-SDCP keys)

## Workflow

### Shared

1. **`project_mode <KEY>`** — choose `field_handoff` vs `comment_handoff`.
2. **Read ticket** — `getJiraIssue` (status, existing handoff comment id, owners).
3. **Draft** — same business content (RCA / Impact / Dev) either way; scan forbidden tokens.
4. **Owners + assignee** — `owners` or `owners_tdpqa` matching the mode.
5. **Apply handoff** — fields (SDCP) **or** `handoff_comment` ADF (TDPQA).
6. **QA transition** when available; verify read-back.

### SDCP only (after step 3)

- Map MICRO Service; set Pre/Post; set AITDP Yes + fraction + remarks.
- `editJiraIssue` with RCA/Impact/Dev custom fields.
- Short ping comment with mentions (optional / if handoff to QA).

### TDPQA only (after step 3)

- `handoff_comment` JSON → ADF comment (canonical).
- `editJiraIssue` with assignee + `owners_tdpqa` only.
- Do **not** create an SDCP bug “for fields” unless the user asks.

Optional: on **SDCP**, a short ping comment is enough when fields are filled. On **TDPQA**, the structured handoff comment is mandatory — do not leave QA with only “ready for QA”.

**QA data caveat** (both modes): if earlier QA loans are already dirty from pre-fix builds, say so in Dev Test / handoff Dev section — retest on fresh loans; functional language only.

## Fields to update (every **SDCP** fix handoff)

For **TDPQA**, skip this table — use Step 0 `comment_handoff` instead.

| Field | Key | Content rules |
|-------|-----|----------------|
| RCA | `customfield_11137` | 3 paragraphs: situation → cause → what was updated (plain language; **no version/branch**) |
| Impact Analysis Details | `customfield_11138` | 4 bullets: in scope, settlement alignment, not changed, edge/regression note |
| Dev Test Details | `customfield_11901` | Ordered **functional retest steps** QA can follow; each ends with `Result: Pass` or `Result: Fail` when run by dev |
| Test scenarios executed | `customfield_11937` | Short scenario titles (mirror dev list; no harness jargon) |
| Test results (Pass/Fail) | `customfield_11938` | One line, e.g. `All listed developer scenarios: Pass.` |
| MICRO Service | `customfield_11337` | Multicheckbox option ids for touched services |
| Pre Deploymenet and Post Deployment Script | `customfield_11336` | See Pre/Post section below |
| Assignee | `assignee` | Darpan unless user overrides |
| Dev/QA/PO owners | see owners section | From `owners-defaults.json` |
| JIRA As per AI TDP Temp | `customfield_11477` | Multicheckbox: Yes `12039` / No `12040` / Not Applicable `12709`. Set **Yes** when AI assisted the work |
| AITDP Effectiveness as % | `customfield_11676` | Float **0–1 fraction** (`0.75` = UI 75%). **Never write `75`** — UI shows 7500% |
| AITDP Remarks | `customfield_11677` | Textarea → ADF. **How the agent helped** (analysis + RCA + impl + verification) — see AITDP section; **never** name Cursor / IDE brand |

**Dev Test Details must not include:** QA ticket pending sign-off, UAT sign-off, harness case ids, or scenarios not run by dev (do not list "not run" e2e as a scenario title).

## Dev test evidence (concrete proof — mandatory for money / closure fixes)

After a dev test **Pass**, you may add a **post-test check** item in Dev Test Details with numbers QA can re-verify. Do not claim Pass from code review or compile alone.

**Internal workflow (agent only — never paste into JIRA):** run local/registry tests and proof SQL in the workspace. Translate outcomes into functional wording only.

**What to include in JIRA (functional labels — no table/column/harness names)**

| Check | Example wording |
|-------|-----------------|
| Loan account number | Ticket-reported LAN, or "fresh parent/member group used in retest" |
| Loan status | Closed / Active |
| Closing date | Set yes/no (parent) |
| Principal paid / waived / pending | Amounts per parent and each member |
| Total outstanding | Must be 0 on parent after last-child closure |
| Settlement postings | Death foreclosure amount per member; group closure amount on parent |

**What to omit everywhere (RCA / Impact / comments too):** table names, column names, transaction type codes, apiNames, branch/SHA/version, ntest/registry/e2e.

**JIRA evidence item template:**

```text
Post-test check (dev env, <date>):
Parent loan <ticket LAN or fresh LAN> — Closed, closing date set. Principal paid: X | Waived: 0 | Pending: 0 | Total outstanding: 0.
Member loan … — Closed. …
Result: Pass.
```

## QA retest / rework proof block (MANDATORY on reopened tickets)

When a ticket is **reworked / reopened** (QA already retested once and posted fresh observations, or the ticket bounced through **Dev:Rework**), a one-line "ready for QA" or a prose-only Dev section is **not enough**. QA needs **traceable, re-verifiable proof** that the exact scenario they failed was tested before the build was shared. Every rework handoff comment (TDPQA) or Dev Test Details (SDCP) **must** carry a **Dev Test Evidence** block with all of the following:

| Proof item | Required content | Notes |
|---|---|---|
| **Build & implementation reference** | Build line + commit reference the fix was verified on | On internal QA projects (TDPQA / HSQA / AUT) this is a **sanctioned exception** to the "no build/SHA" rule — QA themselves cite build tags and demand exact traceability on reopen. Keep it to the build line + one commit reference; do **not** paste branch names or full `mfi_release_*_NNN` tag noise. |
| **How it was verified** | Real-flow run + acceptance mode (functional words: "developer real-flow run in strict acceptance mode") | Encodes the verify_mode / command intent **without** harness jargon (`ntest`, `registry case id`, `e2e`). Never claim Pass from compile/code review. |
| **Dataset / LANs** | The fresh developer LANs actually run (parent + members) | Business identifiers QA can look up; state last-member vs non-last-member. |
| **Scenario matrix** | Each scenario + **Run / Not run** + Result | Must include the **exact QA fail mode** (e.g. pre-existing EMI billing + excess + force-bill). Anything **not** executed this cycle is listed explicitly as **Not run / out of scope** — never implied as Pass. |
| **Persisted values — expected vs actual** | For **every touched money area**, the expected value and the actual observed value | Functional labels + numbers (e.g. "settlement amount == principal: 13,702 == 13,702, excess 200"), not raw table/column names. This is the value-level DB proof — presence-only ("a row exists") is **not** acceptance. |
| **User-visible views (webapp)** | When the fix changes amounts / billing / summary / statement: the screens + fields + values QA sees | Summary (Accrued vs Original), Overview (account list), Statement (txn amount vs principal component). SQL-only is not "webapp verified". |
| **Result + scope note** | `Result: PASS` + why fresh fixture (old QA LANs already closed) + fresh-retest instruction | Never mark PASS if any assert allows the QA fail mode. |

**Hard rule:** No **"Result: Pass"** on a rework handoff unless the proof block covers the **exact** QA fail mode with expected-vs-actual values. A green subset while the acceptance shape QA cited is unproven is **FAIL**, not Pass (`agent-quality-gates.mdc` Gate D-acceptance).

**Presentation (TDPQA comment):** build ADF with a `### Dev Test Evidence` heading, then bold sub-labels (**Build and dataset**, **Scenario matrix**, **Persisted values (expected vs actual)**, **User-visible views (webapp)**, **Result: PASS**, **Scope note**) each followed by a bullet/ordered list. The `handoff_comment` helper's forbidden-token scan bans build/SHA; for the QA-retest proof block on internal QA projects, either post the ADF directly via `addCommentToJiraIssue(contentFormat=adf)` (keeping the build line + one commit reference), or keep those two items out and put the rest through the helper. Everything else (raw table/column names, `ntest`/`registry`/`e2e`, branch names, apiName/Processor) stays banned.

**Ordering on reopened tickets:** the developer proof comment must be the **latest** comment. If QA has posted newer observations since your last handoff, post a **new** structured handoff comment so it appears after the latest QA evidence; edit-in-place only while your handoff is still the newest comment. Do not leave a stale handoff buried above fresh QA observations.

**Status:** move a rework fix to the exact **QA Retest** transition when the workflow exposes one. TDPQA does **not** expose a "QA Retest" transition (available: BA Clarification, To Do, Dev:Rework, QA:Traige, QA Tested→QA:Closed, "QA Tested Issue is Still There"→Dev:Rework, Product Team Validation) — **report that it is unavailable and do not guess** (never silently route through QA:Traige). Leave status as-is and let the handoff comment be the signal.

## AITDP fields (AI Tool Development Productivity — mandatory, do not leave defaults)

Every SDCP fix handoff must set all three honestly. These are audited productivity metrics — a slogan, a product brand name, or the `1` placeholder is treated as not filled.

| Field | Key | Purpose |
|-------|-----|---------|
| JIRA As per AI TDP Temp | `customfield_11477` | Was AI used on this ticket? Yes `12039` / No `12040` / N/A `12709` |
| AITDP Effectiveness as % | `customfield_11676` | Honest estimate as **0–1 fraction** (`0.75` = 75% in UI). Schema is float; Jira % UI ×100. Writing `75` → **7500%** (SDCP-11058). After write: if raw `> 1`, wrong scale — rewrite as `percent/100` |
| AITDP Remarks | `customfield_11677` | **Narrative of how the agent helped** — not a tool brand, not a one-liner slogan |

### AITDP Remarks — what to write (2–4 sentences)

Describe the **help**, not the product:

1. **Analysis** — what evidence was used (attached logs, QA loan data, code-path trace).
2. **Finding** — root cause in functional terms (e.g. independent rounding on parent vs members).
3. **Implementation** — what was changed functionally (e.g. distribute parent BPI across members like fees so books match the parent quote).
4. **Verification** — what the developer confirmed (e.g. split math across multiple group sizes).

OK: "AI-assisted RCA…", "assisted analysis and implementation", "AI agent helped trace…".
**Never:** `Cursor`, `Cursor IDE`, or any IDE/product brand in Remarks (or any other JIRA field unless the user explicitly asks).
**Still never:** branch, SHA, processor/class, ntest/registry/e2e, version numbers.

<bad-example>
```
Used Cursor to trace parent vs member BPI… / Cursor RCA+impl+parity tests
```
</bad-example>

<good-example>
```
AI-assisted RCA on the reported parent vs child foreclosure interest mismatch using the attached logs and QA loan data; traced independent rounding on parent versus members; implemented parent-amount distribution for member BPI so books match the parent quote for any member count; developer verification of the split math across multiple group sizes.
```
</good-example>

```bash
python3 scripts/bin/jira-fix-adf.py aitdp_remarks "<2–4 sentence narrative>"
python3 scripts/bin/jira-fix-adf.py scan "<same text>"   # must reject capital-C Cursor / Cursor IDE
```

**The effectiveness percentage is the developer's call.** If unset by the user, ask for the number (recommend one) rather than guessing.

**Write format (mandatory):** user says "75%" → API value `0.75`. Schema type is `float` (`customfield_11676`); the field name ends in `%` and the UI treats the stored number as a **fraction**.

| Intent (UI) | Correct API write | Wrong (do not) |
|-------------|-------------------|----------------|
| 75% | `0.75` | `75` → UI 7500% |
| 78% | `0.78` | `78` |
| 100% | `1` or `1.0` | `100` |

**Post-write scanner:** `getJiraIssue` → if `customfield_11676 > 1`, you used the wrong scale — set `value / 100` and re-verify.

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
| `hardBreak` only if truly needed | Code identifiers / versions in user-visible text |

**API:** `editJiraIssue` with `contentFormat: "adf"`.

## Content templates (business language)

### RCA (3 paragraphs)

1. **Situation** — what users/ops saw (symptom on which flow).
2. **Cause** — why the system behaved that way (scheme/config vs loan state — no class names).
3. **Resolution** — what behaviour changed after the fix. **Do not** name branch or version.

### Impact (4 bullets)

- What customer-facing / ops flow is fixed
- Consistency at settlement/closure if relevant
- What is explicitly **not** changed (part prepayment, other products, etc.)
- Edge case or “unchanged when X” guard

### Dev scenarios (ordered)

Format each item as a **functional retest step**:

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
    assignee: {"accountId": "5e9d51241067100c195f7b12"},
    ...owners from jira-fix-adf.py owners...,
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

- [ ] **`project_mode` chosen** — SDCP=fields; TDPQA=handoff comment (no fake companion SDCP)
- [ ] **Forbidden-token scan PASS** — including handoff comment / AITDP remarks
- [ ] **No version/branch** in RCA / Impact / Dev / comments
- [ ] **No Cursor / IDE brand** in any JIRA text
- [ ] **Dev Test / handoff Dev = functional QA steps** — not ntest/registry/e2e
- [ ] **Assignee + project owners set** — SDCP `owners` **or** TDPQA `owners_tdpqa`
- [ ] **SDCP only:** AiTDP Yes + 0–1 fraction + remarks; MICRO; Pre/Post; fields `11137`/`11138`/`11901`
- [ ] **TDPQA only:** one `handoff_comment` with RCA + Impact + Dev + Pre/Post + **AITDP % + remarks**; edit-in-place while still newest, else new comment after latest QA observation
- [ ] **Rework / reopened ticket:** Dev Test Evidence proof block present (build+commit ref, real-flow verify wording, dataset LANs, scenario matrix with Run/Not-run, persisted values expected-vs-actual, webapp views when UI impacted, Result + scope note) — no "Pass" without it
- [ ] **QA Retest transition** used if exposed; otherwise reported unavailable (never guess QA:Traige)
- [ ] **Human tone** — developer-to-QA
- [ ] No empty ADF paragraphs
- [ ] `getJiraIssue` / comment read-back confirms content + real mentions

## Related

- Release mail paste: `.cursor/skills/release-details/SKILL.md`
- RCA email (Subject + body): `.cursor/skills/fix-rca-email/SKILL.md`
- Field ids + repo map: [fields-reference.md](fields-reference.md)
- Owners defaults: [owners-defaults.json](owners-defaults.json)
- Memory: `cursor-bundle/memory/feedback_jira_tdpqa_comment_handoff.md`
- Memory: `cursor-bundle/memory/feedback_jira_enrich_forbidden_scan_assignee.md`
- Memory: `cursor-bundle/memory/feedback_jira_aitdp_remarks_no_cursor_brand.md`
- Memory: `cursor-bundle/memory/feedback_jira_aitdp_effectiveness_fraction.md` — `%` write = 0–1 fraction
