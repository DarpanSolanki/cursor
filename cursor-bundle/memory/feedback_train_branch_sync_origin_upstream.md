# Train branch: sync origin with upstream before analyse/push (STANDING)

**Rule:** On `mfi_integration_vX.Y.Z`, never analyse or push from a stale **origin-only** tip. Always work on **latest upstream** tip, then replay any unique origin (DarpanSolanki) commits, then push **origin only**.

## Mandatory steps

```text
Before analysis checkout OR push on train branch mfi_integration_vX.Y.Z:
  1. git fetch origin && git fetch upstream
  2. Ensure local train = upstream/mfi_integration_vX.Y.Z tip (checkout -B from upstream)
  3. Merge/rebase origin unique commits INTO that tip if worth keeping; prefer upstream base + cherry-pick Darpan commits
  4. Never analyse/push from origin tip behind upstream without saying STALE and syncing first
  5. Push result to origin only (never upstream)
```

**Why:** Origin often lags upstream after `trusttai` merges (e.g. origin 35 commits behind). Pushing a fix onto stale origin creates a fork tip that is not the next-release line.

**Cross-links:** [[feedback_jira_reported_version_branch]] (version → branch) → this sync → [[feedback_fetch_latest_before_checking_code]] · rule `.cursor/rules/10-quality-gates.mdc` · `scripts/bin/push-origin.sh`.

**Do not ask again** — apply on every train-branch RCA/port/push.
