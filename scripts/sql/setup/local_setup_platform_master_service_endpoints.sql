-- Local Yugabyte: align platform_master service endpoints with actual bootRun ports.
-- Accounting internal API client reads service_master.endpoint (cached in Redis).
--
-- Usage:
--   PGPASSWORD=yugabyte psql -h localhost -p 5433 -U yugabyte -d yugabyte \
--     -v ON_ERROR_STOP=1 -f scripts/sql/setup/local_setup_platform_master_service_endpoints.sql

\set ON_ERROR_STOP on

UPDATE platform_master.service_master
SET endpoint = 'http://localhost:8594/payments',
    updated_on = NOW(),
    updated_by = 'LOCAL_SETUP'
WHERE UPPER(name) = 'PAYMENTS'
  AND endpoint <> 'http://localhost:8594/payments';

SELECT name, endpoint FROM platform_master.service_master
WHERE UPPER(name) IN ('PAYMENTS', 'ACCOUNTING', 'ACTOR', 'NOTIFICATIONS')
ORDER BY name;
