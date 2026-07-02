#!/usr/bin/env bash
# Onboard a new orchestration apiName into local test harness.
# Usage:
#   flow-onboard.sh loanPrepayment [--write] [--type flow] [--sibling dpic.dpi_sanity]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

API="${1:?apiName required}"
shift || true

WRITE=0
TYPE=api
SIBLING=""
CASE_ID=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --write) WRITE=1; shift ;;
    --type) TYPE="${2:?}"; shift 2 ;;
    --sibling) SIBLING="${2:?}"; shift 2 ;;
    --case-id) CASE_ID="${2:?}"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

echo "=== Flow onboard: $API ==="
echo ""
echo "## 1. Cross-repo trace"
python3 scripts/testing/flow_trace.py "$API" --fast || true
echo ""

echo "## 2. Registry gap check"
if python3 scripts/testing/ftg.py registry-gaps --money 2>/dev/null | rg -q "^${API}\t"; then
  echo "  MISSING from registry (money filter)"
elif python3 scripts/testing/ftg.py registry-gaps 2>/dev/null | rg -q "^${API}\t"; then
  echo "  MISSING from registry"
else
  echo "  Already in registry or not in orchestration scan"
fi
echo ""

echo "## 3. Scaffold"
SCAFF_ARGS=(scripts/testing/flow_scaffold.py "$API" --type "$TYPE")
[[ -n "$SIBLING" ]] && SCAFF_ARGS+=(--sibling "$SIBLING")
[[ -n "$CASE_ID" ]] && SCAFF_ARGS+=(--case-id "$CASE_ID")
[[ "$WRITE" -eq 1 ]] && SCAFF_ARGS+=(--write)

python3 "${SCAFF_ARGS[@]}"
echo ""

if [[ "$WRITE" -eq 1 ]]; then
  echo "## 4. Validate registry"
  python3 scripts/testing/registry_validate.py 2>/dev/null || python3 scripts/bin/ntest.sh validate 2>/dev/null || true
  echo ""
  echo "Next: edit request/expect, then: ntest run <case_id>"
else
  echo "Dry-run only. Re-run with --write to persist registry case."
fi
