#!/usr/bin/env bash
# Multi-repo branch sync — upstream (trusttai) + origin (fork), KG-aware.
#
# Usage:
#   sync-branches.sh --domain dfc --train mfi_integration_v3.7.1
#   sync-branches.sh --train mfi_integration_v3.4.2.5 --yes
#   sync-branches.sh mfi_integration_v3.4.2.5   # prints plan; requires --yes for full sync
#
# Flags: --domain <name>  --train <branch>  --yes  --user <fork>  --root <path>
# Env: SYNC_NO_PUSH=1  SYNC_FETCH_ONLY=1  SYNC_DRY_RUN=1
#
# After sync: .cursor/git-workspace-state.json + kg-session-sync (cache-first)
set -euo pipefail
IFS=$'\n\t'

DOMAIN=""
TRAIN=""
YES=0
USERNAME="${SYNC_USER:-DarpanSolanki}"
BASE_PATH="$(cd "$(dirname "$0")/../.." && pwd)"
POSITIONAL=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain) DOMAIN="${2:-}"; shift 2 ;;
    --train) TRAIN="${2:-}"; shift 2 ;;
    --yes|-y) YES=1; shift ;;
    --user) USERNAME="${2:-}"; shift 2 ;;
    --root) BASE_PATH="${2:-}"; shift 2 ;;
    --help|-h) sed -n '2,14p' "$0"; exit 0 ;;
    --*) echo "Unknown flag: $1" >&2; exit 2 ;;
    *) POSITIONAL+=("$1"); shift ;;
  esac
done

[[ -z "$TRAIN" && ${#POSITIONAL[@]} -ge 1 ]] && TRAIN="${POSITIONAL[0]}"
[[ ${#POSITIONAL[@]} -ge 2 ]] && USERNAME="${POSITIONAL[1]}"
[[ ${#POSITIONAL[@]} -ge 3 ]] && BASE_PATH="${POSITIONAL[2]}"

if [[ -z "$TRAIN" && -f "$BASE_PATH/.cursor/git-branch-manifest.json" ]]; then
  TRAIN="$(python3 -c "import json;print(json.load(open('$BASE_PATH/.cursor/git-branch-manifest.json')).get('default_branch',''))" 2>/dev/null || true)"
fi
TRAIN="${TRAIN:-mfi_integration_v3.2.8.4}"
[[ "$TRAIN" =~ ^[0-9]+\.[0-9] ]] && TRAIN="mfi_integration_v${TRAIN}"
BRANCH="$TRAIN"

# shellcheck source=../lib/github_repo_map.sh
source "$BASE_PATH/scripts/lib/github_repo_map.sh"
UPSTREAM_ORG="${UPSTREAM_ORG:-trusttai}"
NO_PUSH="${SYNC_NO_PUSH:-0}"
FETCH_ONLY="${SYNC_FETCH_ONLY:-0}"
DRY_RUN="${SYNC_DRY_RUN:-0}"

REPO_FILTER=""
if [[ -n "$DOMAIN" ]]; then
  REPO_FILTER="$(
    cd "$BASE_PATH" && PYTHONPATH="$BASE_PATH/scripts/lib" python3 -c "
from train_banner import domain_repos
r = domain_repos('${DOMAIN}')
if not r:
    raise SystemExit('Unknown --domain ${DOMAIN}')
print(chr(10).join(r))
"
  )" || exit 2
fi

if [[ ! -d "$BASE_PATH" ]]; then
  echo "❌ Base path does not exist: $BASE_PATH"
  exit 1
fi

cd "$BASE_PATH"
MANIFEST="$BASE_PATH/.cursor/git-branch-manifest.json"
mkdir -p "$BASE_PATH/.cursor"

SCOPE="full-workspace"
[[ -n "$DOMAIN" ]] && SCOPE="domain:$DOMAIN ($(echo "$REPO_FILTER" | tr '\n' ' '))"

echo "=== sync-branches PLAN ==="
echo "  train:   $BRANCH"
echo "  user:    $USERNAME"
echo "  root:    $BASE_PATH"
echo "  scope:   $SCOPE"
echo "  flags:   NO_PUSH=$NO_PUSH FETCH_ONLY=$FETCH_ONLY DRY_RUN=$DRY_RUN YES=$YES"

if [[ -z "$DOMAIN" && "$YES" != 1 && "$FETCH_ONLY" != 1 ]]; then
  echo ""
  echo "REFUSING full-workspace sync without --yes (foot-gun guard)."
  echo "  Scoped:  bash scripts/bin/sync-branches.sh --domain dfc --train $BRANCH"
  echo "  Full:    bash scripts/bin/sync-branches.sh --train $BRANCH --yes"
  exit 3
fi

python3 - "$BRANCH" "$MANIFEST" <<'PY' 2>/dev/null || true
import json, sys
from pathlib import Path
branch, path = sys.argv[1], Path(sys.argv[2])
m = {}
if path.is_file():
    try: m = json.loads(path.read_text())
    except Exception: pass
m["default_branch"] = branch
m.setdefault("overrides", {})
m.setdefault("notes", "origin=fork push · upstream=trusttai read-only. overrides=stay on feature branch during sync.")
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
    local _ifs="$IFS"
    IFS=' '
    echo "  [dry-run] $*"
    IFS="$_ifs"
  else
    "$@"
  fi
}

echo "=== sync-branches: integration=$BRANCH user=$USERNAME ==="
echo "    remotes: origin=https://github.com/${USERNAME}/<mapped-trustt-repo> · upstream=${UPSTREAM_ORG}"
echo "    name map: scripts/lib/github_repo_map.sh"
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
    trustt-platform-simulators)
      echo "⏭ Skipping $repo"
      SKIPPED=$((SKIPPED + 1))
      continue
      ;;
  esac
  if [[ -n "${REPO_FILTER:-}" ]] && ! grep -qxF "$repo" <<<"$REPO_FILTER"; then
    continue
  fi

  TARGET="$(target_branch "$repo")"
  echo ""
  echo "================================="
  echo "▶ $repo → $TARGET"
  echo "================================="
  cd "$dir"

  GH_REPO="$(github_upstream_repo "$repo")"
  EXPECTED_ORIGIN="$(github_fork_url "$repo" "$USERNAME")"
  EXPECTED_UPSTREAM="$(github_upstream_url "$repo")"
  if [[ "$GH_REPO" != "$repo" ]]; then
    echo "  map: local $repo → GitHub $GH_REPO"
  fi

  if git remote | grep -qx origin; then
    run git remote set-url origin "$EXPECTED_ORIGIN"
  else
    run git remote add origin "$EXPECTED_ORIGIN"
  fi
  if git remote | grep -qx upstream; then
    run git remote set-url upstream "$EXPECTED_UPSTREAM"
  else
    echo "➕ Adding upstream → $EXPECTED_UPSTREAM"
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

  if git rev-parse --verify "origin/$TARGET" >/dev/null 2>&1; then
    run git pull --rebase origin "$TARGET" || {
      echo "⚠ pull origin failed — resolve manually"
      FAIL=$((FAIL + 1))
      cd "$BASE_PATH"
      continue
    }
  fi

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
      # Lease-safe push to fork only (never upstream)
      run git push --force-with-lease origin "$TARGET"
    fi
  else
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
