\set ON_ERROR_STOP on

UPDATE code_master_details cmd
SET value = :'go_live_value',
    updated_on = NOW(),
    updated_by = 'DPI_UD_E2E'
FROM code_master cm
WHERE cmd.code_master_id = cm.id
  AND cm.data_type = 'DPI_GO_LIVE_DATE'
  AND cm.data_sub_type = 'JLGDL'
  AND cm.is_deleted = false
  AND cmd.is_deleted = false;

\echo 'DPI_GO_LIVE_DATE JLGDL =>' :'go_live_value'
