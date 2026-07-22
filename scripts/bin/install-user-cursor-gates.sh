#!/usr/bin/env bash
# Install / verify Cursor hooks + git gates for sliProd.
# Canonical hooks live in .cursor/hooks.json (afterFileEdit → after-ship-path-edit.sh).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HOOKS="$ROOT/.cursor/hooks.json"
if [[ ! -f "$HOOKS" ]]; then
  echo "MISSING: $HOOKS" >&2
  exit 1
fi
if ! grep -q 'after-ship-path-edit.sh' "$HOOKS"; then
  echo "FAIL: hooks.json afterFileEdit must call after-ship-path-edit.sh" >&2
  exit 1
fi
if ! grep -q 'post-commit-ship-test.sh' "$HOOKS"; then
  echo "FAIL: hooks.json must wire post-commit-ship-test.sh on git commit" >&2
  exit 1
fi
# Optional: install kg git hooks into service repos
if [[ -x "$ROOT/scripts/bin/install-kg-git-hooks.sh" ]]; then
  bash "$ROOT/scripts/bin/install-kg-git-hooks.sh" || true
fi
echo "OK: Cursor hooks present (after-ship-path-edit + post-commit-ship-test)."
echo "Enable Hooks in Cursor Settings if not already on."
echo "Verify: bash scripts/bin/workspace-verify.sh"
