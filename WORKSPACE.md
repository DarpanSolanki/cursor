# sliProd workspace — local machine layout

**Path:** `/home/darpan/Documents/sliProd/`

## What agents use (in order)

| # | Layer | Path | Purpose |
|---|-------|------|---------|
| 1 | Memory | `cursor-bundle/memory/MEMORY.md` | Standing corrections |
| 2 | Brain | `cursor-bundle/brain/` | Flows, runbooks, engines, accounting |
| 3 | KG | `cursor-bundle/kg/bin/kg.py` | Processor chains, `why`, CRUD blast-radius |
| 4 | Agent KB | `.cursor/` | Gaps, orchestration map, event registry, rules |
| 5 | Ops notes | `system_brain/` | Symptom-first edge cases |
| 6 | Local DB | `scripts/db-local.sh` | Read-only localhost:5433 |
| 7 | Code | `novopay-*`, `trustt-*` | Source (each own git repo) |

## Quick commands

```bash
# Branch snapshot
for d in /home/darpan/Documents/sliProd/*/; do
  [ -d "$d/.git" ] || continue
  printf "%-40s %s\n" "$(basename "$d")" "$(git -C "$d" rev-parse --abbrev-ref HEAD)"
done

# KG
python3 cursor-bundle/kg/bin/kg.py why disburseLoan
python3 cursor-bundle/kg/bin/kg.py flow disburseLoan
cursor-bundle/kg/bin/build.sh

# Local DB (read-only)
scripts/db-local.sh --sql "SELECT 1"
scripts/db-local.sh --canned 01-loan-status-by-lan --param account_number=<LAN>

# Local DB reset (when user asks)
psql -h localhost -p 5433 -U yugabyte -d yugabyte -v ON_ERROR_STOP=1 \
  -f scripts/local_reset_disburse_loan_replay_mfi_yugabyte.sql

# Build a service
cd novopay-platform-accounting-v2 && ./gradlew build -x test
```

## Local DB defaults

| Setting | Value |
|---------|-------|
| Host | `localhost` |
| Port | `5433` |
| Database | `yugabyte` |
| User / password | `yugabyte` / `yugabyte` |
| Schema | `mfi_accounting` |

No QA/VPN database in this workspace.

## Rules

- `.cursor/rules/darpan.mdc` — pinpoint RCA + local setup
- `.cursorrules` — architect standards

## Docs & scripts

- `docs/` — feature docs, TRDs, archived notes (not in service git)
- `scripts/` — disburse sanity, local SQL resets, `db/canned/` diagnostics

## Removed (clutter)

- `cursor-bundle/db-tools/` — QA VPN DB (replaced by `scripts/db-local.sh`)
- `.cursor/brain/` — duplicate of `cursor-bundle/brain/`
- `.cursor/documentation/` — stale remote (`aitdp`) paths
- `aicodegen/` — unused duplicate at workspace root
