#!/usr/bin/env bash
# beforeShellExecution — git push checklist + block upstream/trusttai/khoslalabs + ship-loop gate.
set -euo pipefail
input=$(cat)
command=$(python3 -c "import json,sys; print(json.load(sys.stdin).get('command',''))" <<<"$input")

if [[ ! "$command" =~ (^|&&|;|\|\|)[[:space:]]*git[[:space:]]+push([[:space:]]|$) ]]; then
  echo '{"permission":"allow"}'
  exit 0
fi

ROOT="${CURSOR_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
PENDING="$ROOT/.cursor/.pending-ship-work.json"
PASSED="$ROOT/.cursor/.ship-loop-passed.json"
GATE="$ROOT/scripts/lib/ship_push_gate.py"

# Impact plan banner for dirty/unpushed tree (human or agent — git is SoT)
echo "pre-push: impact plan (git dirty/unpushed)…" >&2
python3 "$ROOT/scripts/lib/impact_tests.py" --banner --no-stubs >&2 || true

# Auto-close pending ship work before denying push (agent can push to origin after build+test).
if [[ -f "$PENDING" && "${SHIP_PUSH_NO_AUTO_CLOSE:-}" != "1" ]]; then
  if python3 "$GATE" --needs-close 2>/dev/null; then
    echo "pre-push: auto workspace-close (pending ship work)…" >&2
  CLOSE_ARGS=(--from-pending)
  while IFS= read -r api; do
    [[ -n "$api" ]] && CLOSE_ARGS+=(--api "$api")
  done < <(python3 "$GATE" --pending-apis 2>/dev/null || true)
  if python3 "$GATE" --is-merge-head 2>/dev/null; then
    export SHIP_CLOSE_ALLOW_MERGE=1
  fi
  if bash "$ROOT/scripts/bin/workspace-close.sh" "${CLOSE_ARGS[@]}" >&2; then
    echo "pre-push: workspace-close PASS" >&2
  else
    cat <<'EOF'
{
  "permission": "deny",
  "user_message": "Push blocked: workspace-close failed (build/ntest/knowledge gate).",
  "agent_message": "Fix ship-loop failure, then retry push or run: bash scripts/bin/workspace-close.sh --from-pending"
}
EOF
    exit 0
  fi
  fi
fi

if [[ -f "$PENDING" ]]; then
  if ! python3 "$GATE" --satisfied 2>/dev/null; then
    cat <<'EOF'
{
  "permission": "deny",
  "user_message": "Push blocked: ship loop not completed (build + ntest + knowledge gate).",
  "agent_message": "Run `bash scripts/bin/workspace-close.sh --from-pending` or `bash scripts/bin/push-origin.sh`. Push denied until `.cursor/.ship-loop-passed.json` is newer than pending work."
}
EOF
    exit 0
  fi
fi

if [[ -x "$ROOT/scripts/bin/enrichment-audit.sh" ]]; then
  if ! "$ROOT/scripts/bin/enrichment-audit.sh" --pre-push >&2; then
    cat <<'EOF'
{
  "permission": "deny",
  "user_message": "Push blocked: git commit without brain changelog entry.",
  "agent_message": "Prepend cursor-bundle/brain/changelog/CHANGELOG.md via changelog-add.sh, or merge-only commits are auto-exempt when SHIP_CLOSE_ALLOW_MERGE applies. Run workspace-close or push-origin.sh."
}
EOF
    exit 0
  fi
fi

if [[ "$command" =~ upstream|khoslalabs|trusttai ]]; then
  cat <<'EOF'
{
  "permission": "deny",
  "user_message": "Push to upstream/trusttai (or legacy khoslalabs) is blocked in this workspace (darpan boundary).",
  "agent_message": "Do not push to upstream. Use origin only; bash scripts/bin/push-origin.sh"
}
EOF
  exit 0
fi

cat <<'EOF'
{
  "permission": "allow",
  "agent_message": "Pre-push checklist: ship-loop PASS (auto-close if needed), origin not upstream. Prefer: bash scripts/bin/push-origin.sh"
}
EOF
