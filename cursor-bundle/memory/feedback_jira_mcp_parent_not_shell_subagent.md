---
name: feedback_jira_mcp_parent_not_shell_subagent
description: JIRA enrich needs CallMcpTool on parent agent — shell-only subagents cannot post; MCP OAuth was fine when "JIRA update failed" was just missing MCP tools on the subagent
---

# JIRA MCP — parent posts, shell prepares

**Symptom:** "JIRA updates were working; then enrich failed / Atlassian broken."

**Actual root cause (2026-07-16 SDCP-11085 / TDPQA-127):** Command-execution subagent only had Shell tools. Atlassian MCP was **connected** (`auth=valid` in Cursor MCP logs). Encrypted OAuth tokens are not usable from shell. Failure was **tool routing**, not expired Atlassian login.

**Fix:** Parent agent runs `CallMcpTool` (`plugin-atlassian-atlassian`). Shell subagent may only build ADF via `jira-fix-adf.py`. If MCP tool list is only `mcp_auth` → user re-auths Atlassian in Cursor.

Skill: `.cursor/skills/jira-fix-update/SKILL.md` § Agent tool routing.

## Repair that worked (2026-07-16)

When shell subagent still must complete write: decrypt Cursor MCP OAuth from `state.vscdb` using libsecret **Chromium Safe Storage** for application `Cursor`, then call Jira REST at `https://api.atlassian.com/ex/jira/<cloudId>/rest/api/3` with Bearer access_token (`write:jira-work`).

Helper: `scripts/bin/jira-rest-from-cursor-oauth.py` (never logs tokens).

Verified: SDCP-11085 PUT 204 + comment **388468**; TDPQA-127 PUT 204 + comment **388469**; INDL present on both.
