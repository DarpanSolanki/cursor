#!/usr/bin/env bash
# Read-only release-train fix discovery and forward-port analysis.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TOOL="$ROOT/scripts/lib/branch_train.py"

usage() {
  cat <<'EOF'
Usage:
  fwd-port.sh <repo> <sha> [floor]                 branches containing/missing SHA
  fwd-port.sh --train <repo>                       live upstream merge DAG
  fwd-port.sh --path <repo> <from-branch>          forward paths from branch
  fwd-port.sh --diverge <repo> <sha> <target>      target file divergence
  fwd-port.sh --audit <repo>                       KG fixes absent upstream
  fwd-port.sh --fixed-elsewhere <query> [options]  higher-branch fix lookup

fixed-elsewhere options:
  --repo <repo>   Owning repo (optional when KG resolves query)
  --base <branch> Lower/reported branch (default: repo current branch)
  --limit <n>     Candidate commits shown per branch (with --show-candidates)
  --fetch-if-stale  Fetch upstream only when refs are older than 12h/unknown
  --show-candidates Print FILE_TOUCH_HINTS subjects (still REUSE_FORBIDDEN)

Reuse is allowed ONLY when output contains VERIFIED_FIXED_CLEAN and REUSE_ALLOWED.
This tool never checks out, merges, cherry-picks, or pushes.
EOF
}

[[ $# -gt 0 ]] || { usage; exit 2; }

case "$1" in
  --train)
    [[ $# -eq 2 ]] || { usage; exit 2; }
    exec python3 "$TOOL" train "$2"
    ;;
  --path)
    [[ $# -eq 3 ]] || { usage; exit 2; }
    exec python3 "$TOOL" path "$2" "$3"
    ;;
  --diverge)
    [[ $# -eq 4 ]] || { usage; exit 2; }
    exec python3 "$TOOL" diverge "$2" "$3" "$4"
    ;;
  --audit)
    [[ $# -eq 2 ]] || { usage; exit 2; }
    exec python3 "$TOOL" audit "$2"
    ;;
  --fixed-elsewhere)
    shift
    [[ $# -gt 0 ]] || { usage; exit 2; }
    exec python3 "$TOOL" fixed-elsewhere "$@"
    ;;
  -h|--help)
    usage
    ;;
  -*)
    usage
    exit 2
    ;;
  *)
    [[ $# -ge 2 && $# -le 3 ]] || { usage; exit 2; }
    exec python3 "$TOOL" missing "$@"
    ;;
esac
