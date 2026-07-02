\set ON_ERROR_STOP on

UPDATE mfi_masterdata.code_master_details cmd
SET value = :'go_live_value',
    updated_on = NOW(),
    updated_by = 'DPI_UD_E2E'
FROM mfi_masterdata.code_master cm
WHERE cmd.code_master_id = cm.id
  AND cm.data_type = 'DPI_GO_LIVE_DATE'
  AND cm.data_sub_type = :'go_live_sub_type'
  AND cm.is_deleted = false
  AND cmd.is_deleted = false;

\echo 'DPI_GO_LIVE_DATE' :'go_live_sub_type' '=>' :'go_live_value'
