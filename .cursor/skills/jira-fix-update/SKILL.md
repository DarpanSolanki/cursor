---
name: jira-fix-update
description: >-
  Update JIRA after a fix for QA handoff. SDCP: fill RCA/Impact/Dev custom fields.
  TDPQA: fill RCA/Impact/PrePost/AITDP custom fields (mandatory for QA Test) in
  simple language; optional short ping. Other non-SDCP: structured handoff comment.
  Use when user asks to update/enrich JIRA, fill RCA, or release a TDPQA-* / SDCP-*
  ticket to QA.
requires:
  - release-details
reads:
  - cursor-bundle/memory/feedback_release_details_final.md
  - cursor-bundle/memory/feedback_jira_enrich_forbidden_scan_assignee.md
  - cursor-bundle/memory/feedback_jira_tdpqa_comment_handoff.md
  - cursor-bundle/memory/feedback_jira_discussion_comment_plain.md
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
  - jira discussion comment
  - clarify on jira
---

# JIRA fix update (SDCP + TDPQA)

After a code fix is shipped (or ready for QA), update the ticket with **business-language** handoff via **Atlassian MCP** (`plugin-atlassian-atlassian`).

**Content source:** Draft from `.cursor/skills/release-details/SKILL.md` sections 1–3 (RCA, Impact, Dev scenarios).

**Do not** duplicate release mail Special notes (SQL, masterdata) into RCA/Impact/Dev unless the user asks.

## One-page: how to enrich JIRA correctly (fast + clean)
1. Route by key: `SDCP-*` = `field_handoff`; `TDPQA-*` = `tdpqa_field_handoff`; other non-SDCP = `comment_handoff`.
2. Draft **simple** functional text (no branch/SHA/harness jargon). TDPQA/SDCP fields: `rca` + `impact` + `pre`/`post` + AITDP. Comment-only projects: also `dev`.
3. Preflight scan (fail closed): run `python3 scripts/bin/jira-fix-adf.py scan "<full draft text>" --issue-key <ISSUE-KEY>`.
4. Build the pack once: `bash scripts/bin/jira-enrich.sh pack <ISSUE-KEY> payload.json` (single forbidden scan, single ADF build).
5. Apply:
   - SDCP / TDPQA: update custom fields (short ping optional). TDPQA fields unblock **QA Test**.
   - HSQA/AUT/other: one structured handoff comment (edit in place when `comment_id` exists)
6. Verify: TDPQA fields non-null (RCA/Impact/PrePost/AITDP); transition only when the workflow allows.

## Fast path (mandatory — avoids slow multi-step enrich)

**Root causes of slow JIRA updates:** see `cursor-bundle/memory/feedback_jira_enrich_fast_pack.md` (use one pack build + token cache + fields-reference).

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
python3 scripts/bin/jira-fix-adf.py project_mode TDPQA-180
# → mode=tdpqa_field_handoff | field_handoff | comment_handoff
```

| Mode | Projects | Where RCA / Impact live |
|------|----------|-------------------------|
| **`field_handoff`** | **SDCP** | Custom fields (`11137` / `11138` / `11901` …). Comment = short ping only. |
| **`tdpqa_field_handoff`** | **TDPQA** | Custom fields (`11999` RCA / `12008` Impact / `12007` PrePost / `12000` AITDP Dev remarks / `12001` Dev Accuracy / **`12004` Lead Accuracy** / **`12005` Lead Improvement Remarks** / `12009` Yes). **Mandatory for QA Test / transition.** **No Dev Test field** — always include `dev[]` in the pack; helper posts a companion comment headed **Dev Test Details** (+ optional **How to retest**). Short ping can be the comment lead-in. |
| **`comment_handoff`** | HSQA, AUT, other non-SDCP | **One structured handoff comment**. Set only the owners the project has. |

**Hard rules for agents:**

1. Call `project_mode` before drafting. Never send **SDCP** field IDs to TDPQA (and vice versa).
2. **Never invent a companion SDCP ticket** just to host fields — enrich the ticket the user named.
3. On **TDPQA**, fill the mandatory **fields** first (RCA/Impact/PrePost/AITDP). On `comment_handoff`, the handoff **comment** is the product — edit in place when `comment_id` exists.
4. Still run `scan` on every draft. No other JIRA keys, no GitHub URLs, no `@darpan`. Comment-only projects: no prod-ops SQL. **Machine validation:** SDCP/TDPQA field modes allow omit/short ping; `comment_handoff` requires rca+impact+dev. Tests: `scripts/lib/test_jira_fix_adf.py`.
5. **Strict ticket scope:** only the exact issue key. Do not cross-contaminate tickets.
6. **Language:** simple words QA can understand in ~30 seconds. Rule: `.cursor/rules/jira-tdpqa-qa-test-fields.mdc`.

### TDPQA field handoff (canonical — QA Test)

TDPQA Bug has mandatory fields for the **QA Test** transition. Fill them via `tdpqa_field_handoff` / `jira-enrich.sh pack|post`. Owners: `owners_tdpqa` (`11952` / `11953`).

Accuracy (`12001`) = **whole percent** (`80`), not SDCP’s 0–1 fraction.

Common failure mode: leaving fields empty and only commenting → **Transition failed** popup. See `cursor-bundle/memory/feedback_jira_tdpqa_comment_handoff.md`.

```bash
python3 scripts/bin/jira-fix-adf.py owners_tdpqa
# → customfield_11952 Dev Owner (Darpan), customfield_11953 QA Owner (Srikant)

