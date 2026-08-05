---
name: feedback_darpan_boundary
description: "Hard boundary — never write outside /home/darpan/Documents/sliProd/ (plus allowlisted local exceptions). No upstream push; remote QA/prod DB writes forbidden."
metadata:
  node_type: memory
  type: feedback
---

**Never write outside `/home/darpan/Documents/sliProd/`.** No `Edit`/`Write`/`cp`/`mv`/`rm`/`sed -i` targeting paths outside this tree (except allowlisted local ops below).

**Allowed exceptions (standing):**
- Jira edits via Atlassian MCP when the user explicitly asks
- Local Yugabyte writes on `127.0.0.1`/`localhost:5433` via `scripts/bin/db-local-write.sh` / dpic helpers
- `/tmp` scratch

**Forbidden:** `git push` to upstream (`trusttai`), PRs to upstream, remote QA/UAT/prod DB writes, ad-hoc `psql` to non-local hosts.

**Reads** anywhere are fine. Push only to **origin** (DarpanSolanki) on explicit confirm — use `bash scripts/bin/push-origin.sh` on train branches.

**Stale path:** `/home/darpan/darpan/` is the old Claude Code home — **not** this workspace. Agents must not treat it as the write boundary.

Pairs with [[reference_workspace_canonical_setup]], [[feedback_darpan_git_via_darpansolanki]]. Full statement: `.cursor/rules/darpan.mdc`.
