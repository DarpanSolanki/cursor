# Super machine — full automation (standing)

**User never runs scripts.** Agents never ask "run verify-dpi?" — the machine decides and runs.

## Test ladder (automatic)

| When | What runs | Trigger |
|------|-----------|---------|
| **Impact** | Minimal cases for diff (`resolve_ship_cases`) | ship-loop, every money/service ship |
| **Deep** | Path-aware slice (grace/multi/go-live, DCF, ICF) | Auto after impact PASS in ship-loop |
| **Release** | Expanded gate (`dpic.ud_compliance` profile, certify if certify paths) | Auto on `workspace-close` money tier (push gate) |
| **Post-commit** | impact + deep | `post-commit-ship-test.sh` hook (background) |
| **Hot-path perf** | `hot-path-scan.sh --from-pending` (WARN; STRICT=1 blocks money ship-loop) | Autopilot FIX+SHIP / FEATURE / CODE+DAO; money ship-loop |

Engine: `scripts/lib/ship_test_plan.py` · runner: `scripts/bin/ship-test-auto.sh` · perf: `scripts/lib/hot_path_scan.py`

## Agent loop (no manual gaps)

```
user message → super-machine handle → classify + preflight + trace
edit ship path → after-ship-path-edit → pending-ship-work.json
commit → post-commit-ship-test (impact+deep) + post-commit-kg-flag
test PASS → post-ntest-intel-sync → mark-verified → ship-and-continue (push)
session end / close → workspace-close → ship-loop (impact+deep+release) → knowledge gate
```

## What agents must not do

- Ask user to run `ntest`, `verify-dpi`, `workspace-close`, `kg-switch`
- Label release tests "manual only" — they run on money `workspace-close`
- Run full `extended_regression` on every touch — use `ship_test_plan` phases
- Ship money/API/batch fixes without hot-path scan on loop/DAO edits — see `10-quality-gates.mdc`

## Inspect plan (agents only)

```bash
python3 scripts/lib/ship_test_plan.py --path <file> --json
python3 scripts/lib/ship_test_plan.py --from-pending --json
```