# Preferred: field pack (unblocks QA Test)
cat > /tmp/tdpqa-payload.json <<'EOF'
{
  "rca": {
    "situation": "After rebooking, delayed payment interest was a little wrong.",
    "cause": "The system kept using the old rate on an open interest window.",
    "resolution": "When the rate changes, the old window is closed and a new one starts with the new rate."
  },
  "impact": [
    "Fixes delayed payment interest after rebooking or rate change.",
    "Does not change loans without a rate change.",
    "Please retest on a fresh rebooked loan."
  ],
  "pre": "NA",
  "post": "NA",
  "micro": ["accounting"],
  "aitdp_percent": 0.80,
  "aitdp_remarks": "Helped review the QA case and loan data, found the rate-window issue, applied the fix, and checked the result before sending to QA.",
  "aitdp_lead_percent": 0.80,
  "aitdp_lead_remarks": "Lead reviewed the parent-share fix and confirmed member totals and window dates match before QA.",
  "dev": [
    "Fresh rebooked loan — delayed payment interest follows the new rate. Result: Pass.",
    "Loan without a rate change — interest behaviour unchanged. Result: Pass."
  ],
  "qa_retest": [
    "After the accounting build is shared, retest on a fresh rebooked loan."
  ],
  "ping_comment": "@Srikant @Reema Fix is ready for QA. Dev Test Details below."
}
EOF
bash scripts/bin/jira-enrich.sh post TDPQA-180 /tmp/tdpqa-payload.json
```

Then:

1. `editJiraIssue` / `jira-enrich.sh post` — TDPQA fields `11999`/`12008`/`12007`/`12000`/`12001`/`12009`/`12006` + `assignee` + `owners_tdpqa`.
2. **Companion comment (mandatory):** pack always posts **Dev Test Details** from `dev[]` (TDPQA has no Dev Test custom field). Optional `qa_retest` / `qa_retest_steps` → **How to retest**. `ping_comment` is the short lead-in with mentions.
3. Transition toward **QA Test** when workflow allows.
4. Verify fields non-null via `getJiraIssue`; comment shows Dev Test Details.

**AITDP on TDPQA fields (mandatory):**

| Field | How to write |
|-------|--------------|
| JIRA as per AI TDP (`12009`) | Yes `12785` |
| AiTDP Dev Accuracy (`12001`) | **Whole percent** (`80`). Helper converts from `aitdp_percent` 0–1 |
| AiTDP remarks (`12000`) | 2–4 simple sentences: analysis + finding + fix + verify — **never** Cursor / IDE brand |
| AiTDP Lead Accuracy (`12004`) | **Whole percent** 0–100. Payload `aitdp_lead_percent` (0–1 or whole %); defaults to Dev accuracy if omitted |
| AiTDP Lead Improvement Remarks (`12005`) | Lead narrative; payload `aitdp_lead_remarks` (defaults to `aitdp_remarks` if omitted). **Mandatory for transition** (popup: Lead Accuracy + Lead Improvement Remark) |

Helper rejects pack without `aitdp_percent` + `aitdp_remarks`.

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
python3 scripts/bin/jira-fix-adf.py scan "<full draft text>" --issue-key <ISSUE-KEY>
# exit 2 = FORBIDDEN hits — rewrite until OK
```

**Child vs parent GL display (TDPQA-72):** Child settlement legs store `CG*` codes (e.g. `CG13336`). Do **not** strip `CG` and show parent GL names (`REG EMI-JLGDL- BI` / `INT ACC NOT DUE-JLGDL-AIR`) on child proof. Parent may use named GLs. Scan rejects `child_gl_renamed_to_parent_name` when Child text uses those parent names without any `CG####`. Memory: `feedback_child_cg_gl_vs_parent_named.md`.

