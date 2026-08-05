# A gate you have never seen FAIL is not a gate

**Why:** The 2026-08-04 workspace audit found gates that had been green for weeks while
proving nothing:

- `flowtest.invariants_universal` (money tier) called
  `run_universal_invariants(lans, baseline=snapshot_invariants(lans))` — the baseline was
  taken moments before the comparison, so every baseline-delta invariant was neutralised.
  It returned 0 on any state. Worse, `impact_tests.py` uses it as the *substitute* for
  skipped sibling/domain cases ("invariant-guarded smoke replaces N cases") — so the ship
  loop was buying speed by swapping real regression coverage for a no-op.
- `assert-notification-sms-throughput.sh` asserted an SP-308 uplift that exists on **no**
  train — permanently red, therefore ignored.
- `local_parity_gate` harvested table names from `UPDATE/FROM/JOIN` clauses, so a
  `CREATE TEMP TABLE` in a local purge script logged a fake money-table DDL hand-patch and
  kept the gate red for a week.
- 24 gate unit tests existed; **2** were ever run. 5 were broken.

**How to apply:**

1. **Prove the failure path.** Before trusting a gate, make it fail on purpose — a forced
   violation, a synthetic bad input, a mocked reading. `test_invariants_gate.py` pins five
   absolute violations plus a guard that the runner never self-baselines again.
2. **A permanently-red gate is as broken as a permanently-green one.** Both get ignored.
   If it can never pass, it encodes an aspiration, not a contract.
3. **Never substitute broad coverage for a narrow gate you have not proven fail-closed.**
4. **Wire it, then verify the wiring.** `harness_audit.py --quick` checks every
   `*_gate` / `assert-*` / `audit-*` is transitively reachable from a ship host. Match both
   the filename and the python module stem — `import reuse_query_gate` does not contain
   `reuse_query_gate.py`, and matching only the filename reports false "unwired".
5. **Latency asserts do not belong in a correctness sweep.** They flake under any
   concurrent load. Gate correctness always; measure speed separately
   (`KG_MCP_TEST_TIME_FACTOR`).

6. **Failable is not the same as reached.** (2026-08-05) `ship-loop-gate.sh` called
   `harness_audit.py --quick`, whose own help says "skip syntax + tests". Four red self-test
   files were therefore invisible to the blocking path for as long as they had been broken.
   A gate that runs in a mode that skips the check is a gate you do not have — read the mode
   flag at the call site, not just the gate's own code. Ship mode is now `--tests-fast`.
7. **A gate must be train-aware or it asserts an aspiration.** Three of those four files
   failed only because `batchnew/dpi/` is absent on 3.4.2.x while the tests asserted DPI cases
   unconditionally. Guard with `skipUnless(_dpi_tree_present())` rather than letting a test go
   permanently red — permanent red trains people to ignore the suite.
8. **A test that backs up shared state has not isolated it.** `test_session_ship` saved and
   restored `.ship-loop-passed.json` but never cleared it, so the real file answered
   "already satisfied" instead of the state under test. Clear in `setUp`; restore in `tearDown`.

Related: [[feedback_worktree_bypasses_all_gates]], [[feedback_money_behavior_parity_no_amount_only_ship]],
[[feedback_ship_test_autonomy_change_map]], [[feedback_schema_oracle_before_column_claims]].
