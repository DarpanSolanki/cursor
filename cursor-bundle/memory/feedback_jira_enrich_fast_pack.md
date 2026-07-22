---
name: feedback_jira_enrich_fast_pack
description: JIRA enrich was slow — use jira-enrich.sh pack (one scan, all ADF) + token cache; skip getJiraIssueTypeMetaWithFields per handoff
---

# JIRA enrich — fast pack path (2026-07-16)

**Symptoms:** JIRA enrich/update takes many minutes; agents spawn shell subagents, retry OAuth, call field meta API repeatedly.

**Fixes shipped:**
1. `jira-fix-adf.py pack <KEY> payload.json` — mode + owners + all ADF fields + comment + **one** forbidden scan.
2. `scripts/bin/jira-enrich.sh` — `ensure` (`.venv-jira` + secretstorage), `pack`, `post` (pack + REST apply).
3. `jira-rest-from-cursor-oauth.py` — OAuth token cache (~50 min TTL); `apply-pack` command.
4. SKILL.md fast path — parent agent: one `editJiraIssue` + optional `addComment`; **no** `getJiraIssueTypeMetaWithFields` on routine handoff.

**Agent routing unchanged:** parent owns MCP writes; shell prepares pack only.
