# SDCP + TDPQA JIRA fields (novopay.atlassian.net)

## Project routing

| Project | Mode | RCA / Impact / Dev Test |
|---------|------|-------------------------|
| **SDCP** | `field_handoff` | Custom fields below (SDCP IDs) |
| **TDPQA** (Bug `11014`) | **`tdpqa_field_handoff`** | TDPQA custom fields (mandatory for **QA Test**) — see TDPQA section |
| Other non-SDCP (HSQA, AUT, …) | `comment_handoff` | One structured `handoff_comment` unless meta shows field IDs |

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

# TDPQA (field handoff — mandatory for QA Test)

Project: **TDPQA**. Issue type: **Bug** (`11014`).

**QA Test transition** requires RCA / Impact / Pre-Post / AI TDP remarks filled on the ticket
(workflow validator). Use **simple business language**. Rule: `.cursor/rules/jira-tdpqa-qa-test-fields.mdc`.

## Fix handoff fields (TDPQA IDs — not SDCP)

| Display name | Field key | Type | Notes |
|--------------|-----------|------|-------|
| RCA | `customfield_11999` | ADF | 3 short paragraphs: situation / cause / resolution |
| Impact Analysis Details | `customfield_12008` | ADF | Bullets: fixed / unchanged / retest hint |
| Pre /Post Deployment Scripts | `customfield_12007` | ADF | Pre + Post lines; `NA` when none |
| AiTDP Dev Improvement Remarks | `customfield_12000` | ADF | How AI helped — never Cursor brand |
| AiTDP Dev Accuracy | `customfield_12001` | float | **Whole percent** (`80` for 80%). **Not** SDCP’s 0–1 fraction |
| AiTDP Fix Quality Grade | `customfield_12002` | string | `A` / `B` / `NA`. Payload `aitdp_fix_grade` (default `A`). **Required for QA Test** |
| AiTDP Fix Quality Score (Number) | `customfield_12003` | float | Payload `aitdp_fix_score` (defaults to Dev Accuracy). **Required for QA Test** |
| AiTDP Lead Accuracy (Number 0–100) | `customfield_12004` | float | **Whole percent**. Payload `aitdp_lead_percent`; defaults to Dev accuracy. **Required for transition** |
| AiTDP Lead Improvement Remarks | `customfield_12005` | ADF | Payload `aitdp_lead_remarks`; defaults to `aitdp_remarks`. **Required for transition** |
| JIRA As per AI TDP Temp | `customfield_12009` | multicheckboxes | Yes=`12785` when AI assisted |
| Micro Service | `customfield_12006` | multicheckboxes | Accounting=`12770` |
| Assignee | `assignee` | user | Darpan |
| Dev Owner | `customfield_11952` | people | via `owners_tdpqa` |
| QA Owner | `customfield_11953` | people | via `owners_tdpqa` |
| Fix Version | `customfield_11951` | labels | often set by QA — do not invent in text |

```bash
python3 scripts/bin/jira-fix-adf.py project_mode TDPQA-180
# → mode=tdpqa_field_handoff

bash scripts/bin/jira-enrich.sh pack TDPQA-180 payload.json
bash scripts/bin/jira-enrich.sh post TDPQA-180 payload.json
```

Payload: `rca` + `impact` + `pre`/`post` + `aitdp_percent` (0–1 → whole % on `12001`) + `aitdp_remarks` + **`aitdp_fix_grade` / `aitdp_fix_score`** (`12002`/`12003`; default `A` + Dev Accuracy) + **`aitdp_lead_percent` / `aitdp_lead_remarks`** (`12004`/`12005`; default to Dev AITDP) + **`dev[]` (required)** + optional `qa_retest` / `ping_comment` + optional `micro`.

**Dev Test Details:** TDPQA has **no** Dev Test custom field (SDCP uses `11901`). Pack **requires** `dev[]` and always posts a companion comment headed **Dev Test Details** (ordered functional steps). Optional `qa_retest` → **How to retest**. `ping_comment` is the short mention lead-in only.

Do **not** send SDCP field IDs to TDPQA. Do **not** invent a twin SDCP ticket unless the user asks.

Transition to **QA Test** requires the full set non-null: RCA, Impact, Pre/Post, Micro, Dev Accuracy + Dev Remarks, **Fix Quality Grade + Score**, Lead Accuracy + Lead Remarks, AI TDP Yes. Never use **QA:Traige** as a substitute for QA Retest.