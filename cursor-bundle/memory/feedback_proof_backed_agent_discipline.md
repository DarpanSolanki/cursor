---
name: feedback_proof_backed_agent_discipline
description: "Master discipline — every factual claim, recommendation, mail, spec, code change, or sample artifact must be backed by evidence verified THIS turn (file:line, diff hunk, command output). Four pre-output gates — evidence-before-claim, enumerate-before-summarize, widen-search-before-deciding-absent, state-uncertainty."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7fc30f42-df07-4d0a-8093-68fff3c6147e
---

Every factual claim, recommendation, mail, spec, code change, or sample artifact MUST be backed by **evidence verified in THIS turn** (file:line, diff hunk, command output). Four gates before any non-trivial output:

- **(a) evidence-before-claim** — paste the file:line / command that proves it; never half-recall.
- **(b) enumerate-before-summarize** — for "what changed" artifacts, list every diff line explicitly first, then build the deliverable from that list.
- **(c) widen-search-before-deciding-absent** — before saying "X does not exist", search src/, orchestration XML, templates, constants, brain docs, and behavioural keywords (error codes, messages) — not one grep in two dirs.
- **(d) state-uncertainty** — if not verified end-to-end, say so (`NOT VERIFIED — needs runtime confirmation`).

**Why:** Half-recalled or unverified claims cause wrong fixes, wrong mails, and QA re-opens. This discipline is the backbone of the deep-RCA and QA-handoff rules.

**How to apply:** Run all four gates before any factual output. The pre-Edit/Write hook reprints them. CLAUDE.md §0 Rule 7. Pairs with [[feedback_deep_rca_before_fix]], [[feedback_qa_handoff_package]], [[feedback_no_half_fixes_accounting]].
