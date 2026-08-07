#!/usr/bin/env bash
# Refresh the schema oracle: structure (local DB) → code binding (Java) → train labels (Flyway).
#
#   schema-sync.sh              # all three
#   schema-sync.sh --bindings   # code binding only (no DB needed)
#
# Run after a Flyway migration, a branch switch that changes entities, or a local
# schema patch. The gate `scripts/lib/schema_ref_gate.py` reads what this writes.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [[ "${1:-}" != "--bindings" ]]; then
  python3 scripts/lib/schema_oracle.py --rebuild
fi
python3 scripts/lib/column_binding.py --rebuild "${@:2}"
python3 scripts/lib/schema_train_diff.py | head -4
python3 scripts/lib/schema_live_drift.py | head -6 || true
python3 scripts/lib/schema_ref_gate.py --sql
