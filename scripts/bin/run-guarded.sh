#!/usr/bin/env bash
# Minimal wrapper used by ship-loop tooling.
# Provides a stable entrypoint even if advanced guardrails are absent.
set -euo pipefail

SOURCE_LABEL=""
if [[ "${1:-}" == "--source" ]]; then
  SOURCE_LABEL="${2:-}"
  shift 2
fi

if [[ "${1:-}" != "--" ]]; then
  echo "run-guarded.sh: expected '--' delimiter (source=${SOURCE_LABEL:-unknown})" >&2
  exit 2
fi
shift

[[ -n "$SOURCE_LABEL" ]] && echo "→ run-guarded ($SOURCE_LABEL)"
exec "$@"

