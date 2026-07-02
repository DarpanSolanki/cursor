# Canonical knowledge map — where to read first

> **Rule:** One topic → one primary file. Other paths may mirror or summarize; on conflict **verify code + DB**. KG (`kg flow`) is structure only.

## Session entry (every task)

| Order | Path |
|-------|------|
| 1 | `WORKSPACE.md` |
| 2 | `cursor-bundle/memory/MEMORY.md` |
| 3 | `python3 cursor-bundle/kg/bin/kg.py validate && kg orient <request>` |
| 4 | This file → topic row below |
| 5 | Service orchestration XML + `scripts/db-local.sh` |

## Topic → canonical file

| Topic | Canonical | Agent entry / index |
|-------|-----------|---------------------|
| Platform map | `cursor-bundle/brain/platform/architecture.md` | `.cursor/architecture.md` (summary) |
| Open gaps | `cursor-bundle/brain/gaps-and-risks.md` | `.cursor/gaps-and-risks.md` |
| Runbooks | `cursor-bundle/brain/runbooks/00-INDEX.md` | `.cursor/runbooks.md` (legacy index) |
| Accounting flows | `cursor-bundle/brain/accounting/` + `.cursor/accounting-flows.md` | Money paths |
| Orchestration index | `.cursor/orchestration-map.md` | `kg flow <request>` for live chain |
| Events / Kafka | `.cursor/event-registry.md` | `kg deps <service>` |
| Platform-lib | `cursor-bundle/brain/rules/platform-lib.md` | `.cursor/platform-lib.md` |
| Contracts | `.cursor/service-contracts.md` | Cross-service |
| Conventions | `cursor-bundle/brain/` + `.cursor/conventions.md` | Java/XML style |
| Symptom-first ops | `system_brain/` flows + edge_cases | Thin notes; link to brain |
| Shipped fixes (audit) | `cursor-bundle/brain/changelog/CHANGELOG.md` | All commits |
| KG precedents only | same CHANGELOG rows with `\| kg-flow \|` | `kg cases <flow>` |
| Workspace audit trail | `.cursor/changelog.md` | **Not indexed into KG** |
| Standing agent rules | `.cursor/rules/*.mdc` | Enforcement |
| Local DB diagnostics | `scripts/db/canned/` | `scripts/db-local.sh` |

## KG commands (safe usage)

```bash
python3 cursor-bundle/kg/bin/kg.py validate          # run first; abort if fail
python3 cursor-bundle/kg/bin/kg.py orient disburseLoan  # map + disclaimer
python3 cursor-bundle/kg/bin/kg.py crud disburseLoan    # tables touched
python3 cursor-bundle/kg/bin/kg.py cases disburseLoan   # opt-in precedents only
```

## Do not duplicate into new files

- New flow note → extend **one** file under `cursor-bundle/brain/flows/` or `system_brain/flows/`.
- New gap → append `.cursor/gaps-and-risks.md` **and** `brain/gaps-and-risks.md` in same turn (or kb-only changelog row until synced).
- New stable fix → `changelog-add.sh --kg-flow` only when flow behaviour changed.
