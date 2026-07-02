#!/usr/bin/env bash
# Install post-checkout hook in each service repo → kg-session-sync on branch change.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HOOK_BODY="#!/usr/bin/env bash
# sliProd KG — sync knowledge graph on branch checkout (install-kg-git-hooks.sh)
set -euo pipefail
ROOT=\"$ROOT\"
[[ \"\${3:-0}\" == \"1\" ]] && exit 0
[[ -x \"\$ROOT/scripts/bin/kg-session-sync.sh\" ]] || exit 0
timeout 180 bash \"\$ROOT/scripts/bin/kg-session-sync.sh\" --quiet >/dev/null 2>&1 || true
python3 \"\$ROOT/scripts/bin/git_workspace.py\" status --write >/dev/null 2>&1 || true
exit 0
"
for d in "$ROOT"/novopay-* "$ROOT"/trustt-*; do
  [[ -d "$d/.git" ]] || continue
  hook="$d/.git/hooks/post-checkout"
  if [[ -f "$hook" ]] && ! grep -q "sliProd KG" "$hook" 2>/dev/null; then
    echo "⏭ $d — post-checkout exists (not overwriting)"
    continue
  fi
  printf '%s' "$HOOK_BODY" >"$hook"
  chmod +x "$hook"
  echo "✓ $d"
done
echo "Done. Branch switches → kg-session-sync (LRU cache per branch-set)."
