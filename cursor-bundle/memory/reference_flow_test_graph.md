# Flow Test Graph (FTG)

**Canonical:** `cursor-bundle/flow-test/flows.jsonl` + `sources.jsonl` + `README.md`  
**CLI:** `scripts/bin/ftg.sh` · enrich: `scripts/bin/ftg-enrich.sh --apply`

## vs KG

| | KG | FTG |
|---|-----|-----|
| Question | What runs? What tables? What broke before? | How do we **prove** it works? |
| Source | Code + orch XML + kg-flow precedents | flows.jsonl + **sources.jsonl** (ntest/disburse/unit) |
| Self-learning | `changelog-add.sh --kg-flow` | `ftg enrich --apply` after new tests |

## Enrichment loop

```
New test (ntest registry / make jlg / unit / SDCP fix)
  → optional: append sources.jsonl
  → ftg enrich --apply
  → ftg validate && ftg gaps
  → promote tier when gate passes
```

**Wave 1 (2026-06-19):** 24 flows, 39 sources, 3 money gaps left.

## Every money-path fix

1. Unit test (Gradle — local policy may exclude from push)
2. FTG row + sources line
3. `ftg enrich --apply` + validate + gaps
4. Promote tier after smoke/regression

## RCA order

memory → CANONICAL-MAP → `kg orient` → **`ftg show <request>`** → **`ftg sources --ftg <id>`** → XML → db-local
