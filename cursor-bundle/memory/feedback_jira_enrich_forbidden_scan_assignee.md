# JIRA enrich — forbidden-token scan + assignee/owners (STANDING)

**Triggered by:** SDCP-11058 handoff put `3.4.2.2`, harness language (`e2e`, member counts 1–20), and left Dev/QA owner custom fields empty despite `owners-defaults.json`.

## Hard rules

1. **Pre-post scan (mandatory)** — Before `editJiraIssue` / comment update, run every draft field + comment through the forbidden-token scan in `.cursor/skills/jira-fix-update/SKILL.md` (or `python3 scripts/bin/jira-fix-adf.py scan <text>`). Fail closed: do not post if any hit. Also rejects capital-C `Cursor` / `Cursor IDE` (see `feedback_jira_aitdp_remarks_no_cursor_brand.md`).
2. **No version / branch in JIRA text** — Not `3.4.2.2`, not `mfi_integration_*`, not “build X.Y.Z”. Say “the build shared for QA” / “ready for QA” unless the user explicitly asked for a version string.
3. **Dev Test = functional QA retest steps** — Plain-language scenarios QA can re-run. Never `ntest`, registry, unit/e2e harness counts, SHAs, class/apiNames, or “N=1..20” matrix language.
4. **Assignee + owners (mandatory on every enrich)** — Set standard `assignee` to Darpan Solanki (`5e9d51241067100c195f7b12`) unless user says otherwise, **and** merge `owners-defaults.json` via `jira-fix-adf.py owners` into `editJiraIssue` fields (Dev Lead / Dev Owner / Product Owner / QA Owner / Reviewer / Approvers). Skill gap previously: helper existed, SKILL.md never required it.

## Do not ask again

Apply on every SDCP fix handoff / JIRA enrich.
