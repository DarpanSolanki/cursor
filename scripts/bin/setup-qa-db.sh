#!/usr/bin/env bash
# Bootstrap / preflight QA DB env profiles (qa1–qa5).
#
# Usage:
#   setup-qa-db.sh qa1           # one env
#   setup-qa-db.sh --all         # all envs in qa-manifest.json
#   setup-qa-db.sh --list        # show configured envs
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_DIR="$ROOT/scripts/db/env"
MANIFEST="$ENV_DIR/qa-manifest.json"

_list_envs() {
  python3 - <<'PY' "$MANIFEST"
import json, sys
from pathlib import Path
m = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for name, e in sorted(m.get("envs", {}).items()):
    print(f"  {name:4}  {e['host']}:{e['port']}/{e['database']}  user={e['user']}")
PY
}

_has_password() {
  local f="$1"
  grep -qE "^PGPASSWORD=.+" "$f" 2>/dev/null || grep -qE "^PGPASSWORD='.+'" "$f" 2>/dev/null
}

_preflight_one() {
  local ENV_NAME="$1"
  local EXAMPLE="$ENV_DIR/${ENV_NAME}.env.example"
  local TARGET="$ENV_DIR/${ENV_NAME}.env"

  if [[ ! -f "$EXAMPLE" ]]; then
    echo "SKIP $ENV_NAME — no $EXAMPLE" >&2
    return 1
  fi

  if [[ ! -f "$TARGET" ]]; then
    cp "$EXAMPLE" "$TARGET"
    chmod 600 "$TARGET"
    echo "CREATED $TARGET — set PGPASSWORD then re-run setup-qa-db.sh $ENV_NAME"
    return 1
  fi

  if ! _has_password "$TARGET"; then
    echo "SKIP $ENV_NAME — set PGPASSWORD in $TARGET" >&2
    return 1
  fi

  echo "=== QA DB preflight: $ENV_NAME ==="
  if bash "$ROOT/scripts/db/db-qa.sh" --env "$ENV_NAME" --ping >/dev/null 2>&1; then
    echo "OK: $ENV_NAME reachable"
    return 0
  fi
  echo "FAIL: $ENV_NAME not reachable" >&2
  return 1
}

case "${1:-qa1}" in
  --list|-l)
    echo "QA environments (scripts/db/env/qa-manifest.json):"
    _list_envs
    exit 0
    ;;
  --all|-a)
    ok=0 fail=0
    mapfile -t ENVS < <(python3 -c "import json; print('\n'.join(sorted(json.load(open('$MANIFEST'))['envs'])))")
    for e in "${ENVS[@]}"; do
      if _preflight_one "$e"; then ok=$((ok+1)); else fail=$((fail+1)); fi
      echo ""
    done
    echo "=== QA preflight: $ok ok, $fail failed/skipped ==="
    [[ "$fail" -eq 0 ]]
    ;;
  -h|--help)
    sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
    ;;
  *)
    _preflight_one "$1"
    ;;
esac
