-- NEFT v2 double-disbursement dedupe — SINGLE query (no time bound)
-- Train: mfi_integration_v3.4.2.4 | Schema: mfi_accounting
-- DevOps: run as-is on schedule (e.g. every 30 min). No date filter.
--
-- Alert rule:
--   ANY row  => investigate (same CRR loan_account_number + same transaction_type
--               has >1 SUCCESS payment with DIFFERENT client_reference_number)
--   ZERO rows => PASS
--
-- Parent vs child CRR keying (verified 3.4.2.4):
--   Parent/INDL: loan_account_number = that LAN
--                transaction_type    = DISBURSEMENT_NEFT_NEF / _NEI [+_REINIT]
--   Child SHG/JLG money transfer (same disburseLoan orchestration):
--                loan_account_number = PARENT LAN only
--                  (CallBankAPIForIndividualChildLoanDisbursementProcessor L48-L49;
--                   PostNEFTChildLoanBankDisbursementProcessor L67-L75)
--                transaction_type    = …_EXTREF{child_external_ref}_NEFT_NEF/_NEI
--                  (L150: transactionType + EVNTQ + externalRefNumber + NEFT_SUFFIX)
--   Therefore GROUP BY (loan_account_number, transaction_type) is required:
--     - separates sibling child legs under one parent (no cross-child FP)
--     - still catches double pay on the SAME child EXTREF leg
--
-- False-positive hardening:
--   ✓ 1× NEF + 1× NEI SUCCESS (different transaction_type)
--   ✓ Primary then *_REINIT (different transaction_type)
--   ✓ Many children under one parent (different EXTREF in transaction_type)
--   ✓ NEFT v1 / inquiry / *_CALLBACK / '~' LAN / FAIL·UNKNOWN excluded
--   ✓ Same client_ref SUCCESS twice → DISTINCT = 1 → no alert

SELECT
    c.loan_account_number AS crr_loan_account_number,
    CASE
        WHEN c.transaction_type ~ 'EXTREF' THEN 'CHILD_LEG_UNDER_PARENT_LAN'
        ELSE 'PARENT_OR_INDL'
    END AS crr_scope,
    (regexp_match(c.transaction_type, 'EXTREF([^_]+)'))[1] AS child_external_ref,
    c.transaction_type,
    CASE WHEN c.transaction_type LIKE '%REINIT%' THEN 'REINIT' ELSE 'PRIMARY' END AS lane,
    CASE
        WHEN c.transaction_type ~ 'NEFT_NEI(_REINIT)?$' THEN 'NEI'
        WHEN c.transaction_type ~ 'NEFT_NEF(_REINIT)?$' THEN 'NEF'
        ELSE 'OTHER'
    END AS leg,
    COUNT(*) AS success_rows,
    COUNT(DISTINCT c.client_reference_number) AS distinct_client_refs,
    STRING_AGG(DISTINCT c.client_reference_number, ', ' ORDER BY c.client_reference_number) AS client_refs,
    MIN(c.system_date) AS first_success_at,
    MAX(c.system_date) AS last_success_at,
    MAX(la.disbursement_status) AS parent_disbursement_status,
    MAX(la.reinit_disbursement_status) AS parent_reinit_disbursement_status,
    MAX(la.loan_status) AS parent_loan_status
FROM mfi_accounting.client_request_response_log c
LEFT JOIN mfi_accounting.loan_account la
       ON la.la_account_number = c.loan_account_number
      AND la.is_deleted = false
WHERE c.partner = 'Hdfc'
  AND c.status = 'SUCCESS'
  AND c.loan_account_number NOT LIKE '~%'
  AND c.transaction_type ~ '(^|_)NEFT_NE[FI](_REINIT)?$'
  AND c.transaction_type NOT ILIKE '%CALLBACK%'
  AND c.transaction_type NOT ILIKE '%INQUIRY%'
GROUP BY
    c.loan_account_number,
    c.transaction_type
HAVING COUNT(DISTINCT c.client_reference_number) > 1
ORDER BY last_success_at DESC, crr_loan_account_number, transaction_type;
