---
name: workspace-autopilot
description: >-
  Mandatory entry for every task — user speaks plain English only; agents run
  super-machine (classify, preflight, trace, test, ship). User never runs scripts.
triggers:
  - any task
  - session start
  - substantive message
  - logs attached
requires: []
reads:
  - .cursor/workspace-intelligence-state.md
  - .cursor/workspace-ops-state.md
writes:
  - .cursor/.autopilot-state.json
feeds:
  - super-agent
  - autonomous-workspace-ops
  - workspace-close
scripts:
  - scripts/bin/super-machine.sh
  - scripts/bin/workspace-autopilot.sh
---

## Routing metadata

<!-- ported from Cursor skill frontmatter -->

- **triggers:** `any task`, `session start`, `substantive message`, `logs attached`
- **requires:** []
- **reads:** `.cursor/workspace-intelligence-state.md`, `.cursor/workspace-ops-state.md`
- **writes:** `.cursor/.autopilot-state.json`
- **feeds:** `super-agent`, `autonomous-workspace-ops`, `workspace-close`
- **scripts:** `scripts/bin/super-machine.sh`, `scripts/bin/workspace-autopilot.sh`

# Workspace autopilot

**The user does not run commands.** They describe the problem in plain English (+ logs optional). **You** run the workspace.

## First action on every user message

```bash
bash scripts/bin/super-machine.sh handle "<user request verbatim>"
```

Same as `workspace-autopilot.sh task "…"`. Output = classification, skills to load, steps already auto-run, directives.

## With log attachments

1. Read log/content in this turn first
2. Pull error codes, apiName, correlators (LAN, ext_ref, stan)
3. `super-agent trace <api> --fast` if apiName known
4. `agent-ops on-failure` / `novopay-logs.sh snap` if local repro needed
5. `db-local.sh` canned queries — never ask user to run SQL

## Mid-tab task changes

Autopilot tracks state in `.cursor/.autopilot-state.json`. **TASK SHIFT** → re-preflight + trace.

## Push without waiting for session end

Test PASS → hook → `mark-verified` → cooldown → `ship-and-continue`. User continues with next task.

## You must not

- Ask the user to run `ntest`, `kg-switch`, `workspace-close`, `agent-ops`, hygiene, or log paths
- Ask the user to confirm an expanded plan for RCA/analysis-only (only before **code edits**)
- Skip autopilot because session already started

## Classification → auto-runs → you do next

| Type | Auto-runs | You do next |
|------|-----------|-------------|
| TEST | preflight, before-test, trace | `ntest auto <api>`; money/disburse: column-value asserts required (`column_audit` / `acceptance.db_asserts`) — never Pass on HTTP 200 alone |
| BUG/RCA | preflight, trace --fast | logs, DB, orchestration XML, RCA → **OPTIONS BOARD L0–L3** then recommend |
| FIX+SHIP | trace, preflight | fix → test → `autopilot end` (board already shown at propose) |
| FEATURE | trace, preflight | kg flow + XML + impact → **OPTIONS BOARD L0–L3** |
| WORKSPACE | corroborate, max-pass | implement infra if asked |
| RELEASE | (skills) | release-details skill |
| OPS_SQL (prod/adhoc UPDATE, CRR, DTFC reset) | preflight | load `prod-ops-sql-impact` → answer “is contract-native FAIL enough?” → impact matrix → minimal UPDATEs (not local-archive by default) → print SQL path only (no IDE auto-open) |

**OPTIONS BOARD:** Autopilot injects `OPTIONS BOARD (mandatory after analysis): …` for analyse/RCA/Jira/perf plans. After analysis, always list L0–L3 (code options included when they exist); do not end with evidence-only next-step. Detail: `.cursor/rules/00-workspace-core.mdc` § Post-analysis OPTIONS BOARD.

## Task end

```bash
bash scripts/bin/workspace-autopilot.sh end
```

Runs: `kg-ensure-fresh` → `kg_watermark_gate --block-verified` → hygiene → (pending) `ntest validate` + `registry_companion_gate` + `ship-discipline` → `workspace-close`.

Money-path: post-ship knowledge gate still required inside close.

## Verify stack (agents only — user never runs)

```bash
bash scripts/bin/super-machine-smoke.sh
```
