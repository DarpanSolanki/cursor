#!/usr/bin/env bash
# Multi-repo branch sync — upstream (khoslalabs) + origin (fork), KG-aware.
#
# Remotes:  origin = your fork (push) · upstream = canonical (read/rebase, no push)
#
# Usage:
#   sync-branches.sh <integration_branch> [github_user] [workspace_root]
#   sync-branches.sh mfi_integration_v3.3.1.0 DarpanSolanki /home/darpan/Documents/sliProd
#
# Options (env):
#   SYNC_NO_PUSH=1     — checkout/fetch/rebase locally only
#   SYNC_FETCH_ONLY=1  — fetch remotes + refresh state, no checkout
#   SYNC_DRY_RUN=1     — print actions only
#
# Per-repo feature branches: .cursor/git-branch-manifest.json overrides
#   python3 scripts/bin/git_workspace.py set-override novopay-platform-accounting-v2 feature/foo
#
# After sync: .cursor/git-workspace-state.json + kg-session-sync (cache-first)
set -euo pipefail
IFS=$'\n\t'

BRANCH="${1:-mfi_integration_v3.2.8.4}"
USERNAME="${2:-DarpanSolanki}"
BASE_PATH="${3:-$(cd "$(dirname "$0")/../.." && pwd)}"
UPSTREAM_ORG="khoslalabs"
NO_PUSH="${SYNC_NO_PUSH:-0}"
FETCH_ONLY="${SYNC_FETCH_ONLY:-0}"
DRY_RUN="${SYNC_DRY_RUN:-0}"

if [[ ! -d "$BASE_PATH" ]]; then
  echo "❌ Base path does not exist: $BASE_PATH"
  exit 1
fi

cd "$BASE_PATH"
MANIFEST="$BASE_PATH/.cursor/git-branch-manifest.json"
mkdir -p "$BASE_PATH/.cursor"

# Persist default integration branch in manifest
python3 - "$BRANCH" "$MANIFEST" <<'PY' 2>/dev/null || true
import json, sys
from pathlib import Path
branch, path = sys.argv[1], Path(sys.argv[2])
m = {}
if path.is_file():
    try: m = json.loads(path.read_text())
    except Exception: pass
m.setdefault("default_branch", branch)
m.setdefault("overrides", {})
m.setdefault("notes", "origin=fork push · upstream=khoslalabs read-only. overrides=stay on feature branch during sync.")
path.write_text(json.dumps(m, indent=2) + "\n")
PY

target_branch() {
  python3 - "$1" "$BRANCH" "$MANIFEST" <<'PY'
import json, sys
from pathlib import Path
repo, default, mf = sys.argv[1], sys.argv[2], Path(sys.argv[3])
m = json.loads(mf.read_text()) if mf.is_file() else {}
print(m.get("overrides", {}).get(repo, default))
PY
}

is_integration_branch() {
  [[ "$1" =~ ^mfi_(integration|release)_v[0-9] ]]
}

run() {
  if [[ "$DRY_RUN" == 1 ]]; then
    echo "  [dry-run] $*"
  else
    "$@"
  fi
}

echo "=== sync-branches: integration=$BRANCH user=$USERNAME ==="
echo "    remotes: origin=https://github.com/${USERNAME}/<repo> · upstream=${UPSTREAM_ORG}"
[[ -f "$MANIFEST" ]] && echo "    manifest: $MANIFEST ($(python3 -c "import json; print(len(json.load(open('$MANIFEST')).get('overrides',{})))" 2>/dev/null || echo 0) overrides)"

if [[ "$FETCH_ONLY" == 1 ]]; then
  exec bash "$BASE_PATH/scripts/bin/git-fetch-all.sh"
fi

FAIL=0
SKIPPED=0
OK=0

