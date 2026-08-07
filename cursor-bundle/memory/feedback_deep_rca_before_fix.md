---
name: feedback_deep_rca_before_fix
description: "For ANY bug fix or issue analysis — do deep, code-backed, flow-simulated, DB-grounded RCA to an exact pinpoint root cause BEFORE planning the fix. Goal is minimum iterations; never ship a guess."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7fc30f42-df07-4d0a-8093-68fff3c6147e
---

For any fix or issue analysis, do a thorough deep RCA to an **exact, pinpoint root cause before proposing or planning the fix**. The explicit goal is **minimum iterations** — no guess-fix-retest churn. A built-green branch off a half-understood cause is a likely re-open.

**Why:** Shallow "looks like X, try this" fixes cause multiple QA round-trips, can fix a symptom while the real cause re-surfaces elsewhere, and can break a working path. One deep RCA up front is cheaper than three iterations.

**How to apply (before writing any fix):**
1. **Code-back every step** — trace the exact execution path with `txn-graph` / `kg flow` / file:line reads; cite `file:line` for each claim (proof-backed gates in .cursorrules §0.7). No half-recall.
2. **Simulate / replay the flow** — walk the orchestration `<Request>`→processor chain and the writer/reader timeline for the affected row mentally or on paper end-to-end; identify the exact seam (thread, transaction boundary, CAS, predicate) where it breaks. Reproduce locally where feasible.
3. **Check the DB where the case is observed** — when given a LAN / id / env, pull ground-truth first (`lan-360`, `db-access`, canned queries) and correlate to logs by timestamp+correlation-key. Don't theorize over a state you haven't read.
4. **State the pinpoint RCA explicitly** (one cause, file:line, the precise interleaving/condition) and only THEN plan the fix. If not yet certain end-to-end, say `NOT VERIFIED` and close the gap before coding — do not proceed on a hypothesis dressed as a conclusion.
5. Then run the fix proposal through the existing checks: writer-registry / other-callsites sweep, concurrency-contract audit, [[feedback_no_inmem_mutation_after_cas]] CAS rule, build green.

This sharpens — does not replace — the [[rca-workflow]] skill (which already encodes DB→log→classify→cite→fix). The delta this rule adds: **simulate to a single pinpoint cause, verify against DB/code, THEN plan — optimise for first-time-right.** Pairs with [[feedback_keep_knowledge_current]] and the proof-backed discipline in .cursorrules §0.
