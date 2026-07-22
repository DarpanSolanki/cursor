#!/usr/bin/env bash
# Verify DPI feature repos are on feature/delayed_payment_interest
set -euo pipefail
ROOT="${SLIPROD_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
BRANCH="feature/delayed_payment_interest"
REPOS=(trustt-platform-accounting trustt-platform-initial-setup trustt-platform-webapp)
FAIL=0

for repo in "${REPOS[@]}"; do
  dir="$ROOT/$repo"
  if [[ ! -d "$dir/.git" ]]; then
    echo "SKIP $repo (no git)"
    continue
  fi
  cur=$(git -C "$dir" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "?")
  sha=$(git -C "$dir" rev-parse --short=10 HEAD 2>/dev/null || echo "?")
  if [[ "$cur" == "$BRANCH" ]]; then
    echo "PASS $repo @ $BRANCH ($sha)"
  else
    echo "FAIL $repo on $cur ($sha) — need $BRANCH"
    FAIL=1
  fi
done

if [[ $FAIL -ne 0 ]]; then
  echo "Fix: cd <repo> && git fetch origin && git checkout $BRANCH && git pull"
  echo "Then: scripts/bin/kg-switch.sh"
  exit 1
fi
exit 0
