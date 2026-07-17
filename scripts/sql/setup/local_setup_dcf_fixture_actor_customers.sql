-- Local DCF: minimal mfi_actor.customer rows for GL CBS narration (getCustomerDetails).
-- Seeds any ACTIVE loan_account.customer_id missing from actor (auto-discover fixtures).
\set ON_ERROR_STOP on

INSERT INTO mfi_actor.actor (id, type, is_deleted)
SELECT DISTINCT la.customer_id - 1, 'CUSTOMER', false
FROM mfi_accounting.loan_account la
WHERE la.is_deleted = false
  AND la.customer_id IS NOT NULL
  AND la.loan_status = 'ACTIVE'
  AND NOT EXISTS (
    SELECT 1 FROM mfi_actor.customer c WHERE c.id = la.customer_id AND c.is_deleted = false
  )
  AND NOT EXISTS (
    SELECT 1 FROM mfi_actor.actor a WHERE a.id = la.customer_id - 1
  );

INSERT INTO mfi_actor.customer (
  id, actor_id, corporate_id, base_office_id, first_name, last_name, kyc_stage, status, status_changed_on,
  created_on, created_by, updated_on, updated_by, is_deleted
)
SELECT DISTINCT ON (la.customer_id)
  la.customer_id,
  la.customer_id - 1,
  r.corporate_id,
  r.base_office_id,
  'LOCAL',
  'DCF_E2E',
  'KYC',
  'ACTIVE',
  NOW(),
  NOW(),
  r.created_by,
  NOW(),
  r.created_by,
  false
FROM mfi_accounting.loan_account la
CROSS JOIN (
  SELECT corporate_id, base_office_id, created_by
  FROM mfi_actor.customer
  WHERE corporate_id IS NOT NULL AND is_deleted = false
  LIMIT 1
) r
WHERE la.is_deleted = false
  AND la.customer_id IS NOT NULL
  AND la.loan_status = 'ACTIVE'
  AND NOT EXISTS (
    SELECT 1 FROM mfi_actor.customer c WHERE c.id = la.customer_id
  );
