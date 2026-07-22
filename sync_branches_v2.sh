#!/usr/bin/env bash
# DEPRECATED — thin wrapper. Prefer: bash scripts/bin/sync-branches.sh --domain <d> --train …
# No interactive username/path prompts. Defaults: user=DarpanSolanki, root=this workspace.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
echo "⚠ sync_branches_v2.sh is deprecated — use scripts/bin/sync-branches.sh" >&2
echo "  (defaults: user=DarpanSolanki root=$ROOT; no interactive prompts)" >&2

TRAIN=""
USER="DarpanSolanki"
BASE="$ROOT"
EXTRA=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain|--train|--yes|-y|--user|--root|--help|-h)
      EXTRA+=("$1")
      if [[ "$1" == --domain || "$1" == --train || "$1" == --user || "$1" == --root ]]; then
        EXTRA+=("${2:-}"); shift 2
      else
        shift
      fi
      ;;
    --*)
      EXTRA+=("$1"); shift
      ;;
    *)
      if [[ -z "$TRAIN" ]]; then TRAIN="$1"
      elif [[ "$USER" == "DarpanSolanki" && "$1" != /* && "$1" != .* ]]; then USER="$1"
      else BASE="$1"
      fi
      shift
      ;;
  esac
done

ARGS=()
[[ -n "$TRAIN" ]] && ARGS+=(--train "$TRAIN")
ARGS+=(--user "$USER" --root "$BASE")
ARGS+=("${EXTRA[@]}")

# Legacy full-workspace calls need explicit --yes (foot-gun guard in sync-branches).
joined=" ${ARGS[*]} "
if [[ "$joined" != *" --domain "* && "$joined" != *" --yes "* && "$joined" != *" -y "* && "$joined" != *" --help "* && "$joined" != *" -h "* ]]; then
  ARGS+=(--yes)
  echo "  (legacy full-workspace → adding --yes)" >&2
fi

exec bash "$ROOT/scripts/bin/sync-branches.sh" "${ARGS[@]}"
