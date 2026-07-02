---
name: feedback_config_resolution_rca
description: "Universal pinpoint-RCA method for ANY issue — observable→resolver/decision-point→dependency→VERIFY LIVE before concluding; never assume a code↔config/state match. Use `kg why <request>`. Triggered by a config-resolution miss."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ec4adad0-61f0-447b-af7f-0efed75e937a
---

**For ANY analysis or RCA (not one bug class), follow this method before concluding — it is what would have made me right the first time:**

1. **Name the observable precisely** — screen + field + the exact wrong value (wrong / 0 / blank / missing / stuck / duplicate / reverted are different searches).
2. **Find the resolver / decision-point that PRODUCED it** — not the screen/view. Run **`kg why <request>`** (the failure-mode layer: every flow's silent zero/null/empty/swallowed-catch branches + curated root-causes with live SQL) and `kg flow`/`kg crud`; map symptom→file:line. **Do this before grepping.**
3. **Enumerate its dependencies** — config/master mapping, state column, precondition API, master data — and the silent branch that fires when each is absent.
4. **VERIFY each dependency on LIVE data before concluding** — including `is_deleted`/active flags, status, type/sub_type. **Never assert a code↔config/state match from memory; query it.** Compare against a working case.
5. **State the fix as a data/config/code delta + the expected post-fix value** (QA-verifiable).

**Why this is a standing lesson (the miss that triggered it):** on a "CBC Fee shows ₹0 on the foreclosure quote" bug (QA3 2026-06-11, loan 6008846130/scheme 1) I took several iterations and asserted a WRONG cause ("`SI_Fee` isn't the CBC code") because I **assumed instead of verifying the live mapping**. It WAS the right code — the scheme's CBC→`SI_Fee` price-setup mapping was soft-deleted (26 rows, all `is_deleted=true` → resolver returned null → amount silently 0.00). Root systemic gap: the KG modelled code STRUCTURE (reads/writes) but not the SILENT decision-points where bugs hide. That gap is now closed generally (below) — config-resolution is just the first catalogued class.

**The general failure-mode classes** (each has its own first live check): config_resolution (resolver→master mapping `is_deleted`) · silent_catch (swallowed API/precondition) · null/zero/empty_default (resolver input null) · state_gate (stuck; CAS/transition guard) · race_condition (reverts; `updated_on`/@Version) · ordering (stale downstream).

**Tooling built 2026-06-11 to make this no-miss (use FIRST, extend as new classes are found):**
- **`kg why <request>`** — every flow's silent decision-points + curated root-causes w/ live SQL. `kg why <symptom>` searches the catalog. Auto layer = `claude/kg/bin/build_failuremodes.py` (per-processor + injected-service silent surfaces, all flows). Extend the VERIFIED catalog: append a `diag` node (class·symptom·src·mechanism·depends·fails_to·diagnostic·fix) to `claude/kg/curated/diagnostics.jsonl` + `claude/kg/bin/build.sh`.
- Runbooks: `claude/runbooks/pinpoint-rca-playbook.md` (universal method) · `claude/runbooks/charge-amount-shows-zero.md` (the config-resolution example). Reference: `claude/accounting/charge-price-setup-resolution.md`. Canned SQL: `db-query.sh mfi_qa3 --canned 19-price-setup-resolution-by-scheme`.

Related: [[feedback_deep_rca_before_fix]], [[feedback_proof_backed_agent_discipline]] (widen-search + evidence-before-claim), [[reference_system_kg]], [[feedback_keep_knowledge_current]].
