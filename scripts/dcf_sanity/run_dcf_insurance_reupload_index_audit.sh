#!/usr/bin/env bash
# DFC insurance RE_UPLOAD — index coverage + EXPLAIN audit (read-only QA/local DB).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

DB="${DCF_INDEX_AUDIT_DB:-qa4}"
echo "=== DCF insurance RE_UPLOAD index / performance audit ==="
echo "DB profile: $DB (override: DCF_INDEX_AUDIT_DB=local|qa3|qa4)"
echo ""

bash "$ROOT/scripts/bin/query-index-perf-audit.sh" --group dcf_insurance_reupload --db "$DB"

echo ""
echo "=== Code-path overhead (fix vs upstream) ==="
cat <<'TXT'
Per RE_UPLOAD row (after fix):
  + claim UPDATE (REQUIRES_NEW) — 1 round trip
  + updateTaskWorkflow HTTP — unchanged
  + completeAccountingState (REQUIRES_NEW) — 2 reads + 2 writes
  - loanDeathForeclosure callback — removed (~3m lock wait eliminated)

Reader filter: status NOT IN (PROCESSING, COMPLETED) — fewer rows picked.

Composite indexes (Flyway V000198 / scripts/sql/setup/dfc_insurance_staging_indexes.sql):
  idx_dfisd_dfc_inout_claim_status | idx_dfisd_inout_claim_id | idx_dfisd_claim_number_status

L0 prod hot-apply before Flyway train: scripts/sql/setup/dfc_insurance_staging_indexes.sql
TXT

echo ""
echo "=== PASS: dcf insurance reupload index audit (WARN allowed until indexes applied) ==="
