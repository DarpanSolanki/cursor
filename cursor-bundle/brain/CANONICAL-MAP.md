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
| 6 | Multi-ask day → `cursor-bundle/brain/workspace/ASK-TRACKER-*.md` (living checklist) |

## Topic → canonical file

| Topic | Canonical | Agent entry / index |
|-------|-----------|---------------------|
| Platform map | `cursor-bundle/brain/platform/architecture.md` | `.cursor/architecture.md` (summary) |
| Open gaps | `.cursor/gaps-and-risks.md` (**SoT**) | `cursor-bundle/brain/gaps-and-risks.md` (mirror — sync RESOLVED money rows same turn) |
| Runbooks | `cursor-bundle/brain/runbooks/00-INDEX.md` | `.cursor/runbooks.md` (legacy index) |
| Ask completeness | `cursor-bundle/brain/workspace/ASK-TRACKER-YYYY-MM-DD.md` + `.json` | Do not claim done while OPEN/BLOCKED |
| Mixed trains | `cursor-bundle/brain/runbooks/mixed-train-matrix.md` | Scoped sync + kg-switch; never blind all-repo switch |
| Accounting flows | `cursor-bundle/brain/accounting/` + `.cursor/accounting-flows.md` | Money paths |
| Orchestration index | `.cursor/orchestration-map.md` | `kg flow <request>` for live chain |
| Events / Kafka | `.cursor/event-registry.md` | `kg deps <service>` |
| Platform-lib | `cursor-bundle/brain/rules/platform-lib.md` | `.cursor/platform-lib.md` |
| Contracts | `.cursor/service-contracts.md` | Cross-service |
| Conventions | `cursor-bundle/brain/` + `.cursor/conventions.md` | Java/XML style |
| Symptom-first ops | `system_brain/` flows + edge_cases | Thin notes; link to brain |
| Shipped fixes (audit) | `cursor-bundle/brain/changelog/CHANGELOG.md` | All commits |
| JIRA → flow graph | `cursor-bundle/brain/jira/JIRA-INDEX.md` + `jira-flow-graph.json` | Reopen: symptom → domain → SHA → `ntest` |
| KG precedents only | same CHANGELOG rows with `\| kg-flow \|` | `kg cases <flow>` |
| Workspace audit trail | `.cursor/changelog.md` | **Not indexed into KG** |
| Standing agent rules | `.cursor/rules/*.mdc` | Enforcement |
| Local DB diagnostics | `scripts/db/canned/` | `scripts/db-local.sh` |

## KG commands (safe usage)

```bash
python3 cursor-bundle/kg/bin/kg.py validate          # integrity + min nodes/edges; abort if fail
python3 cursor-bundle/kg/bin/kg.py orient disburseLoan  # flow + why + cases (evidence only)
python3 cursor-bundle/kg/bin/kg.py crud disburseLoan    # tables touched
python3 cursor-bundle/kg/bin/kg.py cases disburseLoan   # opt-in precedents only
python3 cursor-bundle/kg/bin/kg.py fresh               # branch watermark vs live checkout
```

## Do not duplicate into new files

- New flow note → extend **one** file under `cursor-bundle/brain/flows/` or `system_brain/flows/`.
- New gap → append `.cursor/gaps-and-risks.md` (**SoT**) **and** mirror the same RESOLVED/High row into `brain/gaps-and-risks.md` same turn.
- New stable fix → `changelog-add.sh --kg-flow` only when flow behaviour changed.
- KG edges/scripts/tests → **evidence only** (orch XML / Java / DB / ntest). Never invent graph edges or registry cases without those proofs.
