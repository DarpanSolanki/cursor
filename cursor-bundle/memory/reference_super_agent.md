# Super agent — unified KG + test KG + skills

**CLI:** `bash scripts/bin/super-agent.sh` · **Skill:** `.cursor/skills/super-agent/SKILL.md`

## Cross-learn loop

```
ntest pass/fail ──► learning_bus.jsonl ◄── capture-flow / super-agent learn
        │                    │
        ▼                    ▼
 test_coverage.jsonl    test_hints.jsonl
        │                    │
        └──────► kg.db ◄─────┘  (build_test_map + build_cross_learn on sync)
```

## Commands

| Command | Purpose |
|---------|---------|
| `super-agent.sh session` | Session bootstrap |
| `super-agent.sh orient <api>` | KG + test + learnings + bus (one view) |
| `super-agent.sh sync [--kg]` | Cross-layer sync |
| `super-agent.sh gaps --money` | All-layer gap merge |
| `ntest map --api <api>` | Registry ↔ FTG row |
| `ntest smoke --tier smoke` | Tier gate |

## Proof gate

Structure from KG · proof from test_coverage · behaviour from XML + db-local.