for dir in "$BASE_PATH"/novopay-* "$BASE_PATH"/trustt-*; do
  [[ -d "$dir/.git" ]] || continue
  repo=$(basename "$dir")
  case "$repo" in
    novopay-platform-simulators)
      echo "⏭ Skipping $repo"
      SKIPPED=$((SKIPPED + 1))
      continue
      ;;
  esac

  TARGET="$(target_branch "$repo")"
  echo ""
  echo "================================="
  echo "▶ $repo → $TARGET"
  echo "================================="
  cd "$dir"

  EXPECTED_ORIGIN="https://github.com/${USERNAME}/${repo}.git"
  EXPECTED_UPSTREAM="https://github.com/${UPSTREAM_ORG}/${repo}.git"

  if git remote | grep -qx origin; then
    run git remote set-url origin "$EXPECTED_ORIGIN"
  else
    run git remote add origin "$EXPECTED_ORIGIN"
  fi
  if ! git remote | grep -qx upstream; then
    echo "➕ Adding upstream"
    run git remote add upstream "$EXPECTED_UPSTREAM"
  fi

  run git fetch origin --prune
  run git fetch upstream --prune

  if ! git show-ref --verify --quiet "refs/heads/$TARGET" 2>/dev/null; then
    if git ls-remote --heads origin "$TARGET" | grep -q "$TARGET"; then
      echo "✔ Branch on origin"
      run git checkout -B "$TARGET" "origin/$TARGET"
    elif git ls-remote --heads upstream "$TARGET" | grep -q "$TARGET"; then
      echo "✔ Branch on upstream"
      run git checkout -B "$TARGET" "upstream/$TARGET"
      if [[ "$NO_PUSH" != 1 ]] && is_integration_branch "$TARGET"; then
        run git push -u origin "$TARGET"
      fi
    else
      echo "⚠ Branch $TARGET not found — skip"
      SKIPPED=$((SKIPPED + 1))
      cd "$BASE_PATH"
      continue
    fi
  else
    run git checkout "$TARGET"
  fi

  # Pull fork
  if git rev-parse --verify "origin/$TARGET" >/dev/null 2>&1; then
    run git pull --rebase origin "$TARGET" || {
      echo "⚠ pull origin failed — resolve manually"
      FAIL=$((FAIL + 1))
      cd "$BASE_PATH"
      continue
    }
  fi

  # Integration line: rebase onto upstream + push fork
  if is_integration_branch "$TARGET"; then
    if git ls-remote --heads upstream "$TARGET" | grep -q "$TARGET"; then
      if ! run git rebase "upstream/$TARGET"; then
        echo "⚠ rebase upstream failed — manual fix"
        FAIL=$((FAIL + 1))
        cd "$BASE_PATH"
        continue
      fi
    fi
    if [[ "$NO_PUSH" != 1 ]]; then
      run git push --force-with-lease origin "$TARGET"
    fi
  else
    # Feature / override branch: stay on fork line, no upstream rebase
    echo "  (feature override — skip upstream rebase)"
    if [[ "$NO_PUSH" != 1 ]] && git rev-parse --verify "origin/$TARGET" >/dev/null 2>&1; then
      run git push origin "$TARGET" || true
    fi
  fi

  echo "✅ $repo @ $(git rev-parse --short=10 HEAD 2>/dev/null || echo '?')"
  OK=$((OK + 1))
  cd "$BASE_PATH"
done

echo ""
echo "🎉 Sync done: ok=$OK skipped=$SKIPPED failed=$FAIL"

python3 "$BASE_PATH/scripts/bin/git_workspace.py" status --write >/dev/null 2>&1 || true
echo "→ .cursor/git-workspace-state.json"

if [[ -x "$BASE_PATH/scripts/bin/kg-session-sync.sh" ]]; then
  echo ""
  echo "⟳ KG session sync (cache-first for this branch-set)…"
  bash "$BASE_PATH/scripts/bin/kg-session-sync.sh" --quiet || {
    echo "⚠ kg-session-sync failed — run: scripts/bin/kg-session-sync.sh"
  }
elif [[ -x "$BASE_PATH/scripts/bin/kg-switch.sh" ]]; then
  bash "$BASE_PATH/scripts/bin/kg-switch.sh" --quiet || true
fi

if [[ "${SYNC_NO_INTEL:-0}" != "1" && -x "$BASE_PATH/scripts/bin/super-agent.sh" ]]; then
  echo ""
  echo "⟳ Intelligence full sync (branch-set changed)…"
  timeout 600 bash "$BASE_PATH/scripts/bin/super-agent.sh" sync --full 2>&1 | tail -8 || {
    echo "⚠ super-agent sync --full failed — run: scripts/bin/super-agent.sh sync --full"
  }
fi

[[ "$FAIL" -eq 0 ]] || exit 1
