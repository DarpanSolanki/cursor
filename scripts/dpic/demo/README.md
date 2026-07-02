# DPIC QA presentation — 4 phases (run **one at a time**)

Accounting `:8002`, task `:8019`, Yugabyte `:5433`. Anchor date = **calendar today** (IST).

## Live demo commands

```bash
# Check LAN + which phase is ready
bash scripts/dpic/demo/run_demo.sh status

# Phase 1 — fresh LAN + fast EOD (~25s)
bash scripts/dpic/demo/run_demo.sh phase1

# Phase 2 — GET APIs, DPI keys (~5s) — needs phase1 state
bash scripts/dpic/demo/run_demo.sh phase2

# Phase 3 — loanRepayment (~3s) — needs phase1
bash scripts/dpic/demo/run_demo.sh phase3

# Phase 4 — reversal INITIATE + APPROVE (~5s) — needs phase3
bash scripts/dpic/demo/run_demo.sh phase4
```

First-time DB seed (once per environment):

```bash
SKIP_SETUP=0 bash scripts/dpic/demo/run_demo.sh phase1
```

Optional pause before continuing: `INTERACTIVE=1 bash scripts/dpic/demo/run_demo.sh phase2`

Via ntest:

```bash
ntest run dpic.demo.status
ntest run dpic.demo.phase1
ntest run dpic.demo.phase2
ntest run dpic.demo.phase3
ntest run dpic.demo.phase4
```

**Do not** run `all` during presentation — automation/CI only:

```bash
bash scripts/dpic/demo/run_demo.sh all   # or: ntest run dpic.demo.all
```

## What each phase does

| Phase | Time | Show QA |
|-------|------|---------|
| **1** | ~25s | New LAN; fast EOD May15→Jun16; state → `scripts/scratch/dpic_demo_state.env` |
| **2** | ~5s | Overview `dpi_*`; Summary `dpi_details`; Basic baseline |
| **3** | ~3s | `loanRepayment`; `dpi_overdue→0`, `dpi_paid>0` |
| **4** | ~5s | `loanAccountTransactionReversal` 30375 → 30376; DPI back overdue |

## Product 6367 setup (negative schedule fix)

Loan product **2886** must use `installment_multiples_of=ZERO` (not `THOUSAND`).  
Applied by `scripts/dpic/sql/setup_local_dev_product_6367.sql` section A0.  
`THOUSAND` + ₹50k/24mo rounds EMI to ₹3000 and produces **negative tail PRIN/INT**.

## Phase 4 prerequisites

- Task `mfi_integration_v3.3.1.1` on `:8019`, actor `:8003`
- `DEMO_REVERSAL_USER_ID=53` in `demo_config.env`
- `operation_mode=SELF` on reversal headers (handled in scripts)

## Speed

- Phase 1: quarantine portfolio + 0.5s batch poll (not full `run_eod.sh`)
- Phase 3: skips full `demo_status.sql` unless `DEMO_SHOW_STATUS=1`
- Phase 2: curl-only API keys (no ntest during presentation)

## DB verify after demo

```bash
psql ... -v loan_account_id=<id> -f scripts/dpic/demo/sql/demo_status.sql
```

## Legacy milestone scripts

See `legacy/README.md` (`step_00` … `step_07`) — not used in live 4-phase flow.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `no demo state` on phase2+ | Run `phase1` first |
| Negative PRIN/INT on schedule | Re-run `bash scripts/dpic/run_setup.sh` + fresh `phase1` |
| Phase 4 fails on task | Task branch `mfi_integration_v3.3.1.1`, setup SQL for `task_activity` |
| Phase 3 no overdue | Re-run `phase1` (loan already repaid/reversed) |
