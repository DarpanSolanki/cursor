---
name: feedback_session_handoff_on_loop
description: "When a session is looping / too long to make progress (same failure 2-3x, RCA not converging, context bloated past compaction), STOP — flag it, write a handoff file under claude/handoff/, and tell the user to start a fresh session pointed at it. Don't keep burning iterations."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7fc30f42-df07-4d0a-8093-68fff3c6147e
---

When a single session is **looping or too long to make progress** — the same build/test fails the same way 2-3×, the same files get re-read/re-edited in circles, RCA isn't converging on a new fact, or context is bloated and compaction isn't helping — **STOP. Do not keep iterating.**

Instead: **(1) flag it** in one honest line ("we're looping on X N times — stopping to avoid wasted iterations"); **(2) write a handoff file** `claude/handoff/<date>-<slug>.md` (goal, verified-vs-assumed state with file:line proof, the exact blocker, the ONE next step, context the next session needs incl. branch + WIP base from `kg watermark`, and the **dead-ends already ruled out**); **(3) tell the user to start a fresh session (or `/clear`) and open with "Read claude/handoff/<file>.md and continue."** Use the **`session-handoff`** skill for the template.

**Honest limit:** the harness owns session lifecycle — **I cannot spawn a new session myself.** I detect the loop, stop, and produce the handoff; the user opens the new session. Don't claim to have "started a new session."

**Why:** repeated no-progress iterations waste tokens/time and often make things worse (churn edits, lost context). A clean handoff lets a fresh session start *ready* and break the loop — this is the escape hatch for [[feedback_deep_rca_before_fix]]'s "minimum iterations" goal.

**How to apply:** ground every "done" claim in proof ([[feedback_proof_backed_agent_discipline]]); write only under `claude/handoff/` (in-boundary, [[feedback_darpan_boundary]]); handoffs are transient — delete once consumed ([[feedback_workspace_hygiene]]). Durable findings still go to the brain docs / KG, not the handoff.
