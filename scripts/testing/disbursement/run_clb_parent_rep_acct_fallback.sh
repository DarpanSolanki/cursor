#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ACCT="$ROOT/trustt-platform-accounting"
SRC="$ROOT/scripts/testing/disbursement/java/in/novopay/accounting/loan/grouploan/disbursement/service/ClbParentRepAcctFallbackRunner.java"
OUT="${TMPDIR:-/tmp}/clb_parent_rep_acct_fallback"

cd "$ACCT"
./gradlew -q compileJava
CP="$(./gradlew -q --init-script tmp-printcp.init.gradle printTestRuntimeClasspath 2>/dev/null | tail -1)"

rm -rf "$OUT"
mkdir -p "$OUT"
javac -nowarn -d "$OUT" -cp "$CP" "$SRC"
java -cp "$OUT:$CP" in.novopay.accounting.loan.grouploan.disbursement.service.ClbParentRepAcctFallbackRunner
