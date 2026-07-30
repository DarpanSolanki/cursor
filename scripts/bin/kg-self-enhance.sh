#!/usr/bin/env bash
# Self-enhance trustt-kg after curated/diag/learning edits:
#   validate → rebuild (cache-aware) → fresh → optional align assert.
#
# Usage:
#   scripts/bin/kg-self-enhance.sh
#   scripts/bin/kg-self-enhance.sh --repo trustt-platform-accounting --branch mfi_integration_v3.5.2.2
#   scripts/bin/kg-self-enhance.sh --force
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

FORCE=0
REPO=""; BRANCH=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --force) FORCE=1; shift ;;
    --repo) REPO="${2:-}"; shift 2 ;;
    --branch) BRANCH="${2:-}"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 2 ;;
  esac
done

echo "=== kg-self-enhance: validate curated + rebuild ==="
if [[ "$FORCE" == "1" ]]; then
  bash "$ROOT/scripts/bin/kg-switch.sh" --force
else
  bash "$ROOT/scripts/bin/kg-switch.sh"
fi
python3 "$ROOT/cursor-bundle/kg/bin/kg.py" validate
python3 "$ROOT/cursor-bundle/kg/bin/kg.py" fresh
if [[ -n "$REPO" && -n "$BRANCH" ]]; then
  python3 "$ROOT/cursor-bundle/kg/bin/kg.py" align --repo "$REPO" --branch "$BRANCH"
fi
echo "=== kg-self-enhance: OK ==="
