#!/usr/bin/env bash
# Print flowtest e2e lock status: held Y/N + owner metadata.
# Usage: bash scripts/bin/flowtest-lock-status.sh [--json]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
AS_JSON=0
for arg in "$@"; do
  case "$arg" in
    --json) AS_JSON=1 ;;
    -h|--help)
      echo "Usage: flowtest-lock-status.sh [--json]"
      exit 0
      ;;
  esac
done
export PYTHONPATH="${ROOT}/scripts/testing${PYTHONPATH:+:$PYTHONPATH}"
if [[ "$AS_JSON" -eq 1 ]]; then
  python3 - <<'PY'
from flowtest.lock import lock_status
import json
print(json.dumps(lock_status(), indent=2))
PY
else
  python3 - <<'PY'
from flowtest.lock import lock_status
st = lock_status()
held = "Y" if st["held"] else "N"
print(f"held={held} path={st['path']}")
if st.get("self_held"):
    print("self_held=Y (FLOWTEST_E2E_LOCK_HELD)")
if st.get("file_exists") and (st.get("pid") or st.get("case") or st.get("started_at")):
    live = st.get("pid_live")
    live_s = "?" if live is None else ("Y" if live else "N")
    print(
        f"owner pid={st.get('pid') or '-'} pid_live={live_s} "
        f"case={st.get('case') or '-'} started={st.get('started_at') or '-'}"
    )
    if st.get("cmdline"):
        print(f"cmdline={st['cmdline']}")
elif not st["held"] and st.get("file_exists"):
    print("file=present flock=free (stale metadata ok to clear)")
elif not st["held"]:
    print("no lock file")
PY
fi
