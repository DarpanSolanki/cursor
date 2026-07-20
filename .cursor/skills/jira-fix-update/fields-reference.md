# SDCP + TDPQA JIRA fields (novopay.atlassian.net)

## Project routing

| Project | Mode | RCA / Impact / Dev Test |
|---------|------|-------------------------|
| **SDCP** | field handoff | Custom fields below |
| **TDPQA** (Bug `11014`) | **comment handoff** | No RCA/Impact/Dev fields — use `jira-fix-adf.py handoff_comment` |
| Other non-SDCP | comment handoff | Same as TDPQA unless metashows the SDCP fields |

```bash
python3 scripts/bin/jira-fix-adf.py project_mode <ISSUE-KEY>
python3 scripts/bin/jira-fix-adf.py pack <ISSUE-KEY> payload.json   # preferred — all fields + one scan
bash scripts/bin/jira-enrich.sh post <ISSUE-KEY> payload.json       # shell REST fallback
```

---

# SDCP JIRA custom fields

Project: **SDCP** (SLI During CUG / POST CUG). Issue type: **Task** (`10428`) / **Bug** (`10429`).

Refresh field list when JIRA admin changes screens:

```text
getJiraIssueTypeMetaWithFields(cloudId=novopay.atlassian.net, projectIdOrKey=SDCP, issueTypeId=10428)
```

## Fix handoff fields

| Display name | Field key | Type | Notes |
|--------------|-----------|------|-------|
| RCA | `customfield_11137` | textarea → ADF | Business language; 3 short paragraphs; **no version/branch** |
| Impact Analysis Details | `customfield_11138` | textarea → ADF | Bullet list; 4 items typical |
| Dev Test Details | `customfield_11901` | textarea → ADF | **Functional QA retest steps** + optional post-test evidence — not harness dumps |
| Test scenarios executed | `customfield_11937` | textarea → ADF | Short labels; mirror dev scenarios |
| Test results (Pass/Fail) | `customfield_11938` | textarea → ADF | One line summary |
| MICRO Service | `customfield_11337` | multicheckboxes | `[{"id": "<optionId>"}]` — see mapping below |
| Pre deployment and Post deployment script | `customfield_11336` | textarea → ADF | **One field** — use Pre/Post sub-lines; `NA` when none |
| Assignee | `assignee` | user | Default Darpan Solanki `5e9d51241067100c195f7b12` |
| Dev Lead | `customfield_11543` | user(s) | From [owners-defaults.json](owners-defaults.json) |
| Dev Owner | `customfield_11898` | user(s) | Darpan |
| Product Owner | `customfield_11005` | user | Sudheer Pandey |
| QA Owner | `customfield_11899` | user(s) | Srikant Sulpule |
| Reviewer | `customfield_10160` | user | Navaneet Kumar |
| Approvers | `customfield_10003` | user(s) | Navaneet Kumar |
| JIRA As per AI TDP Temp | `customfield_11477` | multicheckboxes | Yes `12039` / No `12040` / Not Applicable `12709` — Yes when AI assisted |
| AITDP Effectiveness as % | `customfield_11676` | float (0–1 fraction) | **Write `0.75` for 75%** — UI multiplies by 100. Never write `75` (shows **7500%**). Peer proof: SDCP-11013=`0.78`. After write: if raw `> 1`, wrong scale — fix before close |
| AITDP Remarks | `customfield_11677` | textarea → ADF | **How the agent helped** (analysis + RCA + impl + verify), 2–4 sentences — **never** `Cursor` / IDE brand |

## Assignee + owners (mandatory)

Every enrich must set standard `assignee` **and** merge owner custom fields:

```bash
python3 scripts/bin/jira-fix-adf.py assignee
python3 scripts/bin/jira-fix-adf.py owners
```

Defaults live in [owners-defaults.json](owners-defaults.json). Do not leave Dev/QA owner fields null after a handoff.

## Forbidden-token scan (mandatory)

```bash
python3 scripts/bin/jira-fix-adf.py scan "<draft>"
```

Exit 2 = rewrite. Full token list + BAD/GOOD examples: [SKILL.md](SKILL.md).

## AITDP fields (mandatory, honest)

AI Tool Development Productivity metrics — audited. Fill all three:

- `customfield_11477` = `[{"id": "12039"}]` (Yes) when AI assisted the work.
- `customfield_11676` = **0–1 fraction** (e.g. `0.75` → UI **75%**). Dev's call for the percent; convert before write (`75` → `0.75`). Never write whole-number percent.
- `customfield_11677` = ADF **agent-help narrative** (2–4 sentences): how analysis was done, root cause found, fix chosen, what the developer verified. Prefer "AI-assisted RCA…" — **never** name Cursor / Cursor IDE / product brand. No branch/SHA/processor/ntest. Full rules + BAD/GOOD: [SKILL.md](SKILL.md) § AITDP fields.

