<!-- VERBATIM archive of former alwaysApply `.cursor/rules/ship-loop-enforcement.mdc`. Do not soften. Edit thematic rules; keep this as mandate proof. -->

# Ship-path enforcement (all work types)

Workspace automation handles **any** implementation, fix, or analysis ship — not money-only.

## Tiers (highest wins when merging pending edits)

| Tier | Triggers | `ship-loop-gate` runs |
|------|----------|------------------------|
| **workspace** | `.cursor/`, `scripts/`, `cursor-bundle/`, `system_brain/`, `docs/` | `kg validate` + `ntest validate` (+ quick smoke if `scripts/testing` touched) |
| **service** | Any `novopay-*` / `trustt-*` code or deploy | `gradlew build` + registry API tests or **health** probes |
| **money** | Accounting/LOS/payments money processors, orch, batches, lib money paths | Full build + ntest + `smoke_tier=money` guards |

Hook: `.cursor/hooks/after-ship-path-edit.sh` → `.cursor/.pending-ship-work.json` (`tier`, `files`, `repos`, `apis`, `health_cases`).

## Close any task

```bash
cursor-bundle/kg/bin/changelog-add.sh --kg-flow "..." "apiName …"   # after service/money commit
bash scripts/bin/workspace-close.sh --from-pending
```

`workspace-close.sh` = KG fresh → **tier-aware** ship-loop → super-agent sync → knowledge gate → hygiene.

```bash
bash scripts/bin/workspace-close.sh --from-pending
bash scripts/bin/workspace-close.sh --from-pending --capture   # + capture-flow when CAPTURE_FTG set
python3 scripts/lib/infer_ship_apis.py --classify <path>       # inspect tier
```

## Push blocked when

- Pending ship files exist but `.ship-loop-passed.json` is stale or tier too low
- `.pending-kg-rebuild` without brain CHANGELOG update

## Agent discipline (all tasks)

- **Analysis / RCA:** bootstrap + KG orient — no money-only shortcut on expansion (`always-on.mdc`)
- **Workspace edits:** tier `workspace` — still run `workspace-close` before done
- **Service edits:** tier `service` — build + health/API test
- **Money edits:** tier `money` — full ship loop + optional `capture-flow`

## Registry

Add `scripts/testing/registry.json` cases for new APIs; tag `smoke_tier: smoke` (service) or `money` (financial).

Helper: `python3 scripts/lib/infer_ship_apis.py --path <file> --impact-json`

## If automation seems dead

1. `.cursor/hooks.json` exists and points to `after-ship-path-edit.sh`
2. Cursor → Settings → Hooks
3. `bash scripts/bin/enrichment-audit.sh`
4. Restart Cursor after hook install
