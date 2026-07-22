#!/usr/bin/env bash
# Compute Flyway 5.2.4 migration checksum (matches mfi_accounting.flyway_schema_history).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SQL="$(readlink -f "$1")"
DIR="$(dirname "$SQL")"
FILE="$(basename "$SQL")"
FLYWAY_CP="$ROOT/trustt-platform-initial-setup/flyway/lib/community/*"
SRC="$ROOT/scripts/lib/flyway_checksum/FlywayChecksum.java"
OUT="$ROOT/scripts/lib/flyway_checksum/FlywayChecksum.class"
if [[ ! -f "$OUT" ]] || [[ "$SRC" -nt "$OUT" ]]; then
  javac -cp "$FLYWAY_CP" -d "$ROOT/scripts/lib/flyway_checksum" "$SRC"
fi
cd "$DIR"
java -cp "$FLYWAY_CP:$ROOT/scripts/lib/flyway_checksum" FlywayChecksum "$FILE"
