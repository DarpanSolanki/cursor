---
name: release-details
description: >-
  Paste-ready release mail + auto-push. Internal full impact gate (KG, flows, state)
  before paste — gate is agent-only, NOT in JIRA body. Memory: feedback_release_details_final.md
triggers:
  - release details
  - please release details
  - release mail
  - QA handoff
requires:
  - reuse-queries-java-filter
reads:
  - cursor-bundle/memory/feedback_release_details_final.md
  - cursor-bundle/memory/feedback_qa_handoff_package.md
  - cursor-bundle/memory/feedback_minimal_fix_impact_gate.md
writes: []
---

# Release details (final)

Read **`cursor-bundle/memory/feedback_release_details_final.md`** — canonical **paste** format (do not change detail level).

## Two layers (do not mix)

| Layer | Audience | Content |
|-------|----------|---------|
| **Paste body** | QA / release mail / JIRA | Fix, JIRA, LANs, RCA, Impact, Dev scenarios — plain language, current format is **best** |
| **Impact gate + verification** | Agent chat / end-of-turn only | KG, callers, orchestration, every impacted flow tested, state safety |

**Never** put KG references, grep lists, apiNames, or “full impact analysis” methodology in the paste body.

## Full impact gate (mandatory before paste)

Run **`feedback_release_details_final.md` § Full impact gate** when user asks for release details or before closing a shipped fix:

1. **KG** — `validate`, `fresh`, `orient` / `flow` / `why` / `cases` on each touched apiName (reference only; XML + code + DB decide)
2. **Usage** — grep all callers of changed processors, services, DAO methods, EC keys
3. **Orchestration** — read XML for each impacted request (API, batch, consumer, retry)
4. **Flows tested** — every impacted flow has a dev-scenario line or explicit NOT VERIFIED; build green minimum
5. **State safety** — correct status transitions; system maintains state; no wrong updates on replay/happy path/adjacent flows
6. **Gates** — minimal-fix, no-flow-break, reuse-queries if repository touched

Then write the **paste body** — translate findings into short Impact bullets and Dev scenarios only.

## Quick rules (paste body only)

- **RCA + impact:** concise (~3–5 lines / ~6 bullets).
- **Dev scenarios:** Setup / Action / Expected / Result — **~1–2 extra lines per field** vs RCA; simple language, not code.
- **All LANs** from every linked JIRA in header.
- **No tables.** No code jargon in paste body. Never write to Jira.
- **Before implement:** `.cursor/skills/reuse-queries-java-filter/SKILL.md` — grep repository first; no new `@Query` without documented hot-path reason.

## Auto-push (mandatory — do not wait for separate “push” command)

When release details are produced **and** there are **unpushed fix commits** in the affected service repo:

1. **Before push:** `./gradlew compileJava` or `./gbuild.sh` green in that repo; correct branch; only intended files in commit.
2. **Train sync-first:** If branch is `mfi_integration_vX.Y.Z`, fetch origin+upstream, base on `upstream/<train>` tip, reconcile unique origin commits (`feedback_train_branch_sync_origin_upstream.md`) — never push from stale origin-behind-upstream.
3. **Push** from the **service repo root** (not workspace root): `git push origin <branch>` / `bash scripts/bin/push-origin.sh` (DarpanSolanki fork per `feedback_darpan_git_via_darpansolanki.md`).
4. **Do not** push to `trusttai` upstream unless user explicitly asks.
5. **After push:** prepend brain CHANGELOG (`changelog-add.sh --kg-flow` for money-path fixes), append `.cursor/changelog.md`, state in chat: `Pushed: <repo> <branch> @ <short sha>`.
6. If nothing to push, say `Already on origin` — still deliver release details.

User should **not** have to say “push” after “release details” when fixes were part of the same task.

## Default output (paste body — unchanged)

```text
Fix: <one line>
JIRA: <keys>
Reported LANs: <comma-separated>
Release branch: <branch> (<service>)

RCA
...

Impact analysis
...

Dev testing scenarios done
1. ...
   Setup: ...
   Action: ...
   Expected: ...
   Result: Pass | Pass (logic review) | Not run in UAT
```

Add **What QA should test** only if user asks.

## End-of-turn (agent only — NOT in paste body)

```text
Pushed: <repo> | <branch> | <sha> | origin

Impact verification (agent only):
- KG: <orient/flow/cases apiNames checked>
- Callers: <processors/DAO/keys — count or paths>
- Flows verified: <list each impacted flow + Pass | NOT VERIFIED>
- State safety: <transitions confirmed | risks>
- Open: <prod patch, uncommitted, test gaps>

Knowledge updated: ...
Post-ship gate: PASS | FAIL
```
