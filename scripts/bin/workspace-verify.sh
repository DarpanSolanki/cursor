#!/usr/bin/env bash
# Back-compat entrypoint: older rules/tools call `workspace-verify.sh`.
# Keep it as a stable alias to the current “max-pass” workflow.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec bash "$ROOT/scripts/bin/workspace-max-pass.sh" "$@"

