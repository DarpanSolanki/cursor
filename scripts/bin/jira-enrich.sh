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
REST="$ROOT/scripts/bin/jira-rest-oauth.py"

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
  set-token)
    # Cursor-independent credential. Reads stdin so the secret never lands in shell history.
    #   API token (recommended, long-lived): prompts for email + token -> Basic auth
    #   OAuth bearer (expires ~1h):          pass --bearer
    tf="$HOME/.cursor/jira-oauth-token"
    mkdir -p "$(dirname "$tf")"
    if [[ "${1:-}" == "--bearer" ]]; then
      echo "Paste Atlassian OAuth bearer token (hidden), then Enter:" >&2
      read -rs tok; echo >&2
      printf '%s' "$tok" > "$tf"
    else
      echo "Atlassian API token setup (create at:" >&2
      echo "  https://id.atlassian.com/manage-profile/security/api-tokens )" >&2
      read -rp "Atlassian account email: " email
      echo "Paste API token (hidden), then Enter:" >&2
      read -rs tok; echo >&2
      printf '%s\n%s\n' "$email" "$tok" > "$tf"
    fi
    chmod 600 "$tf"
    echo "jira-enrich: credential stored at $tf (mode 600)"
    echo "verify: bash scripts/bin/jira-enrich.sh whoami"
    ;;
  whoami)
    ensure_venv
    "$PY" "$REST" whoami
    ;;
  token-status)
    tf="$HOME/.cursor/jira-oauth-token"
    if [[ -n "${JIRA_API_TOKEN:-}${JIRA_OAUTH_TOKEN:-}${ATLASSIAN_OAUTH_TOKEN:-}" ]]; then
      echo "jira-enrich: token source = environment variable"
    elif [[ -s "$tf" ]]; then
      if [[ "$(wc -l < "$tf")" -ge 2 ]]; then
        echo "jira-enrich: token source = $tf (API token, Basic auth — long-lived)"
      else
        echo "jira-enrich: token source = $tf (OAuth bearer — expires ~1h)"
      fi
    elif [[ -f "$HOME/.config/Cursor/User/globalStorage/state.vscdb" ]]; then
      echo "jira-enrich: token source = Cursor Atlassian MCP (legacy fallback)"
      echo "  WARNING: this workspace is Claude-only; run 'jira-enrich.sh set-token' to cut the Cursor dependency."
    else
      echo "jira-enrich: NO token configured — run: jira-enrich.sh set-token"; exit 1
    fi
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
Usage: jira-enrich.sh <ensure|set-token|token-status|whoami|pack|apply|post> ...

  ensure                         Install .venv-jira (secretstorage) if missing
  set-token [TOKEN]              Store a bearer token at ~/.cursor/jira-oauth-token (no Cursor needed)
  token-status                   Show which token source will be used
  whoami                         Verify the token against Jira (/myself)
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
