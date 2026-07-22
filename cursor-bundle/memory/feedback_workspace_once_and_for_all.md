---
name: feedback_workspace_once_and_for_all
description: User will not re-setup workspace daily — soft rules failed; machine gates (ship-discipline, path-absolute smoke/enrichment, workspace-contract) are the permanent fix
---

# Workspace once-and-for-all (2026-07-15)

User escalated (~100×): gaps persist (assumptions, overengineering, skipped minimal-fix/perf/KG) despite rules. Cause: **soft rules + cwd bugs**, not missing essays.

## Permanent hard gates

1. `scripts/lib/ship_discipline_gate.py` — money/service ship-loop FAIL without `.cursor/.ship-discipline.json` (minimal_fix, hot_path, verify_mode, kg_enrichment, assumptions as claim+evidence or `[]`).
2. Absolute ROOT paths in `workspace-smoke.sh` learnings check + `enrichment-audit.sh` DCF companion.
3. `.cursor/rules/00-workspace-core.mdc` — contract of record; **fix gates when agents drift**, do not ask user to reconfigure.
4. `super-agent corroborate` CLI restored (was advertised done, CLI choice missing).
5. `workspace-max-pass.sh` self-heals enrichment-sync when CHANGELOG newer than kg.db.

## Agent duty

Never ask Darpan to "setup workspace again". Run max-pass / discipline write / install-user-cursor-gates. If still failing — patch the **gate**, not another markdown rule.
