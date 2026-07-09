-- Local webapp login: mark employee contact flags verified so single DEFAULT login
-- returns session in one call (skips 220402 OTP gate).
--
-- Edit the handle value below, then run:
--   scripts/db-local.sh --file scripts/sql/setup/local_setup_webapp_login_contact_verified.sql

UPDATE mfi_actor.employee e
SET is_mobile_number_verified = true,
    is_alternate_contact_number_verified = true,
    is_primary_email_verified = true,
    updated_on = NOW(),
    updated_by = 'local_webapp_login_setup'
WHERE e.is_deleted = false
  AND e.id IN (
    SELECT emp.id
    FROM mfi_actor.employee emp
    JOIN mfi_actor.user_handle uh ON uh.user_id = emp.user_id AND uh.is_deleted = false
    WHERE UPPER(uh.handle_value) = UPPER('REPLACE_WITH_YOUR_ADID')
  );
