# Workspace disk clean (standing)

**When:** User or agent asks to clean workspace / large logs / reclaim disk.

**Command (preferred):**
```bash
bash scripts/bin/super-agent.sh clean --apply
```

**Safe targets:** `logs/*/archived`, `logs/*/archive` (logback rotation — not used by `novopay-logs.sh` which reads active `*-mfi.log`). Also scratch, `scripts/**/__pycache__`, KG cache LRU (hygiene).

**Do NOT delete:** `deploy/application/dist/*.jar` (optional deploy artifacts), active logs when `gradle bootRun` is running for that repo, `cursor-bundle/kg/data/kg.db`, brain docs.

**Automation:** `workspace-max-pass.sh`, `workspace-autopilot.sh end` run disk-clean before hygiene.
