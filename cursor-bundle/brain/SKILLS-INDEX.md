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
| **accounting-knowledge** | Accounting money-path depth beyond thin `accounting.md` | topic files under skill |
| **architect-thinking** | Architect patterns beyond thin `architect-thinking.md` | topic files under skill |
| **workspace-gates-reference** | Verbatim pre-U3 alwaysApply archives | — |
| **autonomous-workspace-ops** | Tests, sanity, ntest, batch | `agent-ops.sh`, `ntest.sh`, `novopay-logs.sh` |
| **capture-proof** | After fix + test on money path | `capture-flow.sh`, `ship-knowledge-gate.sh` |
| **pr-review** | Proof-backed, zero-speculation review of a fresh PR head | `pr-review.sh` |
| **open-final-file** | Share forwardable path (no auto IDE open); `--open` only if user asks | `open-final.sh` |
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

### Pull-request review
```
agent-router → pr-review.sh freshness proof → branch/train provenance → domain lenses
→ falsify every finding → compile/runtime evidence when required
→ verdict + developer response
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

## Upgrade 2 skills
- `.cursor/skills/accounting-knowledge/` — on-demand accounting deep knowledge
- `.cursor/skills/architect-thinking/` — on-demand architect patterns
