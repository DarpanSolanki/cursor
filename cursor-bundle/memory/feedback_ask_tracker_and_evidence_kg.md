# Ask tracker + evidence-only KG (standing)

**When:** Any multi-ask / workspace-upgrade / harmony day; any agent tempted to invent KG edges, registry cases, or “all trains synced”.

## Standing rules

1. **Ask tracker** — If the user has multiple concurrent asks, create/update `cursor-bundle/brain/workspace/ASK-TRACKER-YYYY-MM-DD.md` + twin `.json`. Mark DONE only with evidence paths. OPEN/IN_PROGRESS/BLOCKED blocks “workspace upgrade complete” / “sure for QA”.
2. **Evidence-only KG** — `kg validate` (integrity) and `kg orient <api>` (flow+why+cases) must exist and be used. Never add graph edges, JIRA nodes, or ntest cases without orch XML / Java / DB / ntest proof. Prefer backlog row (`scripts/workspace-backlog.json`) over fake coverage.
3. **Hooks** — `.cursor/hooks.json` `afterFileEdit` → `after-ship-path-edit.sh` (not `after-money-path-edit.sh`). Ship-path edits must register `.pending-ship-work.json`.
4. **Mixed trains** — Do not run `sync_branches_v2.sh <branch>` across all repos unless the user explicitly wants one train everywhere. Use [`mixed-train-matrix.md`](../brain/runbooks/mixed-train-matrix.md): DFC→accounting `3.7.1`; disburse RCA on `3.4.2.2`→scoped LOS+accounting; then `kg-switch.sh`.
5. **Gaps dual-home** — `.cursor/gaps-and-risks.md` is SoT; mirror RESOLVED money rows into `cursor-bundle/brain/gaps-and-risks.md` same turn.
6. **Ship honesty** — Dirty money code without pending-ship, or `.ship-loop-passed.json` while uncommitted money exists, is a FAIL. After commit: `workspace-close.sh --from-pending`.

## Evidence (2026-07-10 gap-closure)

- Wired `validate`/`orient` into `cursor-bundle/kg/bin/kg.py` (previously docs claimed them; CLI printed help).
- Harmony H01–H07 closed with paths in ASK-TRACKER; H08 documented via mixed-train-matrix.
