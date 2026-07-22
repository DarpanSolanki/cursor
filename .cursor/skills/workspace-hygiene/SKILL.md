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
  - .cursor/rules/00-workspace-core.mdc
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
bash scripts/bin/workspace-hygiene.sh --clean  # fix safe clutter (+ local YB orphan pg_temp_*)
bash scripts/bin/db-local-hygiene.sh           # audit orphan CREATE TEMP leftovers on :5433
bash scripts/bin/db-local-hygiene.sh --clean   # DROP orphan pg_temp_* / pg_toast_temp_* (local only)
bash scripts/bin/workspace-disk-clean.sh       # audit archived service logs (~300MB typical)
bash scripts/bin/workspace-disk-clean.sh --clean
bash scripts/bin/super-agent.sh clean --apply  # disk + fast-sync
python3 cursor-bundle/kg/bin/kg.py validate    # KG intact after clean
```

## Local Yugabyte temp schemas

Local scripts (`CREATE TEMP TABLE` for disburse reset / DPI purge / DCF patches) leave `pg_temp_<uuid>_*` schemas on Yugabyte when the session exits without dropping them (crash, kill, or missing end-of-script `DROP`). These are not app data — `db-local-hygiene.sh --clean` drops them (also via `workspace-hygiene.sh --clean`). Keep `mfi_accounting.temp_unique_gl_code_office_id` (real empty staging table). Prefer end-of-script `DROP TABLE IF EXISTS` over `ON COMMIT DROP` unless the whole script is one explicit transaction.
