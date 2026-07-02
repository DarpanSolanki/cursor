# Accounting ALL-flow coverage (STANDING)

**Not money-only.** accounting-v2 has ~358 orchestration apiNames across read, write, batch, EOD, and money paths.

## Domain map

`scripts/lib/accounting_flow_domains.json` — 18 domains. Report:

```bash
bash scripts/bin/accounting-flow-coverage.sh
bash scripts/bin/accounting-flow-proof.sh
```

## Ship-loop tiers

| Tier | What runs on accounting edit |
|------|---------------------------|
| **service** | `health.accounting`, domain impact case (e.g. `accounting.read_smoke`, `batch.interest_*`, `accounting.eod_core_batches`) |
| **money** | Above + domain money guards (disburse, repayment, foreclosure, DPI SQL proof) |

## Gap reality

Registry covers ~30 apiNames; ~328 accounting apis still have no ntest row. Coverage report lists gap **per domain** — use it before claiming "tested".

Rule: `.cursor/rules/accounting-full-flow-gate.mdc`
