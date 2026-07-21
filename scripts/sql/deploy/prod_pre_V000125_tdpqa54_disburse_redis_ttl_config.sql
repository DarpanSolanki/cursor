-- Production deploy pack: mfi_masterdata 000125 (tdpqa54 disburse redis inflight ttl config)
-- Source: trustt-platform-initial-setup/flyway/sli/masterdata/sql/product/V000125__tdpqa54_disburse_redis_inflight_ttl_config.sql
-- Timing: PRE-DEPLOYMENT (run DML + schema_version INSERT before/with app deploy)

-- === PRE DEPLOYMENT: DML (execute on mfi_masterdata) ===
-- Note: Flyway migration uses unqualified table name (schemas=mfi_masterdata).
-- Manual pack qualifies for DBA sessions without Flyway search_path.

INSERT INTO mfi_masterdata.configuration (prop_key, prop_name, prop_value, description, service, is_editable, is_deleted, created_on, created_by, updated_on, updated_by, approved_on, approved_by, data_type)
VALUES
    ('mfi.disburse.loan.producer.marker.ttl.ms',
     'Disburse Loan Producer Marker TTL (ms)',
     '600000',
     'Redis TTL in milliseconds for LOS disburseLoan in-flight producer marker keys',
     'LOS', true, false, NOW(), 'V000125', NOW(), 'V000125', NOW(), 'V000125', 'NUMBER'),
    ('mfi.disburse.loan.consumer.lock.ttl.ms',
     'Disburse Loan Consumer Lock TTL (ms)',
     '600000',
     'Redis TTL in milliseconds for Accounting disburseLoan in-flight consumer lock keys',
     'ACCOUNTING', true, false, NOW(), 'V000125', NOW(), 'V000125', NOW(), 'V000125', 'NUMBER');

-- === PRE DEPLOYMENT: register in Flyway history ===

INSERT INTO mfi_masterdata.schema_version
(installed_rank, version, description, type, script, checksum, installed_by, installed_on, execution_time, success)
VALUES
((SELECT COALESCE(MAX(installed_rank), 0) + 1 FROM mfi_masterdata.schema_version),
 '000125', 'tdpqa54 disburse redis inflight ttl config', 'SQL', 'product/V000125__tdpqa54_disburse_redis_inflight_ttl_config.sql', NULL, 'yugabyte', NOW(), 0, true);

-- Verify: SELECT version, script, success FROM mfi_masterdata.schema_version WHERE version = '000125';
