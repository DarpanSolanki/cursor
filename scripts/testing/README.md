# Testing — use `ntest` only

**Entry:** `scripts/bin/ntest.sh` · **Doctor:** `./doctor.sh` or `make -C scripts doctor`

```bash
# Workspace health
./doctor.sh
make -C scripts doctor
ntest run workspace.doctor.services   # + HTTP service checks

# Quick test smoke (no LAN required)
ntest smoke --quick
ntest health accounting

# Registry hygiene
ntest validate

# DPIC live demo (one phase at a time)
ntest run dpic.demo.status
ntest run dpic.demo.phase1
ntest run dpic.demo.phase2
ntest run dpic.demo.phase3
ntest run dpic.demo.phase4

# Automation only
ntest run dpic.demo.all

# Autonomous API checks
scripts/bin/kg-switch.sh && scripts/bin/ntest.sh auto getLoanAccountOverviewDetails
ntest list | ntest smoke | ntest run dpic.overview_api
```

**Registry:** `registry.json` — correlators from `scripts/scratch/dpic_demo_state.env` after phase1.

**Self-learning:** `cursor-bundle/brain/testing/learnings.jsonl` — `ntest learn` / `test-learn.sh`; surfaced on failure via `analyze_failure`.

```bash
ntest learn --api disburseLoan --kind gotcha --text "..."
ntest learnings --api dpiAccrualBooking
```

Rule: `.cursor/rules/00-workspace-core.mdc`

**Internal-only APIs** (prod uses `CallInternalOrchestrationWithoutJson`): still need JTF templates in the **service repo** for `ntest` HTTP tests. See `.cursor/rules/20-ship-gates.mdc`. Example: `foreclosure.individual_child` → `individualChildLoanForeclosure`.
