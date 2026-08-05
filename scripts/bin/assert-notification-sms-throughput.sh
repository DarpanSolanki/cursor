#!/usr/bin/env bash
# Report notification_sms_ consumer throughput (SP-308 L0) for the checked-out
# notifications train. Trains diverge in both directions — a value on one train
# implies nothing about another. FAILS only for trains named in --require-trains.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

REQUIRE_TRAINS=""
MIN_THREADS=4
MIN_POLL=50
while [[ $# -gt 0 ]]; do
  case "$1" in
    --require-trains) REQUIRE_TRAINS="${2:-}"; shift 2 ;;
    --min-threads)    MIN_THREADS="${2:-4}";   shift 2 ;;
    --min-poll)       MIN_POLL="${2:-50}";     shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

REPO=""
for cand in "$ROOT/trustt-platform-notifications" "$ROOT/novopay-platform-notifications"; do
  [[ -f "$cand/deploy/application/messagebroker/MessageBroker.xml" ]] && { REPO="$cand"; break; }
done
if [[ -z "$REPO" ]]; then
  echo "notification_sms_: notifications repo not checked out — SKIP"
  exit 0
fi
XML="$REPO/deploy/application/messagebroker/MessageBroker.xml"
BRANCH="$(git -C "$REPO" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"

python3 - "$XML" "$BRANCH" "$REQUIRE_TRAINS" "$MIN_THREADS" "$MIN_POLL" <<'PY'
import re, sys
from pathlib import Path

xml, branch, require, min_threads, min_poll = sys.argv[1:6]
min_threads, min_poll = int(min_threads), int(min_poll)
text = Path(xml).read_text(encoding="utf-8")

m = re.search(r"<topicPrefix>notification_sms_</topicPrefix>.*?</Consumer>", text, flags=re.S)
if not m:
    print(f"notification_sms_: consumer block absent on {branch} — SKIP")
    sys.exit(0)

block = m.group(0)
tm = re.search(r"<numberOfThreads>(\d+)</numberOfThreads>", block)
pm = re.search(r"<maxPollRecords>(\d+)</maxPollRecords>", block)
threads = int(tm.group(1)) if tm else -1
poll = int(pm.group(1)) if pm else -1
print(f"notification_sms_: threads={threads} maxPollRecords={poll} branch={branch}")

required = {t.strip() for t in require.split(",") if t.strip()}
if branch not in required:
    note = "no train declared" if not required else f"declared={sorted(required)}"
    print(f"SP-308 uplift not required on {branch} ({note}) — report only")
    sys.exit(0)

ok = True
if threads < min_threads:
    print(f"FAIL: numberOfThreads={threads} expected >= {min_threads} on {branch}", file=sys.stderr)
    ok = False
if poll < min_poll:
    print(f"FAIL: maxPollRecords={poll} expected >= {min_poll} on {branch}", file=sys.stderr)
    ok = False
sys.exit(0 if ok else 1)
PY
