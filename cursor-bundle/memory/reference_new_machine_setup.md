# Standing up this workspace on a new machine

**One command, dry-run it first:**

```bash
bash scripts/bin/new-machine-setup.sh --dry-run   # shows every step, changes nothing
bash scripts/bin/new-machine-setup.sh             # or --no-clone for knowledge layer only
```

## Order matters

The KG snapshot restores **before** the repos are cloned, on purpose — accounting is 418MB and los
571MB, so the knowledge layer answers while ~10GB is still downloading. Same for the schema oracle:
`cursor-bundle/schema/tables.jsonl` is tracked, so `kg schema <table>.<column>` works on a fresh
clone with no database. Only a *rebuild* of the oracle needs local Yugabyte.

## The KG snapshot is branch-keyed — check it

```bash
bash scripts/bin/kg-snapshot.sh status    # MATCHES or STALE for this checkout
python3 cursor-bundle/kg/bin/kg.py fresh  # rebuild (40–70s) if STALE
bash scripts/bin/kg-snapshot.sh save      # after a good build, to re-ship it
```

The key is a hash of all 21 repos' `branch+HEAD+dirty`. A snapshot from a different branch mix is
stale by construction; never trust it silently.

## What ships in git, and why

| Tracked | Not tracked | Reason |
|---|---|---|
| `kg/snapshot/kg.jsonl` (19MB) | `kg/data/kg.db` (50MB), `kg/data/cache/` (620MB) | text diffs; sqlite and the 29-snapshot LRU do not |
| `schema/tables.jsonl` (1.6MB) | `schema/bindings.jsonl` (9.4MB) | tables need a live DB; bindings rebuild in ~1s from tracked Java |

The rule: **track what cannot be regenerated from tracked sources; ignore what can.**

## Stays manual

Local Yugabyte (localhost:5433), the local services (:8002 accounting, :8003 actor, :8013 los,
:8019 task, :8018 simulators, :9092 Kafka), and one interactive Atlassian MCP auth (`claude mcp`
or `/mcp`). These are machine state, not repo content.

## Branch drift

The setup clones `manifest.default_branch` from `.cursor/git-workspace-state.json` — the *declared*
train, not whatever the source machine drifted to. Scope deliberately afterwards:
`bash scripts/bin/sync-branches.sh --train <mfi_integration_vX.Y.Z> --yes`.

Related: [[feedback_schema_oracle_before_column_claims]], [[feedback_train_branch_sync_origin_upstream]].
