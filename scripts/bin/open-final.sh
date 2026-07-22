#!/usr/bin/env bash
# Resolve workspace path(s) for a forwardable final file.
# Default: print absolute path(s) only — does NOT open the IDE.
# Opt-in open: --open flag, or OPEN_FINAL=1 in the environment.
# Usage:
#   bash scripts/bin/open-final.sh <path> [path2 ...]
#   bash scripts/bin/open-final.sh --open <path>
#   OPEN_FINAL=1 bash scripts/bin/open-final.sh <path>
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

do_open=0
if [[ "${OPEN_FINAL:-0}" == "1" ]]; then
  do_open=1
fi

args=()
for raw in "$@"; do
  case "$raw" in
    --open|-o)
      do_open=1
      ;;
    --help|-h)
      cat <<'EOF' >&2
Usage: bash scripts/bin/open-final.sh [--open|-o] <path> [path2 ...]

Default: print absolute path(s) only (no IDE open).
Open in Cursor only with --open / -o, or OPEN_FINAL=1.
EOF
      exit 0
      ;;
    -*)
      echo "ERROR: unknown flag: $raw (try --open or --help)" >&2
      exit 2
      ;;
    *)
      args+=("$raw")
      ;;
  esac
done

if [[ ${#args[@]} -lt 1 ]]; then
  echo "Usage: bash scripts/bin/open-final.sh [--open|-o] <path> [path2 ...]" >&2
  echo "Default: print path only. Pass --open or OPEN_FINAL=1 to open in Cursor." >&2
  exit 2
fi

paths=()
for raw in "${args[@]}"; do
  if [[ "$raw" = /* ]]; then
    p="$raw"
  else
    p="$ROOT/$raw"
  fi
  if [[ ! -e "$p" ]]; then
    echo "ERROR: not found: $p" >&2
    exit 1
  fi
  paths+=("$(realpath "$p")")
done

for p in "${paths[@]}"; do
  echo "$p"
done

if [[ "$do_open" -eq 1 ]]; then
  # -r = reuse window; no -d → editor buffer (final version), not side-by-side diff
  exec cursor -r "${paths[@]}"
fi
