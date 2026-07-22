<!-- VERBATIM archive of former alwaysApply `.cursor/rules/workspace-autopilot.mdc`. Do not soften. Edit thematic rules; keep this as mandate proof. -->

# Workspace autopilot (mandatory)

The workspace is **self-driving**. The user does **not** run `workspace-close`, `kg-switch`, `ntest`, or health scripts — **agents and hooks do**.

## On every substantive user message (first action)

```bash
bash scripts/bin/workspace-autopilot.sh task "<paste user request one line>"
```

- Follow printed **skills** and **agent directives**
- Do **not** ask the user to run scripts
- Do **not** use the old expansion confirmation gate — autopilot classifies and preflights; proceed to investigation/fix unless user said **discuss only** / **no code**

## What runs automatically (no user action)

| When | What |
|------|------|
| **sessionStart** hooks | KG sync (fast if fresh), intel hub, autopilot health |
| **First agent turn** | `workspace-autopilot.sh task` (preflight, kg validate, orient if API) |
| **before test** | `agent-ops.sh before-test <api>` (via autopilot TEST plan) |
| **after ship-path edit** | pending-ship fingerprint |
| **after ntest/gradle/commit** | intel sync hook |
| **agent stop** | `workspace-autopilot.sh end` — hygiene + auto-close pending ship work |
| **git push** | pre-push checklist + post-push enrichment |

## Task end (agent, before saying "done")

```bash
bash scripts/bin/workspace-autopilot.sh end
```

Money-path fixes still need post-ship knowledge gate content (changelog, gaps) — `workspace-close` runs inside `end` when pending.

## Code edits

`discuss-before-updating.mdc` still applies: propose + wait for **implement/go ahead** unless user already asked to ship/fix.

## Escape hatches (rare)

- `WORKSPACE_AUTOPILOT_NO_AUTO_CLOSE=1` — stop hook nudges instead of auto-close
- `KG_STRICT=1` — stale KG blocks queries

## Skill

`.cursor/skills/workspace-autopilot/SKILL.md` · engine: `scripts/testing/workspace_autopilot.py`
