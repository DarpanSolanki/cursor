---
name: reference_sliProd_local_setup
description: Canonical local workspace paths for sliProd (not remote darpan/QA).
metadata:
  node_type: memory
  type: reference
---

**Workspace:** `/home/darpan/Documents/sliProd/`

| What | Path |
|------|------|
| Brain docs | `cursor-bundle/brain/` |
| KG CLI | `python3 cursor-bundle/kg/bin/kg.py` |
| KG rebuild | `cursor-bundle/kg/bin/build.sh` |
| Memory | `cursor-bundle/memory/MEMORY.md` |
| Agent rules | `.cursor/rules/darpan.mdc` |
| Gaps / orchestration | `.cursor/gaps-and-risks.md`, `.cursor/orchestration-map.md` |
| Local DB read | `scripts/db-local.sh` (localhost:5433) |
| Local DB reset | `scripts/local_reset_*.sql` via psql |
| Setup check | `scripts/setup-local.sh` |
| Layout | `WORKSPACE.md` |

**No QA/VPN database.** Verify state on local Yugabyte only.

**Build:** `cd <repo> && ./gradlew build -x test` (not gbuild.sh).

**Changelog for KG cases:** `cursor-bundle/brain/changelog/CHANGELOG.md` (+ `.cursor/changelog.md` for agent log).
