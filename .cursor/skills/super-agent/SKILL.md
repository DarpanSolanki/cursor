---
name: super-agent
description: >-
  Unified super agent for sliProd: KG + test KG + skills + learning bus in one loop.
  Use at session start, RCA, testing, fix+ship. All layers cross-learn via learning_bus.
triggers:
  - session start
  - any task
  - orient
  - test
  - RCA
  - sync
requires: []
reads:
  - .cursor/workspace-intelligence-state.md
  - cursor-bundle/memory/MEMORY.md
  - cursor-bundle/flow-test/learning_bus.jsonl
  - cursor-bundle/flow-test/test_coverage.jsonl
  - cursor-bundle/kg/data/kg.db
writes:
  - cursor-bundle/flow-test/learning_bus.jsonl
  - cursor-bundle/brain/testing/learnings.jsonl
feeds:
  - workspace-router
  - autonomous-workspace-ops
  - capture-proof
---

## Routing metadata

<!-- ported from Cursor skill frontmatter -->

- **triggers:** `session start`, `any task`, `orient`, `test`, `RCA`, `sync`
- **requires:** []
- **reads:** `.cursor/workspace-intelligence-state.md`, `cursor-bundle/memory/MEMORY.md`, `cursor-bundle/flow-test/learning_bus.jsonl`, `cursor-bundle/flow-test/test_coverage.jsonl`, `cursor-bundle/kg/data/kg.db`
- **writes:** `cursor-bundle/flow-test/learning_bus.jsonl`, `cursor-bundle/brain/testing/learnings.jsonl`
- **feeds:** `workspace-router`, `autonomous-workspace-ops`, `capture-proof`

# Super agent (KG + test KG + skills)

One orchestrator. All intelligence layers **cross-learn** through `learning_bus.jsonl` — skills do not hold separate state.

## Architecture

```
                    super-agent.sh
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
     kg.db          test_coverage      learning_bus
   (structure)        (proof)           (events)
        │                 │                 │
        └──────── cross_learn.py ───────────┘
                          │
              skills · ntest · capture-flow
```

## Session start (mandatory)

```bash
bash scripts/bin/super-agent.sh session   # stamps kg_fresh TTL
# Loop: classify → PLAN (scripts/lib/process_matrix.json) → execute → LEARN close
bash scripts/bin/super-agent.sh close --text "…" --classification BUG/RCA
python3 cursor-bundle/kg/bin/kg.py validate   # abort if fail (when PLAN says RUN)
```

Read `.cursor/workspace-intelligence-state.md`. Weekly: `intel-automation.sh weekly` → bus age + `SELF-REPORT.md`.

## Unified orient (one command, all layers)

```bash
bash scripts/bin/super-agent.sh orient disburseLoan
# or: ntest super orient disburseLoan
# or: ntest orient disburseLoan  # same unified view
```

Returns: KG flow/crud/why/cases + FTG + test_coverage + learnings + bus events.

## Cross-layer sync (after code/test/branch change)

```bash
bash scripts/bin/super-agent.sh sync        # test map + platform + hints + hub
bash scripts/bin/super-agent.sh sync --kg   # + full KG rebuild
```

## Disk cleanup (local dev — archived service logs, scratch)

Local services use `gradle bootRun`; rotated logs under `logs/*/archived` and `logs/*/archive` are safe to purge (~300MB+ typical).

```bash
bash scripts/bin/super-agent.sh clean           # audit reclaimable space
bash scripts/bin/super-agent.sh clean --apply   # clean + fast-sync
bash scripts/bin/workspace-disk-clean.sh --clean  # same disk pass (also in max-pass + autopilot end)
```

Active logs for **running** services are left intact; inactive services get large logs truncated.

## Testing with intelligence

```bash
bash scripts/bin/agent-ops.sh before-test loanPrepayment
ntest auto loanPrepayment          # fail → learning_bus test_fail + analyze + test map
ntest map --api loanPrepayment     # proof-backed coverage row
ntest smoke --tier smoke           # tier gate from test_map
```

## Fix + ship loop

```
fix → test → capture-flow.sh → changelog kg-flow → super-agent sync → ship-knowledge-gate
```

## Unified gaps (all layers)

```bash
bash scripts/bin/super-agent.sh gaps --money
```

Merges: test_coverage gaps + FTG coverage=gap + KG test_gap nodes.

## Learn (writes all layers)

```bash
bash scripts/bin/super-agent.sh learn --api disburseLoan --text "client_reference_number must be numeric"
# writes: learnings.jsonl + learning_bus + test_hints.jsonl
```

## Proof gate (non-negotiable)

1. `kg validate` before structure queries
2. `super-agent orient <api>` before RCA
3. Orchestration XML + `db-local.sh` for behaviour/DB truth
4. `NOT VERIFIED` without this-turn evidence

## Sub-skills (load when router says so)

| Skill | When |
|-------|------|
| autonomous-workspace-ops | run test / sanity |
| capture-proof | after pass on money path |
| reuse-queries-java-filter | DAO edits |
