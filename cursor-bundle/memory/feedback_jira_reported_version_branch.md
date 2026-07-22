# JIRA reported version → upstream branch (STANDING)

**Rule:** For every SDCP/JIRA RCA or fix, read the **Reported version** field first (e.g. `customfield_11895` = `3.4.2.1 (QA3)`), then checkout/analyse **`upstream/mfi_integration_vX.Y.Z`** matching that version — not the local default train (e.g. 3.7.1) and not a guessed env branch.

**Also:** Use the ticket **environment** (QA3/QA6/…) for DB (`scripts/db-qa3.sh`, etc.).

**Example:** SDCP-11058 → `3.4.2.1 (QA3)` → `mfi_integration_v3.4.2.1` + QA3.

**Do not ask again** — apply automatically on every JIRA-linked investigation.

**Then sync:** After mapping Reported version → `mfi_integration_vX.Y.Z`, run the train sync-first gate (`feedback_train_branch_sync_origin_upstream.md`) before analysis checkout or push — base on `upstream/…` tip, not a stale `origin/…` tip.
