#!/usr/bin/env bash
# Fail closed when the RUNNING JVM predates the compiled classes or the source.
#
# Why this exists
# ---------------
# `aops_java_newer_than_boot` compares `src/**/*.java` mtime against the service's
# boot LOG. The running service appends to that log continuously, so its mtime is
# always ~now and no source file is ever "newer" — the check can never fire. On
# 2026-08-03 that let a JVM started 15:52 serve money-path tests against classes
# compiled 16:02, on a checkout whose HEAD moved at 16:01. A whole session of
# interest-accrual evidence was produced against bytecode that did not contain the
# fix under test (`ad399c5f2`).
#
# The only sound comparison is the JVM's own start time vs what is on disk.
#
# Usage:
#   bash scripts/bin/assert-build-current.sh accounting        # exit 1 if stale
#   BUILD_CURRENT_WARN_ONLY=1 bash scripts/bin/assert-build-current.sh accounting
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SVC="${1:-accounting}"

case "$SVC" in
  accounting) REPO="$ROOT/trustt-platform-accounting"; PORT=8002 ;;
  los)        REPO="$ROOT/trustt-platform-los";        PORT=8013 ;;
  actor)      REPO="$ROOT/trustt-platform-actor";      PORT=8003 ;;
  task)       REPO="$ROOT/trustt-platform-task";       PORT=8019 ;;
  *) echo "assert-build-current: unknown service '$SVC'" >&2; exit 2 ;;
esac

pid="$(ss -ltnp 2>/dev/null | grep ":${PORT} " | grep -oP 'pid=\K[0-9]+' | head -1)"
if [[ -z "$pid" ]]; then
  echo "assert-build-current: $SVC not listening on :$PORT — nothing to check"
  exit 0
fi

# /proc/<pid> mtime is the process start time.
jvm_epoch="$(stat -c %Y "/proc/$pid" 2>/dev/null || echo 0)"
[[ "$jvm_epoch" == 0 ]] && { echo "assert-build-current: cannot read /proc/$pid"; exit 0; }

newest() { find "$1" -name "$2" -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1; }

cls_line="$(newest "$REPO/build/classes/java/main" '*.class')"
src_line="$(newest "$REPO/src/main/java" '*.java')"
cls_epoch="${cls_line%% *}"; cls_epoch="${cls_epoch%.*}"; cls_epoch="${cls_epoch:-0}"
src_epoch="${src_line%% *}"; src_epoch="${src_epoch%.*}"; src_epoch="${src_epoch:-0}"

fmt() { [[ "$1" == 0 ]] && echo "-" || date -d "@$1" '+%m-%d %H:%M:%S'; }

stale=0
reasons=()
if (( cls_epoch > jvm_epoch )); then
  stale=1
  reasons+=("JVM started $(fmt "$jvm_epoch") but classes compiled $(fmt "$cls_epoch") — running bytecode is NOT what is on disk")
fi
if (( src_epoch > cls_epoch )); then
  stale=1
  reasons+=("source $(fmt "$src_epoch") is newer than compiled classes $(fmt "$cls_epoch") — build is stale")
fi

head_sha="$(git -C "$REPO" rev-parse --short=10 HEAD 2>/dev/null || echo '?')"
head_epoch="$(git -C "$REPO" log -1 --format=%ct 2>/dev/null || echo 0)"
if (( head_epoch > jvm_epoch )); then
  stale=1
  reasons+=("HEAD $head_sha committed $(fmt "$head_epoch") after the JVM started $(fmt "$jvm_epoch")")
fi

if (( stale == 0 )); then
  echo "assert-build-current: $SVC OK — pid=$pid started $(fmt "$jvm_epoch"), classes $(fmt "$cls_epoch"), HEAD $head_sha"
  exit 0
fi

{
  echo "======================================================================"
  echo "STALE RUNTIME: $SVC (pid=$pid)"
  for r in "${reasons[@]}"; do echo "  - $r"; done
  echo "  Any money-path evidence from this JVM is NOT verified against HEAD."
  echo "  Fix: bash scripts/bin/novopay-service.sh restart $SVC"
  echo "======================================================================"
} >&2

[[ "${BUILD_CURRENT_WARN_ONLY:-0}" == "1" ]] && exit 0
exit 1
