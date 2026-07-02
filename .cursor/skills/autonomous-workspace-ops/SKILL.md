---
name: autonomous-workspace-ops
description: >-
  Autonomous sliProd ops: when to auto-run agent-ops.sh, novopay-service.sh,
  novopay-logs.sh, dpi-sanity, ntest ensure. Use at session start, before tests,
  on failure, or when user asks for sanity.
---

# Autonomous workspace ops

Read `.cursor/rules/autonomous-workspace-ops.mdc` and `.cursor/workspace-ops-state.md`.

**Single entry:** `bash scripts/bin/agent-ops.sh before-test <apiName>` before any batch/DPI test.

**Never** skip ensure/sanity because a port is down. **Never** wait blind — `novopay-logs.sh snap`.
