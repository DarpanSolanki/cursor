#!/usr/bin/env bash
# Super machine — single entry for the full intelligence stack.
#
# Usage:
#   super-machine.sh              # loop: session + corroborate + status (~5–8s)
#   super-machine.sh loop
#   super-machine.sh handle "fix dpi billing on LAN 6004044425"
#   super-machine.sh trace loanPrepayment
#   super-machine.sh corroborate [--full]
#   super-machine.sh sync [--full]
#   super-machine.sh weekly       # full corroborate + intel weekly (~1–3m)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SA="$ROOT/scripts/bin/super-agent.sh"

cmd="${1:-loop}"
shift || true

case "$cmd" in
  loop)
    exec "$SA" loop "$@"
    ;;
  handle|task)
    exec "$SA" handle "$@"
    ;;
  trace|orient|onboard|gaps|learn|sync|session|status|corroborate)
    exec "$SA" "$cmd" "$@"
    ;;
  weekly)
    echo "=== super-machine weekly ==="
    "$SA" sync --full --verbose || true
    python3 "$ROOT/scripts/testing/corroborate.py" --full || true
    python3 "$ROOT/scripts/testing/orch_index.py" --rebuild || true
    bash "$ROOT/scripts/bin/intel-automation.sh" compact 2>/dev/null || true
    bash "$ROOT/scripts/bin/workspace-smoke.sh" --quick || true
    echo "=== weekly done ==="
    ;;
  help|-h|--help)
    sed -n '2,12p' "$0" | tr -d '#'
    ;;
  *)
    echo "Unknown: $cmd (try: loop | handle | trace | corroborate | sync | weekly)" >&2
    exit 1
    ;;
esac
