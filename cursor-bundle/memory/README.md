# Memory index (`cursor-bundle/memory/`)

Standing corrections and workflow discipline. **Read `MEMORY.md` first** — it links every file below.

| Prefix | Purpose | Count |
|--------|---------|-------|
| `feedback_*` | User-corrected rules (boundary, RCA, git, hygiene, …) | 22 |
| `reference_*` | Stable setup pointers (KG, hooks, workspace, gradle) | 6 |
| `project_*` | Capability notes | 1 |

**Do not** duplicate these into new markdown files. Update the relevant `feedback_*` or brain doc in the same turn.

## Quick pointers

- **KG:** `reference_system_kg.md` → `cursor-bundle/kg/LAYERS.md`
- **Hooks:** `reference_enforcement_hooks.md` → `.cursor/hooks.json`
- **RCA:** `feedback_config_resolution_rca.md` → `kg why <request>`
- **Changelog:** `feedback_changelog.md` → `cursor-bundle/brain/changelog/CHANGELOG.md`
- **WIP gate:** `feedback_keep_knowledge_current.md`

## Hygiene

- Paths use `/home/darpan/Documents/sliProd/` and `cursor-bundle/` — **not** legacy `claude/` or `/home/darpan/Documents/sliProd/`.
- Feedback files are **not** indexed into KG; brain docs + curated jsonl are.
