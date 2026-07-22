#!/usr/bin/env bash
# Fast JIRA handoff: one pack build + optional REST apply (single OAuth decrypt).
# Prefer parent-agent CallMcpTool when available; this path is shell fallback.
#
# Usage:
#   jira-enrich.sh ensure
#   jira-enrich.sh pack SDCP-11085 payload.json > pack.json
#   jira-enrich.sh post SDCP-11085 payload.json
#   jira-enrich.sh post TDPQA-127 payload.json --comment-id 388469
#   cat payload.json | jira-enrich.sh pack TDPQA-127
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VENV="$ROOT/.venv-jira"
PY="$VENV/bin/python3"
ADF="$ROOT/scripts/bin/jira-fix-adf.py"
REST="$ROOT/scripts/bin/jira-rest-from-cursor-oauth.py"

ensure_venv() {
  if [[ ! -x "$PY" ]]; then
    echo "jira-enrich: creating $VENV …" >&2
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -q secretstorage cryptography
  fi
}

cmd="${1:-}"
shift || true

case "$cmd" in
  ensure)
    ensure_venv
    "$PY" -c "import secretstorage, cryptography; print('jira-enrich: OK')"
    ;;
  pack)
    ensure_venv
    key="${1:?issue key required}"
    shift || true
    if [[ -n "${1:-}" && -f "$1" ]]; then
      "$PY" "$ADF" pack "$key" "$1"
    else
      "$PY" "$ADF" pack "$key"
    fi
    ;;
  apply)
    ensure_venv
    key="${1:?issue key required}"
    pack="${2:?pack.json required}"
    comment_id=""
    if [[ "${3:-}" == "--comment-id" && -n "${4:-}" ]]; then
      comment_id="--comment-id $4"
    fi
    # shellcheck disable=SC2086
    "$PY" "$REST" apply-pack "$key" "$pack" $comment_id
    ;;
  post)
    ensure_venv
    key="${1:?issue key required}"
    payload="${2:?payload.json required}"
    comment_id=""
    if [[ "${3:-}" == "--comment-id" && -n "${4:-}" ]]; then
      comment_id="--comment-id $4"
    fi
    tmp="$(mktemp)"
    trap 'rm -f "$tmp"' EXIT
    "$PY" "$ADF" pack "$key" "$payload" > "$tmp"
    # shellcheck disable=SC2086
    "$PY" "$REST" apply-pack "$key" "$tmp" $comment_id
    ;;
  *)
    cat <<EOF
Usage: jira-enrich.sh <ensure|pack|apply|post> ...

  ensure                         Install .venv-jira (secretstorage) if missing
  pack <KEY> [payload.json]      Build full handoff pack (one scan, all ADF fields)
  apply <KEY> pack.json          PUT fields + comment via REST (cached OAuth)
  post <KEY> payload.json        pack + apply in one shot

MCP fast path (parent agent): jira-fix-adf.py pack once → one editJiraIssue + one addComment.
Do not call getJiraIssueTypeMetaWithFields on every enrich — use fields-reference.md.

Skill: .cursor/skills/jira-fix-update/SKILL.md
EOF
    exit 2
    ;;
esac
