#!/usr/bin/env bash
# INDIRECT (SU-STITCH-005): not listed in hooks.json by filename.
# Thin alias → kg-session-watermark.sh workspaceOpen (ops/manual refresh).
set -euo pipefail
ROOT="${CURSOR_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
exec "$ROOT/.cursor/hooks/kg-session-watermark.sh" workspaceOpen