Rationale + example forbidden drafts: `cursor-bundle/memory/feedback_jira_enrich_forbidden_scan_assignee.md`.

Reject and rewrite if any of these appear (case-insensitive):

`mfi_integration`, `mfi_release`, `feature/`, `ntest`, `registry.json`, `registry case`, commit SHA (8+ hex), `Processor`, `DAOService`, `apiName`, `N=1..20`, `member counts 1–20`, `\be2e\b`, `unit test`, `fixture`, `poisoned rows`, version `\b3.x.y(.z)?\b`, table/column names listed above, `RSCH_*`, `134xxx`, **`Cursor` / `Cursor IDE`** (capital-C brand only — verb "cursor" is fine), `github.com`, `PR #123`, `@darpan`, and any *other* JIRA issue key besides the target you passed via `--issue-key`.

For TDPQA/other comment handoffs only: SQL/DDL/DML snippets (e.g. `.sql`, `flyway_schema_history`, `UPDATE ... SET`, etc.) are rejected.

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

### Discussion / clarification comments (before a fix)

When the ask is **discuss with product/UI** (not "fill RCA for QA Test"), post **one short plain comment** — not an engineering RCA dump.

Memory: `cursor-bundle/memory/feedback_jira_discussion_comment_plain.md` (TDPQA-221).

**Bar:** readable in ~30 seconds. Product language only.

| Do | Do not |
|----|--------|
| What QA saw on screen | API / processor / class / template names |
| Why in business words (e.g. delayed payment interest vs interest-handling flag) | Error codes, payload dumps, SQL, branch/SHA |
| Who changes what (Web / Accounting / Product) | Long `##` section engineering write-ups |
| 2–4 clear questions + real ADF mentions | "GET returns bpd_amount" style jargon |

<bad-example>
```
## Are GET APIs already returning BPD?
getPartPrepaymentBPIAmount returns bpd_amount; validatePartPrepaymentAmount adds dpi_till_date…
```
</bad-example>

