---
name: workspace-self-improve
description: "Standing self-improvement loop for sliProd \u2014 corroborate, drain safe backlog, perf-first hooks. Use when user asks to improve workspace or \"super machine\"."
---

# Workspace self-improve

## When to use

- User: "improve workspace", "super machine", "setup yourself", "workspace max pass"
- After shipping infra/tooling — run quick verify
- **Not** on every money-path fix (use `ship-knowledge-gate.sh` instead)

## Super machine (complete stack)

```bash
bash scripts/bin/super-machine.sh              # loop (~5–8s) — default health check
bash scripts/bin/super-machine.sh corroborate  # cross-layer score only
bash scripts/bin/super-machine.sh weekly       # full sync + index rebuild (~1–3m)
```

## Fast path (default, ~3–8s)

```bash
bash scripts/bin/workspace-health.sh
bash scripts/bin/workspace-max-pass.sh
```

## Full verify (~30s, services must be up)

```bash
bash scripts/bin/workspace-max-pass.sh --full
bash scripts/bin/workspace-autopilot.sh verify
```

## Backlog

- File: `scripts/workspace-backlog.json`
- CLI: `python3 scripts/lib/workspace_backlog.py status`
- **auto_safe** items: agents may implement without user ask (perf/hooks only)
- **non auto_safe** (registry cases, KG build changes): propose first

## Perf rules (do not regress)

1. **Session start**: kg-session + intel-session (~5s max); corroborate every 6h only
2. **Corroborate --quick**: reads cached JSON only — no orch rglob, no KG rebuild
3. **registry-gaps**: uses `orch_api_index.json`; rebuild on `platform` layer stale only
4. **Smoke default**: skip `workspace-close` unless pending unsatisfied
5. **RCA**: autopilot runs `trace --fast` once — do not also run full orient

## After infra changes

1. `bash scripts/bin/super-machine.sh loop`
2. `bash scripts/bin/workspace-smoke.sh --quick`
3. Append `.cursor/changelog.md` (audit, kb-only)

## New repo / service (only time to revisit super machine)

1. Add repo under workspace root (`novopay-*` / `trustt-*`)
2. `bash scripts/bin/super-machine.sh weekly` — rebuilds orch index + contracts + KG
3. `flow-onboard.sh <apiName> --write` for money-path apis you touch
4. Append brain changelog if flow behaviour ships
