---
name: capture-proof
description: >-
  After a money-path fix and passing test: capture footprint, sources, and learning
  bus events. Use with capture-flow.sh and ship-knowledge-gate before declaring done.
triggers:
  - after fix
  - after test pass
  - ship
  - kg-flow
requires:
  - autonomous-workspace-ops
reads:
  - cursor-bundle/flow-test/chains.jsonl
  - cursor-bundle/flow-test/contracts.jsonl
  - cursor-bundle/flow-test/flows.jsonl
writes:
  - cursor-bundle/flow-test/sources.jsonl
  - cursor-bundle/flow-test/footprints.jsonl
  - cursor-bundle/flow-test/learning_bus.jsonl
feeds:
  - sync-intelligence
---

## Routing metadata

<!-- ported from Cursor skill frontmatter -->

- **triggers:** `after fix`, `after test pass`, `ship`, `kg-flow`
- **requires:** `autonomous-workspace-ops`
- **reads:** `cursor-bundle/flow-test/chains.jsonl`, `cursor-bundle/flow-test/contracts.jsonl`, `cursor-bundle/flow-test/flows.jsonl`
- **writes:** `cursor-bundle/flow-test/sources.jsonl`, `cursor-bundle/flow-test/footprints.jsonl`, `cursor-bundle/flow-test/learning_bus.jsonl`
- **feeds:** `sync-intelligence`

# Capture proof (post fix+test)

## When

Money path fix is coded **and** test passed (unit / ntest / sanity).

## Steps

```bash
scripts/bin/capture-flow.sh --ftg ftf:<flow_id> --jira SDCP-XXXX --test "<TestClass>"
# Dev-Test ADF → scripts/scratch/jira-handoff/; validate then human go:
bash scripts/bin/jira-handoff.sh --dry-run --jira SDCP-XXXX
cursor-bundle/kg/bin/changelog-add.sh --kg-flow "## DATE | acct \`sha\` | ... | kg-flow | title" "apiName …"
scripts/bin/sync-intelligence.sh --quick
scripts/bin/ship-knowledge-gate.sh
bash scripts/bin/write-intelligence-hub.sh
```

## Verify footprint

```bash
python3 scripts/testing/footprint_builder.py show ftf:<flow_id>
bash scripts/bin/super-agent.sh gaps --money | head
```

## Do not

- Skip `ship-knowledge-gate` on money-path fixes
- Index `.cursor/changelog.md` into KG (audit only)
- Mark done with `(pending)` in changelog
