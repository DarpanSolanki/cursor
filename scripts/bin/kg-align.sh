#!/usr/bin/env bash
# Fail-closed: sync KG then assert watermark matches a train (branch-wise impact hygiene).
#
# Usage:
#   scripts/bin/kg-align.sh --repo trustt-platform-accounting --branch mfi_integration_v3.4.2.4
#   scripts/bin/kg-align.sh --domain accounting --train mfi_integration_v3.4.2.4
#
# Does NOT checkout branches — run sync-branches.sh first if live checkout is wrong.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

REPO=""; BRANCH=""; DOMAIN=""; TRAIN=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="${2:-}"; shift 2 ;;
    --branch) BRANCH="${2:-}"; shift 2 ;;
    --domain) DOMAIN="${2:-}"; shift 2 ;;
    --train) TRAIN="${2:-}"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 2 ;;
  esac
done

bash "$ROOT/scripts/bin/kg-switch.sh"
if [[ -n "$REPO" && -n "$BRANCH" ]]; then
  exec python3 "$ROOT/cursor-bundle/kg/bin/kg.py" align --repo "$REPO" --branch "$BRANCH"
fi
if [[ -n "$DOMAIN" && -n "$TRAIN" ]]; then
  exec python3 "$ROOT/cursor-bundle/kg/bin/kg.py" align --domain "$DOMAIN" --train "$TRAIN"
fi
echo "Usage: kg-align.sh --repo <repo> --branch <train>"
echo "   or: kg-align.sh --domain <name> --train <train>"
exit 2
