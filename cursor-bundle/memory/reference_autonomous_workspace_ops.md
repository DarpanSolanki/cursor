---
name: reference_autonomous_workspace_ops
description: "Standing: agents auto-run agent-ops, novopay-service, novopay-logs, dpi-sanity — never skip sanity because port down"
metadata:
  node_type: memory
  type: reference
---

Session: read `.cursor/workspace-ops-state.md` (hook: `agent-ops.sh preflight`).

| Trigger | Command |
|---------|---------|
| Before batch/DPI/disburse test | `bash scripts/bin/agent-ops.sh before-test <apiName>` |
| After DPI Java change / sanity | `bash scripts/bin/agent-ops.sh verify-dpi` |
| Stuck / failed | `bash scripts/bin/novopay-logs.sh snap accounting` |
| ntest | auto before-test + on-failure (override: `NTEST_NO_ENSURE=1`) |

Compile on ensure **only when** `.java` newer than boot log (smart default).

Rule: `.cursor/rules/autonomous-workspace-ops.mdc`