Forbidden-token scan also rejects capital-C `\bCursor\b` / `Cursor IDE` (verb "cursor" OK).

## Dev test evidence (post-test check)

Mandatory for money-path / loan-closure fixes. After developer verification **Pass**, query observable outcomes and add one Dev Test Details item in **functional** language.

**Include:** ticket-reported or fresh retest loan account number(s), loan status, principal paid/waived/pending, total outstanding, posting amounts (functional words — not table/column/txn codes / ntest).

**Skill:** `.cursor/skills/jira-fix-update/SKILL.md` § Dev test evidence

## MICRO Service option IDs

| Checkbox label | Option id |
|----------------|-----------|
| Task | 11840 |
| Inital Set up | 11841 |
| Payments | 11842 |
| Accounting | 11843 |
| LOS | 11844 |
| Actor | 11845 |
| BPMN | 11846 |
| Reporting | 11847 |
| Lib | 11848 |
| sli-android | 11849 |
| Batch | 11850 |
| API Gateway | 11851 |
| Approval | 11852 |
| Audit | 11853 |
| Authorization | 11854 |

### Repo → checkbox (common)

| Workspace repo folder | Check |
|-----------------------|-------|
| `trustt-platform-accounting` | Accounting |
| `trustt-platform-los` | LOS |
| `trustt-platform-payments` | Payments |
| `trustt-platform-actor` | Actor |
| `trustt-platform-batch` | Batch |
| `trustt-platform-api-gateway` | API Gateway |
| `trustt-platform-lib` | Lib |
| `trustt-platform-task` | Task |
| `trustt-platform-approval` | Approval |
| `trustt-platform-audit` | Audit |
| `trustt-platform-authorization` | Authorization |

Multiple services touched → check all that apply. Lib change that ships only inside a service still check **Lib** + consuming service if both repos changed.

## Pre / Post deployment (single field)

JIRA has **one** textarea (`customfield_11336`), not two separate fields. Always use this structure:

```text
Pre deployment: NA
Post deployment: NA
```

When scripts exist, replace `NA` with a one-line purpose per section; SQL/scripts belong here, not in RCA/Impact/Dev.

## MCP call

```text
editJiraIssue(
  cloudId=novopay.atlassian.net,
  issueIdOrKey=SDCP-12345,
  contentFormat=adf,
  fields={ assignee, owners..., customfields... }
)
```

**Never** use `contentFormat: markdown` on textarea custom fields — API rejects it.

## ADF rules (spacing)

- **Do not** emit empty `paragraph` nodes (`content: []`) — causes large gaps in JIRA UI.
- RCA: 3 `paragraph` blocks max (situation, cause, resolution).
- Impact: one `bulletList`.
- Dev Test Details: one `orderedList` with Result in each item.
- Pre/Post: two `paragraph` lines or a 2-item `bulletList`.

Helper: `scripts/bin/jira-fix-adf.py`

---

# TDPQA (comment handoff)

Project: **TDPQA**. Issue type: **Bug** (`11014`). Simplified Jira — **no** SDCP RCA / Impact / Dev Test / MICRO / Pre-Post / AITDP custom fields.

## Writable fields on handoff

| Display name | Field key | Notes |
|--------------|-----------|-------|
| Assignee | `assignee` | Darpan |
| Dev Owner | `customfield_11952` | people — Darpan via `owners_tdpqa` |
| QA Owner | `customfield_11953` | people — Srikant via `owners_tdpqa` |
| Fix Version | `customfield_11951` | labels (already set by QA often) — do not invent versions in comment text |

## Canonical handoff = one ADF comment

Build with:

```bash
python3 scripts/bin/jira-fix-adf.py handoff_comment <<'EOF'
{ "lead_in": "@Srikant …", "rca": {…}, "impact": […], "dev": […], "pre": "NA", "post": "NA", "service": "Accounting", "result": "…", "aitdp_percent": 0.75, "aitdp_remarks": "AI-assisted RCA…" }
EOF
```

Sections (bold labels): **RCA**, **Impact**, **Dev test / QA retest**, **Test result** (optional), **Service** (optional), **Pre / Post deployment**, **AITDP** (mandatory — Yes + effectiveness % + remarks).

`aitdp_percent`: pass **0–1 fraction** (`0.75`); comment displays `75%`. Helper exits 2 if AITDP keys missing.

Do **not** create a twin SDCP ticket only to host SDCP fields unless the user asks.

Transition: use TDPQA workflow (e.g. toward `QA:Traige`) after the handoff comment is up.