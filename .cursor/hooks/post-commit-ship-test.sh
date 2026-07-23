#!/usr/bin/env bash
# afterShellExecution — auto ship tests after commit when pending money/service work exists.
# Also: write .last-ship-commit + re-register pending from HEAD ship paths.
set -euo pipefail
ROOT="${CURSOR_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
INPUT=$(cat)

META=$(echo "$INPUT" | python3 -c "
import json,sys
from pathlib import Path
d=json.load(sys.stdin)
cmd=d.get('command','') or ''
out=(d.get('output') or '')[:800]
cwd=d.get('cwd') or d.get('working_directory') or d.get('workdir') or ''
print(json.dumps({'command':cmd,'output':out,'cwd':cwd}))
" 2>/dev/null || echo '{}')

CMD=$(echo "$META" | python3 -c "import json,sys; print(json.load(sys.stdin).get('command',''))" 2>/dev/null || true)
[[ "$CMD" =~ git[[:space:]]+commit ]] || { echo '{}'; exit 0; }

OUT=$(echo "$META" | python3 -c "import json,sys; print(json.load(sys.stdin).get('output',''))" 2>/dev/null || true)
if echo "$OUT" | grep -qiE 'nothing to commit|no changes added|failed|fatal:'; then
  echo '{}'
  exit 0
fi

# Resolve repo from cwd / -C / pending repos; write last-ship-commit; re-register paths
python3 - <<'PY' "$ROOT" "$META"
import json, subprocess, sys
from pathlib import Path

root = Path(sys.argv[1])
meta = json.loads(sys.argv[2] or "{}")
cwd = (meta.get("cwd") or "").strip()
cmd = meta.get("command") or ""

sys.path.insert(0, str(root / "scripts/lib"))
from register_pending_ship import register_paths, paths_from_commit  # noqa: E402

def repo_from_path(p: Path) -> Path | None:
    cur = p.resolve() if p.exists() else p
    for parent in [cur, *cur.parents]:
        if (parent / ".git").is_dir() and parent.name.startswith(("novopay-", "trustt-")):
            return parent
        if parent == root:
            break
    if (root / ".git").is_dir() and root.name:
        # workspace itself
        return root if (root / ".git").is_dir() else None
    return None

repo_dir = None
if cwd:
    repo_dir = repo_from_path(Path(cwd))
if not repo_dir and " -C " in f" {cmd} ":
    # crude: git -C path commit
    parts = cmd.split()
    for i, p in enumerate(parts):
        if p == "-C" and i + 1 < len(parts):
            repo_dir = repo_from_path(Path(parts[i + 1]))
            break
if not repo_dir:
    # Prefer first service repo listed in pending files
    pending_p = root / ".cursor/.pending-ship-work.json"
    if pending_p.is_file():
        try:
            pending = json.loads(pending_p.read_text(encoding="utf-8"))
            for rel in pending.get("files") or []:
                top = Path(rel).parts[0] if Path(rel).parts else ""
                if top.startswith(("novopay-", "trustt-")) and (root / top / ".git").is_dir():
                    repo_dir = root / top
                    break
        except Exception:
            pass
if not repo_dir and (root / ".git").is_dir():
    repo_dir = root

if not repo_dir:
    raise SystemExit(0)

sha = subprocess.run(
    ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
    capture_output=True, text=True, check=False,
).stdout.strip()
last = root / ".cursor/.last-ship-commit"
last.parent.mkdir(parents=True, exist_ok=True)
rel_name = repo_dir.name if repo_dir != root else "."
if repo_dir == root:
    rel_name = "."  # workspace root commits
else:
    try:
        rel_name = str(repo_dir.relative_to(root))
    except ValueError:
        rel_name = repo_dir.name
last.write_text(f"{rel_name}\n{sha}\n", encoding="utf-8")

paths = paths_from_commit(repo_dir, "HEAD")
if paths:
    register_paths(root, paths, source="post-commit")
print(f"post-commit: last-ship-commit={rel_name}@{sha[:10]} paths={len(paths)}")
PY

PENDING="$ROOT/.cursor/.pending-ship-work.json"
[[ -f "$PENDING" ]] || { echo '{}'; exit 0; }

TIER=$(python3 -c "import json; print(json.load(open('$PENDING')).get('tier','workspace'))" 2>/dev/null || echo workspace)
[[ "$TIER" == "workspace" ]] && {
  python3 - <<'PY'
import json
print(json.dumps({"additional_context": "Post-commit: last-ship-commit updated; pending tier=workspace (no ship-test-auto)."}))
PY
  exit 0
}

LOG="$ROOT/scripts/scratch/logs/post-commit-ship-test.log"
mkdir -p "$(dirname "$LOG")"
(
  echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) post-commit ship-test-auto tier=$TIER ==="
  bash "$ROOT/scripts/bin/ship-test-auto.sh"
) >>"$LOG" 2>&1 &

python3 - <<'PY'
import json
print(json.dumps({"additional_context": "Post-commit: last-ship-commit + pending re-registered; ship-test-auto queued. Log: scripts/scratch/logs/post-commit-ship-test.log"}))
PY
