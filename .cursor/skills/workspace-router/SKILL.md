---
name: workspace-router
description: >-
  Session entry for sliProd: read intelligence hub, classify task, load the right
  skill chain. Use at session start, new incidents, or when unsure which skill applies.
triggers:
  - session start
  - any substantive task
  - orient
requires: []
reads:
  - cursor-bundle/memory/MEMORY.md
  - .cursor/workspace-intelligence-state.md
  - cursor-bundle/brain/CANONICAL-MAP.md
  - cursor-bundle/brain/skills-manifest.json
writes: []
feeds:
  - autonomous-workspace-ops
  - capture-proof
---

# Workspace router

## Mandatory order

1. Read `cursor-bundle/memory/MEMORY.md`
2. Read `.cursor/workspace-intelligence-state.md` (regenerate: `bash scripts/bin/write-intelligence-hub.sh`)
3. `python3 cursor-bundle/kg/bin/kg.py validate` — abort if fail
4. Run classification:

```bash
bash scripts/bin/agent-router.sh classify "<user task in one line>"
```

5. Load skills listed in router output **before** grepping source.

## Task → skill chain

| Classification | Load skills | Run first |
|----------------|-------------|-----------|
| BUG / RCA | workspace-router → ops (logs) | `kg orient <api>` |
| TEST / SANITY | autonomous-workspace-ops | `agent-ops.sh before-test <api>` |
| FIX + SHIP | ops → capture-proof | test then `capture-flow.sh` |
| FEATURE | workspace-router | `kg flow` + orchestration XML |
| DOCS / KB | workspace-router | CANONICAL-MAP only |

## Proof discipline

- Every claim: file path + line, SQL output, or log excerpt from **this turn**
- KG answers: structure only — verify orchestration XML + `scripts/db-local.sh`
- If unverified: state `NOT VERIFIED — needs runtime confirmation`

## Hub refresh

After branch checkout, scan, or shipped fix:

```bash
bash scripts/bin/sync-intelligence.sh --quick
bash scripts/bin/write-intelligence-hub.sh
```
