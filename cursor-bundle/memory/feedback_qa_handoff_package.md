---
name: feedback_qa_handoff_package
description: "Every time the user hands over a JIRA ticket/issue to fix, produce a QA retest hand-off package — functional (non-code) RCA + impact analysis + simulated scenarios (expected vs actual) — drafted in-boundary for the user to paste into the ticket. JIRA writes are forbidden."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7fc30f42-df07-4d0a-8093-68fff3c6147e
---

When releasing a fix to QA, QA needs more than the code change. **Every time the user gives a JIRA ticket for an issue, automatically produce a QA hand-off package** to enrich the ticket before assigning back for retest, with these parts:
1. **RCA — functional, NOT code-specific** (what was going wrong & why, in business terms; no file:line/class names — those stay in CHANGELOG/working notes).
2. **Impact analysis** — flows/transactions/screens affected, regression surface (adjacent paths sharing the changed logic), data/config deps, and which branches/environments need the fix (`fwd-port.sh --path`).
3. **Scenarios simulated to confirm the fix** — each with precondition → action → **expected vs actual** (actual = DB-state delta or flow-trace, not "built green"); include a negative case (bug must not reproduce) and a regression case.
Plus reproducible QA retest steps and the truthful status ("pushed; awaiting QA retest").

**Why:** QA retests faster and more correctly with the functional cause, the blast radius, and concrete pass/fail scenarios. It also forces the fix to be proven by simulation, not asserted — fewer re-opens.

**How to apply:** use the [[rca-workflow]] + [[feedback_deep_rca_before_fix]] discipline to reach the code-level pinpoint RCA first, then translate it to the functional package via the **`qa-handoff` skill** (full template there). **Boundary:** JIRA writes are forbidden (CLAUDE.md Rule 1) — draft the package in-boundary and hand the formatted block to the user to paste; never call a `jira_*` write tool. Reads to pull the ticket are fine. Pairs with [[feedback_proof_backed_agent_discipline]] and the verification gate (never say "done" before QA confirms).