<good-example>
```
@Sudheer Pandey @Himanshu Tomar — quick discussion needed.

What QA saw: part prepayment failed on the reported loan when showing the new schedule even though overdue + fees + principal + charges matched the gross amount.

What we found: the loan also has a little delayed payment interest not yet billed. The interest-handling flag is only for broken-period interest, but the screen zeros delayed-payment interest when that flag is NO.

Who needs to change what: Web should always show and include that delayed-payment amount. Accounting money rule looks fine; optional clearer error text only.

Please confirm: (1) should that amount still be collected when interest handling is NO? (2) can UI take the screen fix?
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

### TDPQA fields (tdpqa_field_handoff) — simple language

Fill **RCA / Impact / Pre-Post / AITDP remarks + Accuracy** on the ticket. Use short plain sentences QA can read in ~30 seconds.

**Dev Test Details:** TDPQA Bug has **no** Dev Test custom field (unlike SDCP `11901`). Always pass `dev[]` in the pack — helper posts a companion comment headed **Dev Test Details** (ordered functional steps; each ends with `Result: Pass` / `Result: Fail` when run by dev). Optional `qa_retest` → **How to retest**. Do **not** leave QA without retest steps. Do **not** invent an SDCP ticket just to host Dev Test.

HSQA/AUT still use `comment_handoff` (structured comment) — see `handoff_comment` helper.

### Tone (all modes)

Write like a developer explaining to a teammate — natural, direct, confident. **Not** like an agent:

- No emoji, no "✓/→", no marketing words ("permanent fix", "no hacks", "100%")
- State what was wrong, what changed functionally, and what to retest — plainly

<bad-example>
Robotic ping with empty mandatory fields:
```
@Reema ready for QA.
```
</bad-example>

<good-example>
SDCP / TDPQA ping (fields already filled):
```
@Sudheer @Srikant done as per your last comment. Interest Original now shows total billed interest and Outstanding = Original − (Paid + Waived + Written Off). @Reema pls retest once the build is shared.
```
</good-example>

<good-example>
TDPQA RCA field (simple): “After rebooking, delayed payment interest was a little wrong. The system kept the old rate on an open window. We close that window and start a new one with the new rate.”
</good-example>

**Minimal fix (mandatory):** Read `.cursor/skills/minimal-fix/SKILL.md`. Impact Analysis **must** include: what is **not** changed, whether read-path dedupe was **rejected**, and post-deploy SQL for existing poison rows (not code guards for dirty data).

## Mentions / tagging (@ — mandatory for comments)

**Markdown `@Name` does NOT tag anyone** — it posts as plain grey text. Real tagging needs ADF `mention` nodes with the person's `accountId`:
In Jira UI these appear as `"[~accountid:<id>]"`.

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
- Never tag/comment-mention `@darpan` / `@Darpan Solanki` (enforced by `never_mention` in `mentions.json` + scan).
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

Do **not** send SDCP `customfield_11898` / `11137` / `11676` keys to TDPQA — use TDPQA IDs (`11999` / `12008` / `12007` / `12000` / `12001` whole %). Helper `tdpqa_field_handoff` maps the payload correctly.

Override owners only when the user names different people.

## When to run

- User says update JIRA / fill RCA / hand off ticket / enrich for QA retest
- **Only after** the fix commit is on the correct **origin** train branch (see Push gate below) — unless the user explicitly asks for draft-only / no-push handoff
- Ticket key `SDCP-*` **or** `TDPQA-*` (and similar non-SDCP keys)

## Push gate (mandatory before QA handoff — TDPQA-207 lesson)

Do **not** treat `origin/fix/<ticket>-…` alone as “pushed for QA” when the ticket’s reported train is an integration branch (e.g. `mfi_integration_v3.5.2.2`).

**Hard sequence:**

1. Identify the **reported train** from the ticket (Reported version / Environment tag / user ask) — e.g. `mfi_integration_v3.5.2.2`.
2. Prove the fix is on **`origin/<train>`** (DarpanSolanki), not only on a personal `fix/*` branch:
   ```bash
   git -C <service-repo> fetch origin
   git -C <service-repo> log -1 --oneline origin/<train>
   # tip must include the fix commit (merge-base / show path with the change)
   ```
3. If missing: cherry-pick/rebase onto `upstream/<train>` tip → **`git push -u origin <train>`** (never upstream/trusttai) → re-verify `origin/<train>`.
4. **Then** enrich JIRA / move to QA Test.

A feature-branch push (`origin/fix/…`) is fine for WIP review, but **QA handoff requires the train branch on origin**.

## Workflow

### Shared

0. **Push gate** — `origin/<reported-train>` contains the fix (or user waived).
1. **`project_mode <KEY>`** — `field_handoff` | `tdpqa_field_handoff` | `comment_handoff`.
2. **Read ticket** — `getJiraIssue` (status, existing fields, owners).
3. **Draft** — simple business RCA / Impact / Pre-Post / AITDP; scan forbidden tokens.
4. **Owners + assignee** — `owners` or `owners_tdpqa` matching the mode.
5. **Apply handoff** — fields (SDCP / TDPQA) **or** `handoff_comment` ADF (HSQA/AUT).
6. **QA Test transition** when available; verify field read-back.

### SDCP only (after step 3)

- Map MICRO Service; set Pre/Post; set AITDP Yes + fraction + remarks.
- `editJiraIssue` with RCA/Impact/Dev custom fields.
- Short ping comment with mentions (optional / if handoff to QA).

### TDPQA only (after step 3)

- Pack/post `rca` + `impact` + `pre`/`post` + AITDP + **`dev[]`** into TDPQA custom fields (`tdpqa_field_handoff`); pack fails closed without `dev[]`.
- Companion comment always includes **Dev Test Details** from `dev[]` (no Dev Test field on TDPQA). Optional `qa_retest` + short `ping_comment` lead-in.
- `editJiraIssue` also sets assignee + `owners_tdpqa` + Micro when known.
- Do **not** create an SDCP bug “for fields” unless the user asks.
- Empty mandatory fields → Transition failed; missing Dev Test comment → QA cannot retest cleanly.

**QA data caveat** (both modes): if earlier QA loans are already dirty from pre-fix builds, say so in Impact / retest bullet — retest on fresh loans; functional language only.

## Fields to update (every **SDCP** fix handoff)

For **TDPQA**, see [fields-reference.md](fields-reference.md) § TDPQA (IDs differ; Accuracy = whole %).

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

When a ticket is **reworked / reopened**, a prose-only Dev section is **not enough**. QA must be able to scan proof in ~30 seconds. Use **simple ADF tables** — one observation per row, short plain English, numbers in their own Expected / Actual cells.

**Never put commit IDs / SHAs in user-facing Dev Test.** Build/branch may be named if it helps QA pick the deployable. Exact SHA stays agent-internal unless the user explicitly asks.

### Required short tables

1. **Test data** — Parent / Child A / Child B (role + account only)
2. **Observation checks** — What QA checked | Account | Expected | Actual | Result
3. **UI checks** — Screen | What was checked | Result (one line each)
4. **How to retest** — 3–4 bullets max (fresh group, preconditions, what to look for)

### Wording rules (fail closed)

- No dense sentences packing multiple facts into one cell
- No jargon: avoid “reconciled”, “labd”, “EMI hijack”, harness flags, method names
- Prefer: “billing table”, “force-bill interest entry”, “EMI billing entry kept”, “same amount”
- One account / one check per row
- Mark untested scenarios explicitly — never imply Pass

### Good Observation checks template

| What QA checked | Account | Expected | Actual | Result |
|---|---|---|---|---|
| Accrued vs Original | Parent `<LAN>` | Same amount | Accrued `<n>`, Original `<n>` | Pass |
| Accrued vs Original | Child `<LAN>` | Same amount | Accrued `<n>`, Original `<n>` | Pass |
| Force-bill in billing table | Child `<LAN>` | Separate force-bill row; principal 0; EMI row kept | Interest `<n>`, principal 0; EMI principal `<n>` kept | Pass |
| Transaction amount vs principal | Parent `<LAN>` | Same amount | Amount `<n>`, Principal `<n>` | Pass |
| Extra amount | Parent `<LAN>` | Extra shown separately | Excess `<n>` | Pass |
| Parent force-bill | Parent `<LAN>` | Not required (settled in reschedule) | No parent force-bill | Expected |

### Good UI checks template

| Screen | What was checked | Result |
|---|---|---|
| Summary | Accrued and Original show the same interest | Pass |
| Overview | Status and payment values look correct | Pass |
| Statement | Force-bill interest entry is visible | Pass |

**Hard rule:** No **"Result: Pass"** unless the Observation checks table covers the **exact** QA fail mode with Expected vs Actual values.

**Presentation:** native ADF `table` nodes (not ASCII). Keep RCA/Impact brief so the tables stay the main scan target. Post via `addCommentToJiraIssue(contentFormat=adf)`; edit in place while the handoff is still newest.

**Ordering on reopened tickets:** developer proof must be the **latest** comment. If QA posted newer observations, post a **new** handoff after them.

**Status:** use **QA Retest** when exposed. TDPQA has no QA Retest transition — **report unavailable; do not guess** (never silently route through QA:Traige).

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

- [ ] **`project_mode` chosen** — SDCP=`field_handoff`; TDPQA=`tdpqa_field_handoff`; other=`comment_handoff` (no fake companion SDCP)
- [ ] **Forbidden-token scan PASS** — including AITDP remarks
- [ ] **No version/branch** in RCA / Impact / Dev / comments
- [ ] **No Cursor / IDE brand** in any JIRA text
- [ ] **Simple language** — QA can read fields in ~30 seconds
- [ ] **Assignee + project owners set** — SDCP `owners` **or** TDPQA `owners_tdpqa`
- [ ] **SDCP only:** AiTDP Yes + 0–1 fraction + remarks; MICRO; Pre/Post; fields `11137`/`11138`/`11901`
- [ ] **TDPQA only:** fields `11999`/`12008`/`12007`/`12000`/`12001`(whole %)/`12004` Lead Accuracy/`12005` Lead Remarks/`12009` filled; **`dev[]` companion comment** with Dev Test Details (required — no Dev Test field)
- [ ] **Rework / reopened ticket:** simple ADF tables in comment when useful (Test data, Expected/Actual); no commit SHA
- [ ] **QA Test / QA Retest transition** used if exposed; otherwise reported unavailable (never guess QA:Traige)
- [ ] **Human tone** — developer-to-QA
- [ ] No empty ADF paragraphs
- [ ] `getJiraIssue` read-back confirms fields + real mentions if commented

## Related

- Release mail paste: `.cursor/skills/release-details/SKILL.md`
- RCA email (Subject + body): `.cursor/skills/fix-rca-email/SKILL.md`
- Field ids + repo map: [fields-reference.md](fields-reference.md)
- Owners defaults: [owners-defaults.json](owners-defaults.json)
- Rule: `.cursor/rules/jira-tdpqa-qa-test-fields.mdc`
- Memory: `cursor-bundle/memory/feedback_jira_tdpqa_comment_handoff.md`
- Memory: `cursor-bundle/memory/feedback_jira_tdpqa_dev_test_comment.md` — TDPQA has no Dev Test field; pack requires `dev[]` companion comment
- Memory: `cursor-bundle/memory/feedback_jira_enrich_forbidden_scan_assignee.md`
- Memory: `cursor-bundle/memory/feedback_jira_aitdp_remarks_no_cursor_brand.md`
- Memory: `cursor-bundle/memory/feedback_jira_aitdp_effectiveness_fraction.md` — SDCP `%` write = 0–1 fraction; TDPQA Accuracy = whole %