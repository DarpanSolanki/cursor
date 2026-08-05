#!/usr/bin/env bash
# Push to origin after ship-loop gate (auto workspace-close if pending).
#
# Train-branch sync-first (mfi_integration_vX.Y.Z / mfi_release_v*): before push,
# fetch origin+upstream and ensure HEAD includes upstream/<branch> tip. Machine
# gate: train-upstream-sync.sh (--sync if clean, else --check fail). Never push
# from an origin tip behind upstream. See:
#   .cursor/rules/upstream-mainline-push-sync.mdc
#   cursor-bundle/memory/feedback_train_branch_sync_origin_upstream.md
#   .cursor/rules/10-quality-gates.mdc
#
# Usage:
#   push-origin.sh                    # push current branch: git push -u origin HEAD
#   push-origin.sh origin my-branch   # pass through to git push
#   SHIP_PUSH_NO_AUTO_CLOSE=1 push-origin.sh …  # skip auto-close (fail if stale)
#   TRAIN_UPSTREAM_SYNC_SKIP=1 …      # skip upstream-ahead gate (rare; state aloud)
#   Knowledge OR workspace-harness-only HEAD auto-skips sticky money close
#   (see ship_push_gate.should_skip_auto_close_for_knowledge_head).
#   SHIP_CLOSE_REPO=trustt-platform-accounting   # scope pending → that repo only
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PENDING="$ROOT/.cursor/.pending-ship-work.json"
PASSED="$ROOT/.cursor/.ship-loop-passed.json"
GATE="$ROOT/scripts/lib/ship_push_gate.py"
TRAIN_SYNC="$ROOT/scripts/bin/train-upstream-sync.sh"

if [[ ! -x "$GATE" ]]; then
  GATE="python3 $ROOT/scripts/lib/ship_push_gate.py"
fi

# When invoked from a service repo checkout, scope auto-close to that repo so a
# train-branch push does not re-run the entire accumulated money pending suite.
_detect_ship_close_repo() {
  if [[ -n "${SHIP_CLOSE_REPO:-}" ]]; then
    echo "$SHIP_CLOSE_REPO"
    return 0
  fi
  local top base
  top="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  [[ -n "$top" ]] || return 0
  base="$(basename "$top")"
  case "$base" in
    trustt-*|novopay-*)
      if [[ "$top" == "$ROOT/$base" ]]; then
        echo "$base"
      fi
      ;;
  esac
}

_run_close_if_needed() {
  if [[ "${SHIP_PUSH_NO_AUTO_CLOSE:-}" == "1" ]]; then
    if python3 "$ROOT/scripts/lib/ship_push_gate.py" --needs-close 2>/dev/null; then
      echo "push-origin: ship loop stale — run: bash scripts/bin/workspace-close.sh --from-pending" >&2
      return 1
    fi
    return 0
  fi
  if ! python3 "$ROOT/scripts/lib/ship_push_gate.py" --needs-close 2>/dev/null; then
    return 0
  fi
  # Knowledge-only HEAD skip only when pending also has no service/money code paths.
  if python3 "$ROOT/scripts/lib/ship_push_gate.py" --skip-auto-close-knowledge 2>/dev/null; then
    echo "=== push-origin: knowledge/harness HEAD — skip money auto-close (pending GC'd for clean+pushed) ===" >&2
    return 0
  fi
  if python3 "$ROOT/scripts/lib/ship_push_gate.py" --is-knowledge-head 2>/dev/null; then
    echo "=== push-origin: HEAD is knowledge-only but pending has service/money — auto-close required ===" >&2
  fi
  local close_repo
  close_repo="$(_detect_ship_close_repo || true)"
  if [[ -n "$close_repo" ]]; then
    export SHIP_CLOSE_REPO="$close_repo"
    echo "=== push-origin: scoping ship-close to repo=$close_repo ===" >&2
  fi
  echo "=== push-origin: auto workspace-close (pending ship work) ===" >&2
  local -a close_args=(--from-pending)
  local api
  while IFS= read -r api; do
    [[ -n "$api" ]] && close_args+=(--api "$api")
  done < <(python3 "$ROOT/scripts/lib/ship_push_gate.py" --pending-apis)
  # Merge / sync commits: skip brain CHANGELOG hard-fail during close
  if python3 "$ROOT/scripts/lib/ship_push_gate.py" --is-merge-head 2>/dev/null; then
    export SHIP_CLOSE_ALLOW_MERGE=1
  fi
  bash "$ROOT/scripts/bin/workspace-close.sh" "${close_args[@]}"
}

_run_close_if_needed

# Mainline train: refuse push when behind upstream (auto-rebase if worktree clean).
_ensure_train_upstream() {
  if [[ ! -x "$TRAIN_SYNC" ]]; then
    chmod +x "$TRAIN_SYNC" 2>/dev/null || true
  fi
  if [[ ! -f "$TRAIN_SYNC" ]]; then
    echo "push-origin: WARN — train-upstream-sync.sh missing; skipping sync gate" >&2
    return 0
  fi
  if [[ -n "$(git status --porcelain 2>/dev/null || true)" ]]; then
    echo "=== push-origin: train upstream check (dirty — check only) ===" >&2
    bash "$TRAIN_SYNC" --check
  else
    echo "=== push-origin: train upstream sync (rebase onto upstream if behind) ===" >&2
    bash "$TRAIN_SYNC" --check --sync
  fi
}
_ensure_train_upstream

if [[ $# -eq 0 ]]; then
  set -- -u origin HEAD
fi

# Java comment volume on what is about to leave. push-origin runs `git push` in-process,
# so the beforeShellExecution pre-push hook never sees it — gate here or nowhere.
_comment_lint_outgoing() {
  local repo upstream_ref base
  repo="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  [[ -n "$repo" && "$repo" != "$ROOT" ]] || return 0
  [[ -z "${JAVA_COMMENT_LINT_SKIP:-}" ]] || { echo "push-origin: JAVA_COMMENT_LINT_SKIP set — comment lint skipped" >&2; return 0; }
  upstream_ref="$(git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null || true)"
  base="${upstream_ref:-}"
  [[ -n "$base" ]] || return 0
  git rev-parse --verify -q "$base" >/dev/null || return 0
  python3 "$ROOT/scripts/lib/java_comment_lint.py" --diff "$base" --repo "$repo" || {
    echo "push-origin: BLOCKED — strip the comments, amend, retry (JAVA_COMMENT_LINT_SKIP=1 to override)" >&2
    exit 1
  }
}
_comment_lint_outgoing

# Block upstream — origin only
for arg in "$@"; do
  if [[ "$arg" =~ upstream|khoslalabs|trusttai ]]; then
    echo "push-origin: blocked — use origin only (darpan boundary)" >&2
    exit 1
  fi
done

exec git push "$@"
