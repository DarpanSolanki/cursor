#!/usr/bin/env bash
# Generate production deploy SQL: DDL + flyway_schema_history INSERT (manual prod path).
#
# Usage:
#   flyway-prod-deploy-pack.sh novopay-platform-initial-setup/flyway/sli/accounting/sql/product/V000198__dfisd_staging_composite_indexes.sql
#   flyway-prod-deploy-pack.sh <flyway.sql> --out scripts/sql/deploy/prod_V000198_dfisd_indexes.sql
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec python3 "$ROOT/scripts/lib/flyway_prod_deploy_pack.py" "$@"
