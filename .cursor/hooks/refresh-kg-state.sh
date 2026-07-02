#!/usr/bin/env bash
# workspaceOpen — refresh .cursor/workspace-kg-state.md (KG fresh + watermark).
set -euo pipefail
ROOT="${CURSOR_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
exec "$ROOT/.cursor/hooks/kg-session-watermark.sh" workspaceOpen
