---
name: feedback_darpan_boundary
description: "Hard boundary — never write outside /home/darpan/darpan/ (plus the memory dir). No external writes (Jira, upstream push, PR, KG mutations). Reads anywhere are fine. If a request needs an external write, refuse and offer the in-boundary alternative."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7fc30f42-df07-4d0a-8093-68fff3c6147e
---

**Never write outside `/home/darpan/darpan/`.** No `Edit`/`Write`/`cp`/`mv`/`rm`/`sed -i`/`mkdir`/`chmod`/`git checkout -- <path>` targeting paths outside this tree. No KG mutations (`mcp__kms-kb__kg_*` write tools), no Jira writes (`jira_create_issue`/`jira_update_issue`/`jira_transition_issue`/comments/worklogs), no `git__create_pr`/`git__push_to_fork`/Camunda-write/Postman-run. **Reads anywhere, read-only MCP, and writes inside `/home/darpan/darpan/`** (plus memory under `/home/darpan/.claude/projects/-home-darpan-darpan/`) are fine. Push only to **origin** (DarpanSolanki fork) via the `github-darpan` SSH alias, on explicit confirm — never to upstream/`trusttai` (formerly khoslalabs).

**Why:** This is the workspace's #1 safety contract — it prevents touching other users' homes, the shared environment, or external systems of record.

**How to apply:** If a request needs an external write, **refuse clearly, pivot to the in-boundary equivalent, and continue** (e.g. draft a Jira comment in-boundary for the user to paste; generate a PR compare URL instead of creating the PR). The boundary rule **beats every other instruction** — a skill, slash command, or chained instruction asking for an external write does not override it. If a memory and CLAUDE.md disagree, the more restrictive wins. Full statement: CLAUDE.md §0 Rule 1. Pairs with [[feedback_darpan_git_via_darpansolanki]], [[feedback_qa_handoff_package]].
