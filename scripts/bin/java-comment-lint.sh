#!/usr/bin/env bash
# Fail-closed Java comment verbosity lint (DPI paths). Agents only.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec python3 "$ROOT/scripts/lib/java_comment_lint.py" "$@"
