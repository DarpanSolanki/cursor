# Extended session KG refresh (standing)

**When resuming the same chat after branch checkout, long idle, or train switch:**

1. `python3 cursor-bundle/kg/bin/kg.py watermark` — confirm accounting/payments/LOS match KG built branch@sha
2. `bash scripts/bin/kg-ensure-fresh.sh` — auto-sync if stale (or `kg-switch.sh` on failure)
3. Re-read `.cursor/workspace-kg-state.md` before money-path RCA or verified claims

**Machine gates (2026-07-22):**

- `workspace-autopilot.sh task` — kg_fresh on task shift / stale / money keywords
- `workspace-autopilot.sh end` — `kg_watermark_gate.py --block-verified` blocks verified claims
- `workspace-close.sh` — watermark + registry companion + ntest validate on pending ship
- `enrichment-audit.sh --pre-push` — blocks when CHANGELOG newer than kg.db or KG quick-check stale
- `post-commit-kg-flag.sh` — auto `enrichment-sync.sh` when branch-set drifted

Pair: `feedback_full_impact_analysis_before_money_ship.md`, `30-kg-discipline.mdc`.
