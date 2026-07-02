---
name: workspace-hygiene
description: >-
  Clutter audit + cleanup. Run at session end, after ship, or when scratch grows.
  Keeps minimal files — merge into existing scripts/registry, never duplicate docs.
triggers:
  - session end
  - ship
  - task done
  - clutter
  - hygiene
requires: []
reads:
  - .cursor/rules/workspace-hygiene.mdc
writes: []
feeds:
  - super-agent
  - capture-proof
scripts:
  - scripts/bin/workspace-hygiene.sh
  - scripts/bin/ship-knowledge-gate.sh
---

# Workspace hygiene

**One command:** `bash scripts/bin/workspace-hygiene.sh`  
**Auto-clean on ship:** `ship-knowledge-gate.sh` runs `--gate` then `--clean` if needed.

## When (mandatory)

| Moment | Action |
|--------|--------|
| Task done / ship PASS | `workspace-hygiene.sh --clean` (also in knowledge gate) |
| Session start | Hooks warn if `hooks.json` missing or scratch cluttered |
| Before commit | No new markdown/SQL in repo root or `.cursor/` — use `scripts/scratch/<task>/` |

## Merge discipline (minimal files)

1. **Prefer** extend `registry.json`, `agent-ops.sh`, `super-agent.sh` — not new one-off scripts.
2. **Thin wrappers** (`exec python3 …`) stay — stable CLI names.
3. **Skills** = short routing; **rules** (`.mdc`) = enforcement. Do not duplicate full checklists in both.
4. **Scratch** = delete when task closes; reusable SQL → `scripts/sql/adhoc/` only if reused twice.

## Self-learning tie-in

After hygiene clean on ship: learning bus already updated by `post-ntest-intel-sync` / `enrichment-sync` — do not add parallel state files.

## Verify

```bash
bash scripts/bin/workspace-hygiene.sh          # audit
bash scripts/bin/workspace-hygiene.sh --clean  # fix safe clutter
python3 cursor-bundle/kg/bin/kg.py validate    # KG intact after clean
```
