UPDATE mfi_notifications.notification_message
SET message = 'This group can only be rejected by a ${required_role} or above, as it is sourced under the ${scheme} scheme and includes at least one member from the ${community} category.',
    updated_on = NOW(),
    updated_by = 'ROLLBACK_3_4_2_2_055'
WHERE code = 'LOS-GEN-0562' AND locale = 'en-in';

UPDATE mfi_notifications.notification_message
SET message = 'The group can only be approved by ${required_role} or higher roles, as it falls under the ${scheme} scheme/sales promocode and includes ${community} member(s) with Non-Availing status.',
    updated_on = NOW(),
    updated_by = 'ROLLBACK_3_4_2_2_055'
WHERE code = 'LOS-GEN-0563' AND locale = 'en-in';

DELETE FROM mfi_notifications.code__notification_code__mapping
WHERE service_name = 'LOS' AND code IN ('LOS-0609', 'LOS-5213');

DELETE FROM mfi_notifications.notification_message
WHERE code IN ('LOS-GEN-0609', 'LOS-GEN-5213') AND locale = 'en-in';

DELETE FROM mfi_notifications.flyway_schema_history
WHERE version IN ('9000414', '9000415', '9000417', '9000418', '9000420');

DELETE FROM mfi_masterdata.code_master_details d
USING mfi_masterdata.code_master cm
WHERE d.code_master_id = cm.id
  AND (
    (cm.created_by = 'V9000842' AND cm.data_type IN ('SHGDL', 'JLGDL', 'INDL_LOAN') AND cm.data_sub_type IN ('SC', 'ST'))
    OR (cm.created_by = 'V9000849' AND cm.data_type = 'NON_CANCELLABLE_GROUP_STATUSES' AND cm.data_sub_type = 'DEFAULT')
  );

DELETE FROM mfi_masterdata.code_master
WHERE (created_by = 'V9000842' AND data_type IN ('SHGDL', 'JLGDL', 'INDL_LOAN') AND data_sub_type IN ('SC', 'ST'))
   OR (created_by = 'V9000849' AND data_type = 'NON_CANCELLABLE_GROUP_STATUSES' AND data_sub_type = 'DEFAULT');

DELETE FROM mfi_masterdata.configuration
WHERE prop_key IN (
  'mfi.create.request.dedupe.ttl.ms',
  'mfi.create.request.dedupe.enabled',
  'payment.reinitiation.disbursed.status'
);

DELETE FROM mfi_masterdata.schema_version
WHERE version IN ('9000840', '9000842', '9000844', '9000849');

DELETE FROM platform_master.api_master
WHERE name = 'generateRecordAttemptReportSftpDailyJob';

DELETE FROM platform_master.flyway_schema_history
WHERE version = '000448';

ALTER TABLE mfi_los.individual_mitigant_details
  ALTER COLUMN forwarded_notes TYPE varchar(255)
  USING left(forwarded_notes, 255);

DROP TABLE IF EXISTS mfi_los.audit_fallback_event CASCADE;

DELETE FROM mfi_los.flyway_schema_history
WHERE version IN ('000379', '000380');

DROP TABLE IF EXISTS mfi_audit.audit_fallback_event CASCADE;

DELETE FROM mfi_audit.flyway_schema_history
WHERE version = '000008';
