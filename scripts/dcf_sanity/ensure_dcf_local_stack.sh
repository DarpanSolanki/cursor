#!/usr/bin/env bash
# SDCP-10199 — local deps for deathForeclosureInsuranceJob e2e (real postings).
# Kafka :9092; masterdata :8014; payments stub :8594; BRE stub :8025;
# actor + accounting (MessageBroker.xml). BRE stub = harness-only (other team).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"

echo "=== ensure DCF local stack ==="

if ! ss -tln 2>/dev/null | grep -q ':9092 '; then
  echo "FAIL: Kafka not listening on :9092" >&2
  exit 1
fi
echo "  kafka: :9092 listening"

PGPASSWORD="${PGPASSWORD:-yugabyte}" psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" \
  -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}" -v ON_ERROR_STOP=1 \
  -f "$ROOT/scripts/sql/setup/local_setup_platform_master_service_endpoints.sql" >/dev/null 2>&1 || true

dpi_ensure_masterdata
dpi_ensure_actor
bash "$ROOT/scripts/dcf_sanity/local_payments_stub.sh" ensure
bash "$ROOT/scripts/dcf_sanity/local_notifications_stub.sh" ensure
# Harness-only: treat getForeclosureRoles as SUCCESS so Sim B loanPrepayment CREATE works.
bash "$ROOT/scripts/dcf_sanity/local_bre_stub.sh" ensure

PGPASSWORD="${PGPASSWORD:-yugabyte}" psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" \
  -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}" -v ON_ERROR_STOP=1 \
  -f "$ROOT/scripts/sql/setup/local_setup_dcf_fixture_actor_customers.sql" >/dev/null
echo "  sql: DCF fixture actor customers applied"

PGPASSWORD="${PGPASSWORD:-yugabyte}" psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" \
  -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}" -v ON_ERROR_STOP=1 \
  -f "$ROOT/scripts/sql/setup/local_setup_dcf_insurance_ptc_placeholders.sql" >/dev/null
echo "  sql: DCF DPI placeholder IAD applied"

# Harness-only: LOAN_PREPAYMENT DPI placeholders (existing) + RSCH_LOAN_PREPAYMENT DPI for parent PPP
PGPASSWORD="${PGPASSWORD:-yugabyte}" psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" \
  -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}" -v ON_ERROR_STOP=1 \
  -f "$ROOT/scripts/sql/setup/local_setup_loan_prepayment_dpi_ptc_placeholders.sql" >/dev/null
echo "  sql: LOAN_PREPAYMENT DPI PTC placeholders applied"
PGPASSWORD="${PGPASSWORD:-yugabyte}" psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" \
  -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}" -v ON_ERROR_STOP=1 \
  -f "$ROOT/scripts/sql/setup/local_setup_rsch_loan_prepayment_dpi_ptc_placeholders.sql" >/dev/null
echo "  sql: RSCH_LOAN_PREPAYMENT DPI PTC placeholders applied"

if [[ "${DCF_STACK_SKIP_ACCOUNTING_RESTART:-}" != "1" ]]; then
  bash "$ROOT/scripts/bin/novopay-service.sh" restart accounting --compile
else
  bash "$ROOT/scripts/bin/novopay-service.sh" ensure accounting
fi

bash "$ROOT/scripts/bin/novopay-service.sh" ensure task

echo "=== DCF local stack ready ==="
