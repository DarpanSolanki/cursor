#!/usr/bin/env bash
# Curated use-case runner. List registered flows or run one by id.
#   scripts/testing/run.sh list
#   scripts/testing/run.sh dpic.full
#   LOAN_ACCOUNT_ID=8055060 scripts/testing/run.sh dpic.eod
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
UC_FILE="$ROOT/scripts/testing/usecases.json"

usage() {
  echo "Usage: $(basename "$0") list | <usecase-id>"
  echo "Registry: $UC_FILE"
  exit "${1:-0}"
}

[[ $# -ge 1 ]] || usage 1

if [[ "$1" == "list" || "$1" == "-h" || "$1" == "--help" ]]; then
  python3 - "$UC_FILE" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
for uid, meta in sorted(data.items()):
    print(f"  {uid:<28} {meta.get('title', '')}")
print(f"\n{len(data)} use case(s). Run: scripts/testing/run.sh <id>")
PY
  exit 0
fi

ID="$1"
shift

python3 - "$UC_FILE" "$ID" "$ROOT" "$@" <<'PY'
import json, os, subprocess, sys
uc_file, uid, root, extra = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
data = json.load(open(uc_file))
if uid not in data:
    print(f"Unknown use case: {uid}", file=sys.stderr)
    print("Run: scripts/testing/run.sh list", file=sys.stderr)
    sys.exit(2)
meta = data[uid]
cmd = meta["cmd"]
env = os.environ.copy()
for k, v in (meta.get("env") or {}).items():
    env.setdefault(k, str(v))
print(f"=== {uid}: {meta.get('title', '')} ===")
print(f"$ {cmd}")
rc = subprocess.call(cmd, shell=True, cwd=root, env=env)
sys.exit(rc)
PY
