---
name: reference-enforcement-hooks
description: "Active enforcement for Cursor sliProd — .cursor/hooks.json + .cursor/hooks/*.sh (not .claude/settings.json)."
metadata:
  node_type: memory
  type: reference
---

Memory/feedback files are **passive**. Active enforcement for **this** workspace lives in **`.cursor/hooks.json`**, which runs scripts under **`.cursor/hooks/`** (often via `scripts/bin/with-budget.py`).

Representative hooks (see `hooks.json` for the live list):

1. **sessionStart** → `memory-session-start.sh`, `kg-session-start.sh`, `intel-session-sync.sh`, `workspace-autopilot-session.sh`, …
2. **afterFileEdit** → `after-ship-path-edit.sh`, `kg-after-file-edit.sh`
3. **beforeShellExecution** → `pre-commit-kg-reminder.sh`, `pre-push-checklist.sh`, `kg-grep-leak-log.sh`
4. **afterShellExecution** → `post-commit-kg-flag.sh`, `post-commit-ship-test.sh`, `post-push-enrichment.sh`, `post-checkout-kg.sh`, …
5. **stop** → `stop-ship-nudge.sh`

**Boundary / quality** also comes from alwaysApply rules under `.cursor/rules/` (`00-workspace-core`, `10-quality-gates`, `20-ship-gates`, `30-kg-discipline`, `darpan`) and user gates under `~/.cursor/rules/` / `scripts/cursor-user-gates/`.

**Wrong SoT (do not follow):** `/home/darpan/darpan/.claude/settings.json` or Claude Code `sync-claude-hooks.py` — that is the sibling Claude product. Cursor reads **`hooks.json` directly**.

Review: Cursor Settings → Hooks, or open `.cursor/hooks.json`.
