---
name: feedback_keep_code_simple
description: "User wants simple, non-over-engineered code — and NO explanatory comments. Recurring, high-irritation."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 35aa8001-a8d4-4a27-92f5-7ac0ac972372
---

**RULE 1 — NO COMMENTS. Default to zero.** The user has flagged this 5+ times ("again you are adding lot of comments", "what kind of memory you have created", "lot of verbose comments are created for dpic development — comment should be as crisp and short"). Do NOT write javadoc, rationale, "why", "Sheet rule X binds on...", idempotency notes, or any explanatory inline comment on a code change. The accounting codebase is sparsely commented — match it. Rationale goes in the commit message + `claude/changelog`, NEVER inline. Only keep a comment if the exact surrounding lines already carry comparable ones. When rewriting a file, STRIP existing verbose comments too, don't preserve them. Apply this reflexively on the FIRST write — checking it after the user complains is already a failure. Self-check before every Edit/Write: "did I add a comment? delete it."

**Machine gate:** `scripts/bin/java-comment-lint.sh` (lib: `scripts/lib/java_comment_lint.py`) — fail-closed on DPI Java for consecutive `//` narratives, long javadocs, and ticket/parity essay markers. Wired into money `ship-loop-gate` via `--from-pending`.

**RULE 2 — no over-engineering / no dead ceremony. Mirror the existing analogous flow exactly.** "Our code should be in same lines as current interest accrual/billing is handled — do not over-engineer." Before writing anything for a DPI/lifecycle change, find how the parallel **interest** flow does it and reproduce that shape — same helpers, same idioms, same structure. Do NOT add capability beyond current scope. Examples the user reacted to:
- Speculative frequency branches (`WEEKLY` handling) when v1 is MONTHLY-only; loop guard-counters / bounds on a loop that already terminates; helper methods + javadoc for a 2-line inline computation.
- Defensive null-ternaries (`x != null ? x.toString() : ""`) placed after an `if` that already guarantees non-null; `cond ? "true" : "false"` instead of `String.valueOf(cond)`.
- Inventing a new GL leg/key/flag (`DPI_FORCE_BILL_AMT`) when an existing analogous flow already had the mechanism (death-FC force-books the gap by folding it into the single settlement amount + `markBilledTillDate`). Before adding a construct, find how an existing flow does it and reuse that exact pattern.
- Keeping dead branches/overloads/fields "just in case." Delete them.

**RULE 3 — reuse existing code & DB queries; filter in code, don't add queries.** "Use the current code and db queries as much as you can; if some filtering is required do it in code as much as we can — we should not introduce more queries unnecessarily." Before adding a repository method / `@Query`, check whether an existing query already returns the rows (even if its NAME implies otherwise — e.g. `getLatestLoanInstallmentDetailsEntity` actually returns the *earliest* installment `>= date`). Prefer: extend an existing SELECT with an extra column over writing a new query; do the predicate/pick/roll in Java over a new DB round-trip. New query only when no existing one fits.

**Why:** ceremony, comments, and redundant queries that can't change behaviour are noise that obscures intent and adds DB load. **How to apply:** compute inside the scope where values are already valid; prefer the terse idiom; match surrounding terseness; remove dead code; reuse the existing query and filter in code. Broader terseness discipline: [[feedback_proof_backed_agent_discipline]].
