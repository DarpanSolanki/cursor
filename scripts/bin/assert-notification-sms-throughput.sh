#!/usr/bin/env bash
# Assert SP-308 L0 SMS consumer throughput settings on the active notifications train.
# Fails closed if MessageBroker.xml is missing or still at the old 1/10 defaults.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
XML=""
for cand in \
  "$ROOT/trustt-platform-notifications/deploy/application/messagebroker/MessageBroker.xml" \
  "$ROOT/novopay-platform-notifications/deploy/application/messagebroker/MessageBroker.xml"
do
  if [[ -f "$cand" ]]; then
    XML="$cand"
    break
  fi
done
if [[ -z "$XML" ]]; then
  echo "assert-notification-sms-throughput: MessageBroker.xml not found" >&2
  exit 2
fi

python3 - "$XML" <<'PY'
import re, sys
from pathlib import Path
text = Path(sys.argv[1]).read_text(encoding="utf-8")
# Isolate the notification_sms_ consumer block
m = re.search(
    r"<topicPrefix>notification_sms_</topicPrefix>.*?</Consumer>",
    text,
    flags=re.S,
)
if not m:
    print("FAIL: notification_sms_ consumer block not found", file=sys.stderr)
    sys.exit(1)
block = m.group(0)
tm = re.search(r"<numberOfThreads>(\d+)</numberOfThreads>", block)
pm = re.search(r"<maxPollRecords>(\d+)</maxPollRecords>", block)
threads = int(tm.group(1)) if tm else -1
poll = int(pm.group(1)) if pm else -1
print(f"notification_sms_: threads={threads} maxPollRecords={poll} file={sys.argv[1]}")
ok = True
if threads < 4:
    print(f"FAIL: numberOfThreads={threads} expected >= 4 (SP-308 L0)", file=sys.stderr)
    ok = False
if poll < 50:
    print(f"FAIL: maxPollRecords={poll} expected >= 50 (SP-308 L0)", file=sys.stderr)
    ok = False
sys.exit(0 if ok else 1)
PY
