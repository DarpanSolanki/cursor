#!/usr/bin/env bash
# Capture a durable fact into cursor-bundle/memory + MEMORY.md in one command.
#
# Facts stated in conversation — a branch policy, a deployment constraint, a correction —
# have no capture path of their own: the learning bus only carries test/flow findings and
# the changelog only carries shipped code. Without this they survive only if an agent
# volunteers a hand-written file, which is why they usually did not.
#
#   scripts/bin/learn.sh reference forward-merge-chain "Trains merge 3.4.2.3 -> 3.7.1" "Detail line."
#   scripts/bin/learn.sh feedback no-alter-in-prod "Production runs no ALTER" "Why: ... How to apply: ..."
#
# types: user | feedback | project | reference
set -euo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
MEM="$ROOT/cursor-bundle/memory"
INDEX="$MEM/MEMORY.md"

if [[ $# -lt 3 ]]; then
  sed -n '2,14p' "$0" | sed 's/^# \?//'
  exit 2
fi

type="$1"; slug="$2"; summary="$3"; shift 3
body="${*:-}"

case "$type" in
  user|feedback|project|reference) ;;
  *) echo "learn: type must be user|feedback|project|reference (got '$type')" >&2; exit 2 ;;
esac

if [[ ! "$slug" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
  echo "learn: slug must be kebab-case (got '$slug')" >&2
  exit 2
fi

file="$MEM/${type}_${slug//-/_}.md"

if [[ -e "$file" ]]; then
  echo "learn: $file already exists — edit it instead of creating a duplicate." >&2
  echo "       (memory rule: update the existing file rather than adding a sibling)" >&2
  exit 3
fi

{
  echo "---"
  echo "name: $slug"
  echo "description: $summary"
  echo "metadata:"
  echo "  type: $type"
  echo "---"
  echo
  echo "$summary"
  [[ -n "$body" ]] && { echo; echo "$body"; }
} > "$file"

rel="${file#"$ROOT"/}"
printf -- '- [%s](%s) — %s\n' "$slug" "$(basename "$file")" "$summary" >> "$INDEX"

echo "learn: wrote $rel and indexed it in MEMORY.md"
echo "       commit it so the next session and the next machine both see it."
