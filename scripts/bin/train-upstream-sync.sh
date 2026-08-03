#!/usr/bin/env bash
# Ensure local/origin train tip is not behind upstream before mainline push.
#
# Usage (from a service repo checkout):
#   train-upstream-sync.sh --check          # exit 2 if behind upstream
#   train-upstream-sync.sh --sync           # fetch + rebase onto upstream when clean
#   train-upstream-sync.sh --check --sync   # sync if behind and tree clean, else fail
#
# Env:
#   TRAIN_UPSTREAM_SYNC_SKIP=1  — no-op success (must be justified aloud by agent)
set -euo pipefail

MODE_CHECK=0
MODE_SYNC=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) MODE_CHECK=1; shift ;;
    --sync) MODE_SYNC=1; shift ;;
    -h|--help)
      sed -n '1,20p' "$0"
      exit 0
      ;;
    *)
      echo "train-upstream-sync: unknown arg: $1" >&2
      exit 1
      ;;
  esac
done

if [[ "$MODE_CHECK" -eq 0 && "$MODE_SYNC" -eq 0 ]]; then
  MODE_CHECK=1
fi

if [[ "${TRAIN_UPSTREAM_SYNC_SKIP:-}" == "1" ]]; then
  echo "train-upstream-sync: SKIP (TRAIN_UPSTREAM_SYNC_SKIP=1)" >&2
  exit 0
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "train-upstream-sync: not a git repo" >&2
  exit 1
fi

branch="$(git rev-parse --abbrev-ref HEAD)"
case "$branch" in
  mfi_integration_v*|mfi_release_v*)
    ;;
  *)
    echo "train-upstream-sync: branch=$branch — not a mainline train; skip"
    exit 0
    ;;
esac

if ! git remote get-url upstream >/dev/null 2>&1; then
  echo "train-upstream-sync: no upstream remote — skip (origin-only repo)" >&2
  exit 0
fi

echo "train-upstream-sync: fetch origin + upstream for $branch"
git fetch origin "$branch" 2>&1 | tail -3 || true
git fetch upstream "$branch" 2>&1 | tail -3 || true

if ! git rev-parse --verify "upstream/$branch" >/dev/null 2>&1; then
  echo "train-upstream-sync: upstream/$branch missing — skip" >&2
  exit 0
fi

behind="$(git rev-list --count "HEAD..upstream/$branch" 2>/dev/null || echo 0)"
ahead="$(git rev-list --count "upstream/$branch..HEAD" 2>/dev/null || echo 0)"
echo "train-upstream-sync: vs upstream/$branch — behind=$behind ahead=$ahead tip_local=$(git rev-parse --short=10 HEAD) tip_up=$(git rev-parse --short=10 upstream/$branch)"

if [[ "$behind" -eq 0 ]]; then
  echo "train-upstream-sync: OK — includes upstream tip"
  exit 0
fi

echo "train-upstream-sync: STALE — local is $behind commit(s) behind upstream/$branch" >&2

if [[ "$MODE_SYNC" -eq 1 ]]; then
  if [[ -n "$(git status --porcelain)" ]]; then
    echo "train-upstream-sync: cannot --sync with dirty worktree; commit/stash first" >&2
    exit 2
  fi
  echo "train-upstream-sync: rebasing onto upstream/$branch"
  git rebase "upstream/$branch"
  behind2="$(git rev-list --count "HEAD..upstream/$branch" 2>/dev/null || echo 0)"
  if [[ "$behind2" -ne 0 ]]; then
    echo "train-upstream-sync: still behind after rebase (behind=$behind2)" >&2
    exit 2
  fi
  echo "train-upstream-sync: synced — tip=$(git rev-parse --short=10 HEAD)"
  exit 0
fi

if [[ "$MODE_CHECK" -eq 1 ]]; then
  echo "train-upstream-sync: FAIL — run: bash scripts/bin/train-upstream-sync.sh --sync" >&2
  echo "  (or: git fetch upstream && git rebase upstream/$branch)" >&2
  exit 2
fi

exit 0
