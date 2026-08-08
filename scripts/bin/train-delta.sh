#!/usr/bin/env bash
# What code is actually new between two trains — the "is this new to production?" question.
#
# An IAC EOD job tripled after a deploy. The reader SQL was byte-identical between the
# assumed baseline and the shipped train, so the reader looked innocent — but production
# had been two trains back, where the 503-line SHG accrual distribute did not exist at
# all. Diffing against the assumed baseline instead of the deployed one is why that cost
# an afternoon. Name both trains explicitly; never infer the baseline.
set -euo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"

usage() {
    cat >&2 <<'EOF'
usage: train-delta.sh <repo> <fromTrain> <toTrain> [pathspec...]

  repo        directory name under the workspace root (e.g. trustt-platform-accounting)
  fromTrain   train currently in production (branch name, with or without remote prefix)
  toTrain     train being deployed

  pathspec    optional git pathspecs to scope the delta

examples:
  train-delta.sh trustt-platform-accounting mfi_integration_v3.4.2.3 mfi_release_v3.4.2.5
  train-delta.sh trustt-platform-accounting mfi_release_v3.4.2.4 mfi_release_v3.4.2.5 \
      'src/main/java/**/interest/**'
EOF
    exit 2
}

[[ $# -ge 3 ]] || usage
REPO="$1"; FROM="$2"; TO="$3"; shift 3

REPO_DIR="$ROOT/$REPO"
[[ -d "$REPO_DIR/.git" ]] || { echo "train-delta: not a git repo: $REPO_DIR" >&2; exit 1; }

resolve() {
    local ref="$1"
    for candidate in "$ref" "upstream/$ref" "origin/$ref"; do
        if git -C "$REPO_DIR" rev-parse --verify --quiet "$candidate^{commit}" >/dev/null; then
            echo "$candidate"
            return 0
        fi
    done
    echo "train-delta: cannot resolve '$ref' in $REPO (fetch first?)" >&2
    return 1
}

FROM_REF="$(resolve "$FROM")"
TO_REF="$(resolve "$TO")"

echo "== train delta: $REPO =="
echo "   from (in prod): $FROM_REF @ $(git -C "$REPO_DIR" rev-parse --short=10 "$FROM_REF")"
echo "   to  (deploying): $TO_REF @ $(git -C "$REPO_DIR" rev-parse --short=10 "$TO_REF")"
echo

echo "-- files changed --"
git -C "$REPO_DIR" diff --stat "$FROM_REF" "$TO_REF" -- "$@"
echo

echo "-- files that are entirely NEW on $TO_REF (absent in prod) --"
git -C "$REPO_DIR" diff --diff-filter=A --name-only "$FROM_REF" "$TO_REF" -- "$@" | sed 's/^/   NEW  /'
echo

echo "-- commits --"
git -C "$REPO_DIR" log --oneline --no-merges "$FROM_REF..$TO_REF" -- "$@"
