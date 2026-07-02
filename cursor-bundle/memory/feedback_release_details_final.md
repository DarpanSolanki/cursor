---
name: feedback_release_details_final
description: "Canonical release-details format — user-approved detail level. Triggers: release details, please release details. Skill: .cursor/skills/release-details/SKILL.md"
metadata:
  node_type: memory
  type: feedback
---

When the user asks for **release details**, produce a **paste-ready** block for release mail or JIRA — structured, plain language, **no tables**, **no code jargon**.

## User detail level (always apply)

| Section | Depth | Tone |
|---------|-------|------|
| **RCA** | **Short** — ~3–5 lines max | What broke, why, when; name prod LANs; one line on correct behaviour after fix |
| **Impact analysis** | **Short** — ~3–6 bullets total | Affected / Not affected / Note (stuck loans, manual fix) |
| **Dev testing scenarios done** | **More detail** — 4–5 scenarios | Enough that QA sees dev already tested; not code-level |
| **QA retest** | Only if asked | Mirror dev scenarios with Pass if / Fail if |

**RCA + impact = concise.** **Dev scenarios = clearer** (Setup / Action / Expected / Result). Do not make all sections equally long.

## Dev scenario line guide (per item)

- **Setup:** Starting state — loan, group, foreclosure/batch status, which LAN
- **Action:** What dev did (reviewed prod data, walked the flow, verified build) — plain words
- **Expected:** What should happen after the fix
- **Result:** Pass | Pass (logic review) | Not run in UAT — never overclaim

Include: prod/JIRA sample match, main bug path, approved-path regression, happy-path payment regression, build check.

## Header (always)

```
Fix: <one line>
JIRA: <all keys>
Reported LANs: <every LAN from every linked ticket>
```

Pull LANs from **all** linked JIRAs before writing (e.g. SDCP-8102 had 6000000010 and 6000301987; SDCP-10400 had 6000000010).

## Paste rules

- **No markdown tables** — they break on JIRA/mail paste
- **No code:** APIs, classes, git branch/sha, orchestration
- Use app words: foreclosure freeze, active, pending, expired, collection batch
- Blank line between major sections; bullets and numbered lists only
- Copy-paste friendly — QA should understand what to test without reading code

## Workflow

1. Read linked JIRAs for LANs, groups, symptoms
2. Pinpoint RCA in code/DB (agent-only); translate to business language
3. Output for user to paste — **never write to Jira**

Skill: `.cursor/skills/release-details/SKILL.md`  
Rule: `.cursor/rules/release-details.mdc`

## Example calibration (foreclosure batch expiry — SDCP-10400 / SDCP-8102)

RCA: 3 lines + cause. Impact: 3 bullets. Dev: 5 scenarios with Setup/Action/Expected/Result — prod LAN 6000000010 in scenario 1; note 6000301987 in header as second bank-reported LAN.
