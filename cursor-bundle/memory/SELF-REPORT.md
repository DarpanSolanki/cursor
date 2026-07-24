# SELF-REPORT — week of 2026-07-22

Generated: 2026-07-22T15:49:44Z · Upgrade 8 self-metrics

## Fixed tax
- alwaysApply bytes: **30120** / soft ceiling **35000** — OK
- largest offenders: 00-workspace-core.mdc=7855, 10-quality-gates.mdc=7449, darpan.mdc=5940, 30-kg-discipline.mdc=4544, 20-ship-gates.mdc=4332

## Speed (wall-clock by process class)
- `question`: p50=0.01s p95=0.01s n=1
- `read-only-rca`: p50=0.02s p95=0.02s n=1

## KG
- cache hit ratio (telemetry window): 0% (hit=0 miss=5)
- gate hits (PROVISIONAL): 8 — revisit kg-profiles.md if ≥8/week

## QA bar
- enforced acceptance domains: **4/21** — death_foreclosure, disbursement, repayment, foreclosure
- money verify_mode coverage: **56/56**
- proposals: total=20 drafts=2 gap_stubs=18
- flaky: flaky: demo.case: 2/3 fails

## Env / ratchets
- env-smoke: see `.cursor/workspace-ops-state.md` § Env smoke
- money-cell process ratchet + acceptance enforced_domains ratchet: active

## Red flags
- gap stubs still high (18)
- KG gate hits 8 — consider kg-profiles

## KG map-completeness
- map-completeness: overall=98.8% req=100.0% table=97.5% doc=392/392 topic=153 sched=16 excluded=4
- measured: 2026-07-23T08:46:54Z
## Self-upgrade (2026-07-23)
- unincorporated findings: 0 (oldest age n/a)
- unincorporated findings: 2 (oldest age 0d)
- query-gate runs=0 WARN=1 FAIL=0 (2026-07-24)
