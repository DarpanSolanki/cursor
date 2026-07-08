#!/usr/bin/env bash
# Build ADF JSON for SDCP fix handoff fields. No API calls — pipe into editJiraIssue.
# Usage: scripts/bin/jira-fix-handoff.sh rca "situation" "cause" "resolution"
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec python3 "$ROOT/scripts/bin/jira-fix-adf.py" "$@"
