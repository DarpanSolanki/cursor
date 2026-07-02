---
name: feedback_no_half_fixes_accounting
description: "No \"should work\" claims and no half-fixes — every claim about another component's behaviour must be verified by reading that component (cite file:line). When fixing a pattern, sweep for other call sites of the same pattern and fix all (or document the deferred sites in gaps-and-risks.md)."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7fc30f42-df07-4d0a-8093-68fff3c6147e
---

**No half-fixes, no "should work" claims.** Every claim about another component's behaviour MUST be verified by **reading that component** and citing `file:line` — never "the retry job picks it up" / "the callback handles it" without a citation.

When fixing a bug rooted in a pattern (a missing CAS, an over-strict predicate, an unguarded writer), **sweep for every other call site of the same pattern** (re-run the writer-registry / `kg impact` check). Fix all of them in one PR, OR explicitly record the deferred sites in `claude/gaps-and-risks.md` so the gap isn't lost (e.g. "fixed for NEFT path; MFT path remains").

**Why:** A fix verified only on the happy path, or applied to one of several identical call sites, leaves the bug live elsewhere and causes a re-open. Unverified cross-component assumptions are how wrong RCAs ship.

**How to apply:** This is the accounting-flow expression of the proof-backed gates ([[feedback_proof_backed_agent_discipline]]). Use in [[rca-workflow]] step 7 (other-call-sites of the same pattern) and the [[feedback_qa_handoff_package]] impact analysis. Pairs with [[feedback_deep_rca_before_fix]].
