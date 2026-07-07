-- Local DCF JLG fixture: minimal mfi_actor.customer rows for GL CBS narration (getCustomerDetails).
-- LANs 6003973025 / 6003973329 / 6003973330 reference customer_id on loan_account.
\set ON_ERROR_STOP on

WITH need AS (
  SELECT DISTINCT la.customer_id AS cid, la.customer_id - 1 AS aid
  FROM mfi_accounting.loan_account la
  WHERE la.la_account_number IN ('6003973025', '6003973329', '6003973330')
    AND la.is_deleted = false
    AND la.customer_id IS NOT NULL
),
ref AS (
  SELECT corporate_id, base_office_id, created_by
  FROM mfi_actor.customer
  WHERE corporate_id IS NOT NULL AND is_deleted = false
  LIMIT 1
),
ins_actor AS (
  INSERT INTO mfi_actor.actor (id, type, is_deleted)
  SELECT n.aid, 'CUSTOMER', false FROM need n
  WHERE NOT EXISTS (SELECT 1 FROM mfi_actor.actor a WHERE a.id = n.aid)
  RETURNING id
)
INSERT INTO mfi_actor.customer (
  id, actor_id, corporate_id, base_office_id, first_name, last_name, kyc_stage, status, status_changed_on,
  created_on, created_by, updated_on, updated_by, is_deleted
)
SELECT n.cid, n.aid, r.corporate_id, r.base_office_id, 'LOCAL', 'DCF_E2E', 'KYC', 'ACTIVE', NOW(),
       NOW(), r.created_by, NOW(), r.created_by, false
FROM need n
CROSS JOIN ref r
WHERE NOT EXISTS (SELECT 1 FROM mfi_actor.customer c WHERE c.id = n.cid);

UPDATE mfi_actor.customer c
SET corporate_id = r.corporate_id,
    base_office_id = COALESCE(c.base_office_id, r.base_office_id),
    created_by = r.created_by,
    updated_by = r.created_by,
    updated_on = NOW()
FROM (
  SELECT corporate_id, base_office_id, created_by
  FROM mfi_actor.customer
  WHERE corporate_id IS NOT NULL AND is_deleted = false
  LIMIT 1
) r
WHERE c.id IN (
  SELECT la.customer_id FROM mfi_accounting.loan_account la
  WHERE la.la_account_number IN ('6003973025', '6003973329', '6003973330')
);
