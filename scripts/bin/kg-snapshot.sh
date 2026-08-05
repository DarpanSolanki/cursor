#!/usr/bin/env bash
# Ship a built KG with the repo so a new machine has knowledge before cloning 21 repos.
#
#   kg-snapshot.sh save      # current build -> cursor-bundle/kg/snapshot/ (tracked)
#   kg-snapshot.sh restore   # snapshot -> data/kg.{jsonl,db} + manifest
#   kg-snapshot.sh status    # does the snapshot match this checkout?
#
# jsonl, not sqlite: 19MB of text diffs and compresses; a 50MB binary rewritten
# on every build does neither. `build_db.py` materialises it in seconds.
#
# The snapshot is branch-keyed. `status` compares its composite key against the
# live checkout so a stale snapshot is visible rather than silently believed —
# after `restore`, run `kg fresh` and rebuild if it reports STALE.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

SNAP="$ROOT/cursor-bundle/kg/snapshot"
DATA="$ROOT/cursor-bundle/kg/data"
BIN="$ROOT/cursor-bundle/kg/bin"

live_key() { python3 "$BIN/kg_composite.py" 2>/dev/null | tr -d '[:space:]'; }
snap_key() { python3 -c "import json,sys;print(json.load(open('$SNAP/manifest.json'))['key'])" 2>/dev/null; }

case "${1:-status}" in
  save)
    [[ -f "$DATA/kg.jsonl" ]] || { echo "no build to save — run cursor-bundle/kg/bin/build.sh" >&2; exit 1; }
    mkdir -p "$SNAP"
    cp "$DATA/kg.jsonl" "$SNAP/kg.jsonl"
    key="$(python3 - <<'PY'
import json, pathlib, subprocess, sys
root = pathlib.Path(".").resolve()
cache = root / "cursor-bundle/kg/data/cache"
best = None
for m in cache.glob("*.manifest.json"):
    d = json.loads(m.read_text())
    if best is None or d.get("built_at", "") > best.get("built_at", ""):
        best = d
if best is None:
    print("", end="")
    sys.exit(0)
out = root / "cursor-bundle/kg/snapshot/manifest.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(best, indent=2) + "\n")
print(best["key"])
PY
)"
    echo "saved snapshot key=${key:-unknown} ($(du -h "$SNAP/kg.jsonl" | cut -f1))"
    echo "commit cursor-bundle/kg/snapshot/ so a new machine can restore it"
    ;;
  restore)
    [[ -f "$SNAP/kg.jsonl" ]] || { echo "no snapshot committed — run kg-snapshot.sh save" >&2; exit 1; }
    mkdir -p "$DATA"
    cp "$SNAP/kg.jsonl" "$DATA/kg.jsonl"
    [[ -f "$SNAP/manifest.json" ]] && cp "$SNAP/manifest.json" "$DATA/kg.manifest.json"
    python3 "$BIN/build_db.py" "$DATA/kg.jsonl" "$DATA/kg.db"
    python3 "$BIN/kg_validate.py" >/dev/null 2>&1 || echo "warn: validate reported an issue"
    echo "restored KG from snapshot (key=$(snap_key))"
    echo "run: python3 cursor-bundle/kg/bin/kg.py fresh   # rebuild if STALE for your checkout"
    ;;
  status)
    if [[ ! -f "$SNAP/manifest.json" ]]; then echo "kg-snapshot: none committed"; exit 0; fi
    # The composite key folds in a brain-doc fingerprint, so a pure knowledge
    # commit flips it. Reporting that as STALE fires on every docs change and
    # trains people to ignore the signal. Repo drift is what makes a KG wrong.
    python3 - "$SNAP/manifest.json" <<'PY'
import json, subprocess, sys, pathlib
snap = json.loads(pathlib.Path(sys.argv[1]).read_text())
sys.path.insert(0, str(pathlib.Path("cursor-bundle/kg/bin").resolve()))
import kg_composite as kc

moved = []
for repo, was in (snap.get("repos") or {}).items():
    try:
        now = kc.repo_state(repo)
    except Exception:
        continue
    if now.get("branch") != was.get("branch") or not now.get("sha", "").startswith(was.get("sha", "")[:10]):
        moved.append((repo, was.get("branch"), now.get("branch")))

print(f"snapshot built : {snap.get('built_at')}  key={snap.get('key')}")
docs_changed = kc.docs_fingerprint() != snap.get("docs_fp")
if not moved:
    extra = " (brain docs changed — doc nodes only, code map unaffected)" if docs_changed else ""
    print(f"kg-snapshot: MATCHES this checkout{extra}")
    sys.exit(0)
print(f"kg-snapshot: STALE — {len(moved)} repo(s) moved since the snapshot:")
for repo, was, now in moved[:10]:
    print(f"  {repo:44s} {was} -> {now}")
print("rebuild: bash cursor-bundle/kg/bin/build.sh && bash scripts/bin/kg-snapshot.sh save")
PY
    ;;
  *) sed -n '2,8p' "$0"; exit 2 ;;
esac
