# SELF-REPORT — week of 2026-07-24

Generated: 2026-07-24T23:16:14Z · Upgrade 8 self-metrics

## Fixed tax
- alwaysApply bytes: **31972** / soft ceiling **35000** — OK
- largest offenders: 00-workspace-core.mdc=8953, 10-quality-gates.mdc=7717, darpan.mdc=5940, 20-ship-gates.mdc=4818, 30-kg-discipline.mdc=4544

## Speed (wall-clock by process class)
- `batch-dpi`: p50=0.01s p95=0.01s n=5
- `docs-kb`: p50=0.02s p95=0.02s n=3
- `money-fix`: p50=0.01s p95=0.02s n=8
- `non-money-fix`: p50=0.01s p95=0.02s n=29
- `question`: p50=0.01s p95=0.02s n=22
- `read-only-rca`: p50=0.01s p95=0.02s n=20

## KG
- grep-leak shell counter (cumulative jsonl lines): **2** (baseline sessions 172 grep / 50 kg — 2026-07-27)
- cache hit ratio (telemetry window): 0% (hit=0 miss=12)
- gate hits (PROVISIONAL): 8 — revisit kg-profiles.md if ≥8/week
- map-completeness: map-completeness: overall=98.8% req=100.0% table=97.5% doc=393/393 topic=153 sched=16 excluded=4

## QA bar
- enforced acceptance domains: **4/21** — death_foreclosure, disbursement, repayment, foreclosure
- money verify_mode coverage: **73/73**
- flow-coverage (live harness YES): **16/35 (45.7%)**
- SU-FLOW backlog count: **6**
- proposals: total=519 drafts=495 gap_stubs=18
- flaky: flaky: batch.interest_accrual_posting: 10/10 fails; flowtest.part_prepayment: 9/9 fails; flowtest.loan_prepayment_fc: 7/8 fails; dcf.group_parent_last_child_e2e: 6/10 fails; dpic.overview_api: 6/6 fails; dcf.group_parent_last_child_e2e_clean: 5/7 fails; disbursement.quick: 5/7 fails; flowtest.repayment_reversal: 5/6 fails; dpic.summary_api: 4/4 fails; dcf.vikram_fc_rstcre_dfc_e2e: 4/5 fails; ntest.dcf_e2e_fail_exit.sim: 3/10 fails; dpic.part_prepayment_write_e2e: 3/3 fails; dpic.foreclosure_bpd_day_window_sim: 3/3 fails; dcf.group_parent_last_child_fresh_e2e: 3/5 fails; demo.case: 2/3 fails

## Env / ratchets
- env-smoke: see `.cursor/workspace-ops-state.md` § Env smoke
- money-cell process ratchet + acceptance enforced_domains ratchet: active
- flow_coverage.json ratchet: harness_ready YES count must not decrease
- flow_coverage YES↔registry expect: scripts/lib/flow_coverage_gate.py (doctor WARN)

## Red flags
- gap stubs still high (18)
- KG gate hits 8 — consider kg-profiles

