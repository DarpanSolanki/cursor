# Legacy step scripts (milestone-by-milestone)

**Live QA demo:** use phased entry only:

```bash
bash scripts/dpic/demo/run_demo.sh phase1   # disburse + fast EOD
bash scripts/dpic/demo/run_demo.sh phase2   # APIs
bash scripts/dpic/demo/run_demo.sh phase3   # repayment
bash scripts/dpic/demo/run_demo.sh phase4   # reversal
bash scripts/dpic/demo/run_demo.sh status   # readiness
```

These `step_*.sh` files remain for **deep dives** (one EOD milestone per command):

| Script | Purpose |
|--------|---------|
| `step_00_setup.sh` | DB product 6367 setup |
| `step_01_disburse.sh` | Disburse only (no fast EOD) |
| `step_02` … `step_04b` | One DPI EOD date each |
| `step_05_apis_phase2.sh` | → delegates to `phase_02_show_apis.sh` |
| `step_06_foreclosure_phase3.sh` | Optional foreclosure sim (not in live 4-phase flow) |
| `step_07_loan_repayment.sh` | Called by `phase_03` |

Not registered in `ntest` — use `dpic.demo.phase1` … `phase4` instead.
