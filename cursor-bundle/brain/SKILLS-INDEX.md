# Skills index — composition map

> Skills share facts via **`cursor-bundle/flow-test/learning_bus.jsonl`**, not by calling each other in code.  
> Machine manifest: `cursor-bundle/brain/skills-manifest.json`

## Session router

| Step | What |
|------|------|
| 1 | Load **workspace-router** skill |
| 2 | Read `.cursor/workspace-intelligence-state.md` (hub) |
| 3 | Run `scripts/bin/agent-router.sh classify "<task>"` |
| 4 | Follow printed skill chain + scripts |

## Skills

| Skill | Use when | Key scripts |
|-------|----------|-------------|
| **workspace-router** | Every session / new task | `agent-router.sh`, `write-intelligence-hub.sh` |
| **autonomous-workspace-ops** | Tests, sanity, ntest, batch | `agent-ops.sh`, `ntest.sh`, `novopay-logs.sh` |
| **capture-proof** | After fix + test on money path | `capture-flow.sh`, `ship-knowledge-gate.sh` |
| **reuse-queries-java-filter** | Before new `@Query` | — |
| **concise-email** | Draft stakeholder email | — |

## Pipelines

### RCA (bug / incident)
```
agent-router → kg orient → footprint show → contract list --money → XML → db-local
Optional: brain-gap-capture.sh → brain-triage.sh
```

### Fix + ship (money path)
```
fix → agent-ops before-test → ntest → capture-flow.sh → changelog-add --kg-flow
→ sync-intelligence --quick → ship-knowledge-gate.sh
```

### Branch / intelligence sync
```
sync branches → platform-scan.sh --with-kg → write-intelligence-hub.sh
```

## Learning bus event types

| Type | Writer |
|------|--------|
| `scan_complete` | `platform_scan.py` |
| `test_pass` / `test_fail` | `workspace-sanity.sh`, ntest hooks |
| `gotcha` | `test-learn.sh` |
| `fix_captured` | `capture-flow.sh` |
| `gap_discovered` | `brain-gap-capture.sh` |
| `fix_shipped` | changelog kg-flow |
| `hub_refresh` | `intelligence_hub.py` |
| `sanity_pass` / `sanity_fail` | `workspace-sanity.sh` |
