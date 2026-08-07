#!/usr/bin/env bash
# Bring this workspace up on a fresh Claude-enabled machine.
#
#   new-machine-setup.sh --dry-run    # show every step, change nothing (do this first)
#   new-machine-setup.sh              # run it
#   new-machine-setup.sh --no-clone   # knowledge layer only, skip the ~10GB of repos
#
# Ordered so the knowledge layer works BEFORE the repos land: the committed KG
# snapshot restores with zero repos cloned, which matters because accounting is
# 418MB and los is 571MB. Everything is idempotent — existing repos are never
# touched, and re-running is safe.
#
# What it cannot do, and reports instead: the local Yugabyte fixture and the
# running services. Those are machine state, not repo content.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

DRY=0
CLONE=1
FORK="${WORKSPACE_FORK_USER:-DarpanSolanki}"
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    --no-clone) CLONE=0 ;;
    -h|--help) sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown arg: $a" >&2; exit 2 ;;
  esac
done

run() { if [[ $DRY == 1 ]]; then echo "    would run: $*"; else "$@"; fi }
step() { echo ""; echo "== $* =="; }

step "1/6 prerequisites"
missing=0
for tool in git python3; do
  if command -v "$tool" >/dev/null 2>&1; then
    printf "  %-10s %s\n" "$tool" "$($tool --version 2>&1 | head -1)"
  else
    printf "  %-10s MISSING (required)\n" "$tool"; missing=1
  fi
done
for tool in java psql; do
  if command -v "$tool" >/dev/null 2>&1; then
    printf "  %-10s %s\n" "$tool" "$($tool --version 2>&1 | head -1)"
  else
    printf "  %-10s missing (needed only for builds / local DB)\n" "$tool"
  fi
done
[[ $missing == 0 ]] || { echo "install the required tools first" >&2; exit 1; }

step "2/6 knowledge layer (works with zero repos cloned)"
if [[ -f cursor-bundle/kg/snapshot/kg.jsonl ]]; then
  run bash scripts/bin/kg-snapshot.sh restore
else
  echo "  no committed snapshot — KG will need cursor-bundle/kg/bin/build.sh after cloning"
fi

step "3/6 service repos"
if [[ $CLONE == 0 ]]; then
  echo "  skipped (--no-clone)"
else
  default_branch="$(python3 -c "import json;print(json.load(open('.cursor/git-workspace-state.json'))['manifest']['default_branch'])")"
  # The manifest is the declared train, which is NOT necessarily what any given
  # machine has checked out today. Clone to the declared one, then scope
  # deliberately with sync-branches.sh rather than inheriting someone's drift.
  echo "  manifest default train: $default_branch (overrides applied per repo)"
  mapfile -t repos < <(python3 -c "
import json
d = json.load(open('.cursor/git-workspace-state.json'))
for name in d['repos']:
    if name.startswith('novopay-'):
        continue
    print(name)
")
  for repo in "${repos[@]}"; do
    if [[ -d "$repo/.git" ]]; then
      printf "  %-44s present\n" "$repo"
      continue
    fi
    branch="$(python3 -c "
import json
d = json.load(open('.cursor/git-workspace-state.json'))
print(d['manifest'].get('overrides', {}).get('$repo', '$default_branch'))
")"
    printf "  %-44s cloning (%s)\n" "$repo" "$branch"
    run git clone --branch "$branch" "https://github.com/$FORK/$repo.git" "$repo"
  done
  # novopay-platform-lib is a symlink alias, not a checkout — several older paths
  # and the KG activation anchors still resolve through it.
  if [[ ! -e novopay-platform-lib ]]; then
    echo "  restoring novopay-platform-lib -> trustt-platform-lib symlink"
    run ln -s trustt-platform-lib novopay-platform-lib
  fi
fi

step "4/6 derived indexes"
if [[ -d trustt-platform-accounting/src ]]; then
  run bash scripts/bin/schema-sync.sh --bindings
else
  echo "  skipped — needs the service repos"
fi

step "5/6 hooks and gates"
run bash scripts/bin/install-user-cursor-gates.sh
run bash scripts/bin/install-kg-git-hooks.sh

step "6/6 what is still manual"
cat <<'TXT'
  - Local Yugabyte fixture (localhost:5433). Without it `scripts/db-local.sh` and a
    schema-oracle REBUILD do not work. The committed cursor-bundle/schema/tables.jsonl
    still serves lookups read-only, so `kg schema` works before the DB exists.
  - Local services (accounting :8002, actor :8003, los :8013, task :8019,
    simulators :8018, Kafka :9092) — needed only to RUN flows, not to query knowledge.
  - Atlassian MCP needs an interactive auth once: `claude mcp` or /mcp.
TXT

echo ""
echo "verify with:"
echo "  bash scripts/bin/workspace-doctor.sh"
echo "  bash scripts/bin/kg-snapshot.sh status     # snapshot vs this checkout"
echo "  python3 cursor-bundle/kg/bin/kg.py fresh   # rebuild if STALE"
echo ""
echo "to work on a specific train:"
echo "  bash scripts/bin/sync-branches.sh --train <mfi_integration_vX.Y.Z> --yes"
[[ $DRY == 1 ]] && echo "" && echo "(dry run — nothing changed)"
exit 0
