---
name: workspace-close
description: >-
  Single command to close any task (workspace / service / money tier): KG fresh →
  tier-aware ship-loop → sync → knowledge gate → hygiene.
triggers:
  - task done
  - ship
  - workspace-close
  - from-pending
  - analysis done
requires:
  - autonomous-workspace-ops
reads:
  - .cursor/.pending-ship-work.json
  - cursor-bundle/brain/changelog/CHANGELOG.md
writes:
  - .cursor/.ship-loop-passed.json
scripts:
  - scripts/bin/workspace-close.sh
feeds:
  - super-agent
  - workspace-hygiene
  - capture-proof
---

## Routing metadata

<!-- ported from Cursor skill frontmatter -->

- **triggers:** `task done`, `ship`, `workspace-close`, `from-pending`, `analysis done`
- **requires:** `autonomous-workspace-ops`
- **reads:** `.cursor/.pending-ship-work.json`, `cursor-bundle/brain/changelog/CHANGELOG.md`
- **writes:** `.cursor/.ship-loop-passed.json`
- **feeds:** `super-agent`, `workspace-hygiene`, `capture-proof`
- **scripts:** `scripts/bin/workspace-close.sh`

# Workspace close (all tiers)

## When

- Any ship-path edit (workspace scripts, service code, money APIs)
- Hooks nudge at session stop
- User says close task / ship / release details prep

## Command

```bash
bash scripts/bin/workspace-close.sh --from-pending
bash scripts/bin/workspace-close.sh --from-pending --capture   # CAPTURE_FTG set (money proof)
bash scripts/bin/workspace-close.sh --tests-only
python3 scripts/lib/infer_ship_apis.py --classify path/to/file
```

## Tiers (from pending-ship-work.json)

| Tier | Ship-loop |
|------|-----------|
| workspace | KG validate + ntest validate |
| service | gradlew build + health/API ntest |
| money | build + API ntest + smoke_tier=money |

## Pipeline

1. KG validate + fresh
2. Brain CHANGELOG vs pending commit
3. Tier-aware `ship-loop-gate.sh`
4. Optional `capture-flow.sh` with `--capture`
5. `super-agent sync` + `kg-enrich --cases`
6. `ship-knowledge-gate.sh` + hygiene
7. `write-intelligence-hub.sh`

## Do not

- Skip close for “just workspace” edits — tier workspace still validates KG/registry
- Declare done with STALE KG or open `.pending-kg-rebuild`
