<!-- VERBATIM archive of former alwaysApply `.cursor/rules/upstream-sync-no-unrelated-diff.mdc`. Do not soften. Edit thematic rules; keep this as mandate proof. -->

# Upstream sync: zero unrelated diff policy

When the user asks to move/port changes to another base branch (for example `mfi_integration_vX.Y.Z`), follow this mandatory gate before commit/push.

## Mandatory flow

1. Create/reset target branch from exact upstream base:
   - `git checkout -B <target-branch> upstream/<target-branch>`
2. Bring only intended files/commits for requested feature.
3. Run diff gate against upstream:
   - `git diff --name-only upstream/<target-branch>...HEAD`
4. Verify every changed file is in the approved feature scope.

## Hard stop conditions (no exceptions)

- If any unrelated file appears in the diff, STOP.
- Do not push until unrelated changes are reverted/removed.
- Do not justify “small” unrelated changes (formatting, moved processors, removed request blocks, etc.).
- Re-run the diff gate after cleanup and confirm clean scope.

## For orchestration/XML-heavy changes

- Validate with file-level diff for each changed XML:
  - only requested controls/validators/processors may change
  - no collateral replacements/removals
- If uncertain whether a diff is intended, ask user before push.

## Push checklist (must pass all)

- [ ] Branch is based on exact `upstream/<target-branch>` tip
- [ ] `git diff upstream/<target-branch>...HEAD` contains only approved files
- [ ] No internal docs/discussion files included
- [ ] User-requested scope only


## Sync-first gate (train branches — mandatory)

Before **analysis checkout** OR **push** on `mfi_integration_vX.Y.Z` (or any release-train branch):

1. `git fetch origin` and `git fetch upstream` separately (do not pass both remotes as one `git fetch` arg list).
2. Ensure local train = **`upstream/mfi_integration_vX.Y.Z` tip** (`git checkout -B mfi_integration_vX.Y.Z upstream/mfi_integration_vX.Y.Z`).
3. If `origin/mfi_integration_vX.Y.Z` has unique commits not in upstream: **rebase/replay** those onto the upstream tip (prefer upstream as base; cherry-pick Darpan-only commits). Do not analyse or push from an origin tip that is **behind** upstream.
4. If origin tip is behind upstream without sync: say **STALE**, sync first, then continue.
5. Push result to **origin only** (never upstream/`trusttai`). Use `bash scripts/bin/push-origin.sh` from the service repo when possible.

Pairs with: `feedback_train_branch_sync_origin_upstream.md`, `feedback_fetch_latest_before_checking_code.md`, `feedback_jira_reported_version_branch.md` (map Reported version → branch, then sync).
