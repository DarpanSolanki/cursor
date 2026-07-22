#!/usr/bin/env bash
# Local + cron entrypoints for intelligence automations (fast by default).
# Usage:
#   intel-automation.sh session|sync|sync-full|sanity|status|daily|weekly
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

cmd="${1:-session}"
shift || true

case "$cmd" in
  session)
    exec python3 scripts/testing/sync_engine.py fast-session "$@"
    ;;
  sync)
    exec python3 scripts/testing/sync_engine.py fast-sync "$@"
    ;;
  sync-full)
    exec python3 scripts/testing/super_agent.py sync --full "$@"
    ;;
  sanity)
    exec bash scripts/bin/workspace-sanity.sh --fast "$@"
    ;;
  status)
    exec python3 scripts/testing/sync_engine.py status "$@"
    ;;
  daily)
    # Weekday morning: session + sanity + status + gap miner (target <30s)
    python3 scripts/testing/sync_engine.py fast-session --quiet
    bash scripts/bin/workspace-sanity.sh --fast
    python3 scripts/testing/sync_engine.py status
    python3 scripts/lib/registry_proposals.py mine || true
    python3 -c "from ntest_telemetry import doctor_report, emit_quarantine_proposals; print(doctor_report()); emit_quarantine_proposals()" 2>/dev/null || true
    ;;
  weekly)
    # Heavy: full test intel + bus compact
    bash scripts/bin/super-agent.sh sync --full
    python3 scripts/testing/sync_engine.py compact-bus 2>/dev/null || true
    python3 scripts/lib/registry_proposals.py mine || true
    if [[ "${RUN_PLATFORM_SCAN:-0}" == "1" ]]; then
      bash scripts/bin/platform-scan.sh --with-kg
    fi
    ;;
  compact)
    exec python3 scripts/testing/sync_engine.py compact-bus "$@"
    ;;
  *)
    echo "Usage: intel-automation.sh session|sync|sync-full|sanity|status|daily|weekly" >&2
    exit 1
    ;;
esac
