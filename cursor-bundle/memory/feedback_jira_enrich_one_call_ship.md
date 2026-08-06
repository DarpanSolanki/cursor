---
name: jira-enrich-one-call-ship
description: Jira enrichment slowness was agent round trips, not the scripts — use jira-enrich.sh ship for the whole handoff in one call
metadata:
  type: feedback
---

Jira enrichment slowness was agent round trips, not the scripts — use jira-enrich.sh ship for the whole handoff in one call

**Why:** Darpan 2026-08-06. Measured: `pack` 0.04s, a REST call 0.38s — the tooling was never slow. TDPQA-241 cost ~15 agent tool calls (read skill, owners, mentions, project_mode, GET fields, GET transitions, pack, inspect, rebuild after a forbidden hit, post, then POST+GET+GET per transition step). Re-verifying things already confirmed earlier in the same conversation is the waste.

**How to apply:** `bash scripts/bin/jira-enrich.sh ship <KEY> payload.json --to QA:Test --sha <sha> --train <branch>` — one process, ~2s, prints one JSON summary. It carries the gates that caught real mistakes: forbidden text blocks before posting, push gate blocks a sha not on origin, PR-review states are skipped unless the sha is on upstream, and the walk stops at the target by equality so it cannot overshoot into QA:Closed. Do not re-read SKILL.md / owners-defaults.json / mentions.json / fields-reference.md on a routine enrich — ship reads them itself.
