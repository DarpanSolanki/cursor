# Runbook — Pinpoint RCA for ANY accounting issue (the method)

> The general method to go from a symptom to a file:line + live-data root cause in the fewest iterations.
> Pairs with the KG failure-mode layer: **`kg why <request>`** (silent decision-points of the whole flow)
> and the curated diagnostics in `claude/kg/curated/diagnostics.jsonl`.
> Companion deep-dives: [`charge-amount-shows-zero.md`](charge-amount-shows-zero.md) (the config-resolution class).

## Why this exists

Most slow RCAs come from one mistake: **guessing a cause instead of locating the decision-point that produced the observed value, then confirming it on live data.** The reads/writes graph shows *structure*; bugs live in the **silent branches** (return 0 / null / empty / swallowed catch / state gate / config-resolution-returns-null) that structure can't show. This runbook makes that search mechanical.

## The 5 steps (every issue)

1. **Name the observable precisely.** Not "foreclosure broken" — "CBC Fee shows ₹0.00 on the foreclosure quote screen for LAN X". The screen + field + the exact wrong value. A wrong *value* and a *missing* value and a *stuck* state are three different searches.

2. **Find the producing flow + decision-point — do NOT grep blind.**
   - `kg why <request>` → the silent-failure surface of the **whole flow** (every invoked processor's zero/null/empty/swallowed-catch points, file:line) + any curated root-cause.
   - `kg flow <request>` (processor order) · `kg crud <request>` (read-set/write-set) to see what the flow touches.
   - `brain-find` → the flow's brain doc for the intended behaviour.
   - Which request serves the screen? Trace the orchestration `<Request>` (e.g. the foreclosure quote = `fetchLoanForeclosureSimulationDetails`). The resolver/computation processor is the pinpoint, **not** the screen.

3. **Classify the failure mode** (this picks the live check):
   | Class | Tell | First live check |
   |---|---|---|
   | **config_resolution** | amount/field is 0/blank but txn data exists | the master/price-setup mapping — **incl. `is_deleted`** + type/sub_type (see charge-amount-shows-zero.md) |
   | **silent_catch** | "nothing happened", no error, partial state | the API/precondition the catch swallows; the row that should have been written |
   | **null/zero/empty_default** | wrong/zero value computed | the resolver input that was null → which branch returned the default |
   | **state_gate** | stuck / not progressing | the status column + the CAS/transition guard; maker-checker/task rows |
   | **race_condition** | value reverts / lost update | `updated_on`/`updated_by` vs the writer log; multi-writer row + @Version |
   | **ordering** | downstream sees stale/missing | processor order in `kg flow`; batch dependency |

4. **Confirm on live data BEFORE proposing a fix.** Each class above maps to a concrete `db-query.sh mfi_qa3 --sql`. Prove which branch fired — quote the row(s). Compare against a *working* case (another scheme/LAN). Never assert a cause you haven't seen in the data this turn (proof-backed gate).

5. **State the fix as data/config/code delta + the expected post-fix value.** "Activate 1 CBC mapping → CBC Fee = ₹89,988". Then it's QA-verifiable.

## Anti-patterns (what cost iterations before)

- Assuming a code↔config match (e.g. "`SI_Fee` isn't the CBC code") instead of **querying the live mapping**. It WAS the code — the mapping was soft-deleted.
- Reading the screen/view processor when the value is produced by a **different** resolver (view of an initiated foreclosure vs the live simulation quote).
- Treating a "shows 0" bug as missing transactional data when it's a **config-resolution null** (the data was fine).
- Grepping code before `kg why`/`kg flow`/`brain-find` (violates the §2 precedence ladder).

## Extending the knowledge (so the next one is instant)

When you root-cause a new class of issue, **capture it** — don't let it evaporate:
- Add a verified `diag` node (+edges) to [`claude/kg/curated/diagnostics.jsonl`](../kg/curated/diagnostics.jsonl): `class · symptom · src(file:line) · mechanism · depends · fails_to · diagnostic(live SQL) · fix`, then `claude/kg/bin/build.sh`.
- If it's a recurring symptom, add a row to the runbook index + the `lms-debug` symptom map.
- The auto layer (`build_failuremodes.py`) already lists every processor's silent branches; the curated layer is where the **verified root cause + live SQL** lives.
