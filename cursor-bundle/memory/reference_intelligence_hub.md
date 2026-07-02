# Intelligence hub + skill mesh

**Hub (regenerate every session / after sync):** `bash scripts/bin/write-intelligence-hub.sh` → `.cursor/workspace-intelligence-state.md`

**Router:** `bash scripts/bin/agent-router.sh classify "<task>"`

**Sanity:** `bash scripts/bin/workspace-sanity.sh` (quick) · `--full` includes smoke-workspace

## Learning bus

Append-only: `cursor-bundle/flow-test/learning_bus.jsonl`

| Event | Writer |
|-------|--------|
| `gotcha` | `test-learn.sh` |
| `scan_complete` | `platform_scan.py` |
| `fix_captured` | `capture-flow.sh` |
| `gap_discovered` | `brain-gap-capture.sh` |
| `sanity_pass` / `sanity_fail` | `workspace-sanity.sh` |

## Skills

Index: `cursor-bundle/brain/SKILLS-INDEX.md` · Manifest: `skills-manifest.json`

Load **workspace-router** first; it points to ops / capture-proof / reuse-queries as needed.

## Proof gate (all analysis)

1. `kg validate` before knowledge queries
2. Orchestration XML + processors for behaviour
3. `scripts/db-local.sh` for DB facts
4. Mark `NOT VERIFIED` without this-turn evidence
