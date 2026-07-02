#!/usr/bin/env bash
# Triage discovery inbox → promote to gaps or dismiss.
# Usage:
#   brain-triage.sh list
#   brain-triage.sh promote DISC-20260619-120000 --gap-id GAP-070
#   brain-triage.sh dismiss DISC-20260619-120000 --reason "duplicate of GAP-018"
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec python3 "$ROOT/scripts/testing/brain_triage.py" "$@"
