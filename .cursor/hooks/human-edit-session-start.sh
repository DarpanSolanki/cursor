#!/usr/bin/env bash
# sessionStart — warn-only human-edit drift vs last session-close fingerprint.
set -euo pipefail
ROOT="${CURSOR_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
python3 "$ROOT/scripts/lib/human_edit_detect.py" start || true
echo '{}'
