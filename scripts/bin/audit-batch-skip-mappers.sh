#!/usr/bin/env bash
# Enforce batch write-skip contract (platform-lib + job mappers stay aligned).
#
# Contract (non-negotiable):
#   1. GenericListenerV3.onSkipInWrite → BatchWriterSkipItemSupport.resolveSkipItem → fromWriter(O)
#   2. Vo-typed fromWriter (calc, billing, penal, …): direct field access + null guards only
#   3. List-typed fromWriter (booking, interest posting): null-safe first element — never Future unwrap
#   4. No job-local wrappers that re-call resolveSkipItem (e.g. DpiBatchWriterSkipItemSupport)
#
# Usage:
#   audit-batch-skip-mappers.sh           # all accounting BatchFailureEntityMapper
#   audit-batch-skip-mappers.sh --dpi-only
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ACCT="$ROOT/novopay-platform-accounting-v2/src/main/java"
LIB="$ROOT/novopay-platform-lib/infra-batch/src/main/java"
DPI_ONLY=0
FAIL=0

for a in "$@"; do
  case "$a" in
    --dpi-only) DPI_ONLY=1 ;;
    -h|--help)
      sed -n '1,12p' "$0"
      exit 0
      ;;
  esac
done

_err() { echo "AUDIT FAIL: $*" >&2; FAIL=1; }

# --- platform spine ---
if ! rg -q 'BatchWriterSkipItemSupport\.resolveSkipItem' "$LIB/in/novopay/infra/batch/listener/GenericListenerV3.java"; then
  _err "GenericListenerV3 must call BatchWriterSkipItemSupport.resolveSkipItem before fromWriter"
fi

if rg -q 'implements SkipListener<I,O>' "$LIB/in/novopay/infra/batch/listener/GenericListenerV3.java" 2>/dev/null; then
  _err "GenericListenerV3 must implement SkipListener<I,Object> (async writer passes Future, not O)"
fi

# --- DPI: no duplicate skip wrapper ---
if [[ -f "$ACCT/in/novopay/accounting/batchnew/dpi/DpiBatchWriterSkipItemSupport.java" ]]; then
  _err "Delete DpiBatchWriterSkipItemSupport — Future resolve is platform-owned in GenericListenerV3"
fi

_audit_mapper_file() {
  local f="$1"
  local label="$2"
  [[ -f "$f" ]] || return 0

  if rg -q 'DpiBatchWriterSkipItemSupport|resolveSkipItem|FutureTask|Future<' "$f" 2>/dev/null; then
    _err "$label: must not unwrap Future/skip item — platform resolves before fromWriter ($f)"
  fi
  if rg -q 'unwrap\(' "$f" 2>/dev/null; then
    _err "$label: remove unwrap() helper calls — use direct Vo or null-safe list.get(0) ($f)"
  fi
}

# Vo-typed DPI mappers (writer output is a single VO after platform resolve)
_audit_mapper_file \
  "$ACCT/in/novopay/accounting/batchnew/dpi/dpiaccrualcalculation/DpiAccrualCalculationFailureEntityMapper.java" \
  "dpiAccrualCalculation"
_audit_mapper_file \
  "$ACCT/in/novopay/accounting/batchnew/dpi/dpibilling/DpiBillingFailureEntityMapper.java" \
  "dpiBilling"

# List-typed DPI booking: null guard before isEmpty/get(0)
BOOKING="$ACCT/in/novopay/accounting/batchnew/dpi/dpiaccrualbooking/DpiAccrualBookingFailureEntityMapper.java"
if [[ -f "$BOOKING" ]]; then
  if rg -q 'fromWriter\(List<' "$BOOKING" && rg -q 'item\.isEmpty\(\)|item\.get\(0\)' "$BOOKING" \
     && ! rg -q 'item == null' "$BOOKING"; then
    _err "dpiAccrualBooking: list fromWriter must null-check item before isEmpty/get(0)"
  fi
fi

# DPI jobs must use GenericListenerV3 (grep batch config)
for job in dpiaccrualcalculation dpiaccrualbooking dpibilling; do
  cfg=$(rg -l "class Dpi.*BatchConfigService" "$ACCT/in/novopay/accounting/batchnew/dpi/$job" --glob '*.java' 2>/dev/null | head -1)
  if [[ -n "$cfg" ]] && ! rg -q 'GenericListenerV3' "$cfg"; then
    _err "DPI job $job must register GenericListenerV3 for fault-tolerant skip audit"
  fi
done

if [[ "$DPI_ONLY" -eq 1 ]]; then
  if [[ "$FAIL" -eq 1 ]]; then
    echo "audit-batch-skip-mappers (--dpi-only): FAILED" >&2
    exit 1
  fi
  echo "audit-batch-skip-mappers (--dpi-only): PASS"
  exit 0
fi

# --- all accounting failure mappers: no Future re-unwrap ---
while IFS= read -r f; do
  if rg -q 'Future|FutureTask|resolveSkipItem|DpiBatchWriterSkipItemSupport' "$f" 2>/dev/null; then
    _err "$f: failure mapper must not unwrap Future — GenericListenerV3 resolves skip items"
  fi
done < <(rg -l 'implements BatchFailureEntityMapper' "$ACCT" --glob '*.java')

# List mappers: null-safe first element
while IFS= read -r f; do
  if rg -q 'fromWriter\(List<' "$f" && rg -q 'item\.isEmpty\(\)|item\.get\(0\)' "$f" \
     && ! rg -q 'item == null' "$f"; then
    _err "$f: list fromWriter must null-check item before isEmpty/get(0)"
  fi
done < <(rg -l 'implements BatchFailureEntityMapper' "$ACCT" --glob '*.java')

if [[ "$FAIL" -eq 1 ]]; then
  echo "audit-batch-skip-mappers: FAILED" >&2
  exit 1
fi
echo "audit-batch-skip-mappers: PASS"
