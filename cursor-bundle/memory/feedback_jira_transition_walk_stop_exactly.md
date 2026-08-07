---
name: jira-transition-walk-stop-exactly
description: Walking a Jira workflow: plan the full route, verify each state's precondition, and match the target state by equality — substring matching walked a ticket into QA:Closed
metadata:
  type: feedback
---

Walking a Jira workflow: plan the full route, verify each state's precondition, and match the target state by equality — substring matching walked a ticket into QA:Closed

**Why:** TDPQA-241, 2026-08-06. TDPQA does not expose QA Test directly; the route is DevAITDP:Start → In Progress → PR: Dev Reviewing → PR: Dev Lead Reviewing → PR: Lead Approved → QA:Test → QA:Closed. Two failures in one session: (1) started stepping before reading the whole path, and landed in the PR-review states while the fix was still origin-only with no upstream PR — those states assert a review that had not happened; (2) the stop condition was `"qa test" in to.lower()`, which is **False** for `QA:Test` because of the colon, so the walk continued one more step and set **QA:Closed** — asserting QA had tested a fix they had never seen.

**How to apply:** enumerate `/transitions` and plan the route before the first POST. Check each state's real-world precondition (PR states need `git merge-base --is-ancestor <sha> upstream/<train>`). Compare the target with `to == "QA:Test"`, never a substring, and block every state past the target alongside QA:Traige / Dev:Rework / Not an issue. Recovery: transition id 11 (To Do) returns to DevAITDP:Start with fields intact — re-walk, and say out loud that it happened, because a ticket that briefly read QA:Closed may already have notified people. Rule: `.cursor/rules/jira-tdpqa-qa-test-fields.mdc` § Status.
