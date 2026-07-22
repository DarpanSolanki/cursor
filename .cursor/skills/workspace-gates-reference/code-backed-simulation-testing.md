<!-- VERBATIM archive of former alwaysApply `.cursor/rules/code-backed-simulation-testing.mdc`. Do not soften. Edit thematic rules; keep this as mandate proof. -->

# Code-backed simulation testing (platform suite enrichment)

## Why this exists

Ship-loop / workspace-close require a **verified** registry case. Full money-path E2E (maker-checker, child events batch, bank) is not always runnable in the same turn. Agents must **not** skip verification — they escalate down a ladder and **enrich** `scripts/testing/registry.json` so the platform suite grows.

## Verification ladder (strict order)

| Priority | Mode | Label | When allowed |
|----------|------|-------|--------------|
| 1 | Live API / flow + DB asserts | `RUNTIME_VERIFIED` | Service up, fixture LAN, stages completable |
| 2 | Staged real (reset → reach stage N → assert) | `STAGE_PARTIAL` | Early stages real; later stage blocked (document blocker) |
| 3 | Orchestration sibling parity from **disk XML** | `ORCH_SIBLING_SIM` | Parent/sibling Request already correct; child/async path must mirror beans |
| 4 | Processor / utility mirror reading **source .java** | `PROCESSOR_MIRROR_SIM` | Pure field-copy / formula; no Spring boot needed |

**Forbidden:** invented expected amounts, hand-wavy “should work”, chat-only reasoning without an artifact that cites orch `Request name=` or `file:line`.

## Code-backed means

1. **Orchestration** — parse real `deploy/application/orchestration/*.xml` (`Request name=…` → ordered `Processor bean=` / `API name=`). Helper: `scripts/testing/lib/orch_sibling_parity.py`.
2. **Processor mirror** — expected field list / formula extracted from the Java source under test (regex or shared constants), not from memory.
3. **Registry** — every sim/flow case has:
   - `"verify_mode": "runtime" | "stage_partial" | "orch_sibling_sim" | "processor_mirror_sim"`
   - `"api"` / `"apis"` for ship resolve
   - `"note"` stating what full E2E still needs
   - Prefer `"ship_auto": true` for money-path sims that gate the *exact* beans/logic changed
4. **Honest claims** — JIRA / ship notes say `ORCH_SIBLING_SIM` (or similar). Never claim “QA Pass” / “Result: Pass (scenario)” for sim-only.

## Real-flow first; sim only after real-flow is blocked

Simulation is priority 3–4 on the ladder — reach for it **only** after live/staged real-flow
(priority 1–2) is genuinely blocked, and say why. Even a code-backed sim must **cite the exact
expected DB writes** (table + column + value) it stands in for — never presence-only or a guessed
amount (`feedback_real_flow_db_write_validate.md`). When the real flow *can* run, it must read the
row back and assert column values; a passing sim does not substitute for real-flow value asserts on
the tables the fix writes.

## Prefer real — escalate only on blocker

Document the blocker in the case `note` or test stdout, e.g.:

- no foreclosed SHG fixture locally
- checker task / events queue batch not runnable this turn
- external bank / NEFT required for later stage

Then run the highest ladder step that still proves the **fix under review**. Prefer upgrading `*_sim` → realtime E2E in a later turn when fixtures exist.

## Agent checklist (every money/orch fix)

1. Resolve `apiName` → `ntest orient` / KG flow.
2. Prefer registry **runtime** / **flow** case; run it.
3. If blocked → add or extend a **code-backed sim** case (do not invent a one-off outside `registry.json`).
4. Wire domain: `scripts/lib/accounting_flow_domains.json` `impact_cases` / `api_hints`.
5. Run `ntest run <case_id>` (or `python3 …_sim.py`) and `mark-verified` / workspace-close.
6. Print: `Verify mode: RUNTIME_VERIFIED | ORCH_SIBLING_SIM | …` and `Blocker (if any): …`

## TDPQA-102 precedent

- Fix: `childLoanReopening` must include parent reopen’s `loanAccountPaymentsDetailsReversalProcessor` (+ tax reversal).
- Suite case: `reopening.child_payments_parity_sim` — orch sibling sim until full SHG reopen E2E fixture exists.

## Pair with

- `.cursor/rules/ship-test-mandatory.mdc`
- `.cursor/rules/workspace-developer-tester.mdc`
- `.cursor/rules/flow-cross-learn.mdc`
- Memory: `cursor-bundle/memory/feedback_code_backed_simulation_testing.md`
