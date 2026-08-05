WITH r AS (
    SELECT
        c.loan_account_number AS lan,
        substring(c.transaction_type FROM '_EXTREF([^_]+)_(?:MFT|NEFT)') AS child_ext_ref,
        (regexp_match(c.client_reference_number,
                      '^(' || c.loan_account_number || '[0-9]*?)(0[26789])([0-9]+)$')) AS ref_parts,
        CASE WHEN c.transaction_type LIKE '%\_REINIT' THEN 'REINIT' ELSE 'PRIMARY' END AS lane,
        CASE WHEN c.transaction_type ~ '_MFT(_REINIT)?$'                  THEN 'MFT'
             WHEN c.transaction_type = 'MFT_TRANSACTION_INQUIRY'          THEN 'MINQ'
             WHEN c.transaction_type ~ '_NEFT_NE[FI]_CALLBACK(_REINIT)?$' THEN 'CB'
             WHEN c.transaction_type ~ '_NEFT_NEF(_REINIT)?$'             THEN 'NEF'
             WHEN c.transaction_type ~ '_NEFT_NEI(_REINIT)?$'             THEN 'NEI'
             ELSE 'NINQ' END AS leg,
        c.status,
        c.client_reference_number AS ref,
        substring(c.response FROM '(?:referenceno|internalReferenceNumber)"?\s*[:=]\s*"?([A-Za-z0-9]+)') AS bank_ref,
        c.system_date
    FROM mfi_accounting.client_request_response_log c
    WHERE c.partner = 'Hdfc'
      AND c.loan_account_number NOT LIKE '~%'
      AND c.loan_account_number <> 'UNRESOLVED'
      AND c.status IN ('SUCCESS', 'UNKNOWN')
      AND (c.transaction_type ~ '_MFT(_REINIT)?$'
           OR c.transaction_type = 'MFT_TRANSACTION_INQUIRY'
           OR c.transaction_type ~ '_NEFT_NE[FI](_CALLBACK)?(_REINIT)?$'
           OR c.transaction_type = 'NEFT_TRANSACTION_INQUIRY')
),
p AS (
    SELECT r.*,
           COALESCE(r.ref_parts[1], r.lan || COALESCE(r.child_ext_ref, '')) AS pay_id,
           r.ref_parts[3] AS attempt
    FROM r
),
prim AS (
    SELECT p.pay_id,
           array_agg(DISTINCT p.attempt) FILTER (WHERE p.leg IN ('NEF', 'NEI')) AS neft_attempts
    FROM p
    WHERE p.lane = 'PRIMARY' AND p.status = 'SUCCESS' AND p.attempt IS NOT NULL
    GROUP BY p.pay_id
),
q AS (
    SELECT p.*,
           (p.lane = 'PRIMARY' AND p.leg = 'MFT' AND p.status = 'SUCCESS')
           OR (p.lane = 'PRIMARY' AND p.leg IN ('NINQ', 'CB') AND p.status = 'SUCCESS'
               AND p.attempt = ANY(COALESCE(prim.neft_attempts, ARRAY[]::text[]))) AS bank_ref_primary
    FROM p LEFT JOIN prim ON prim.pay_id = p.pay_id
)
SELECT
    MIN(q.lan)                                                                          AS lan,
    MIN(q.child_ext_ref)                                                                AS child_ext_ref,
    q.pay_id,
    CASE WHEN COUNT(DISTINCT q.ref) FILTER (
              WHERE q.lane = 'PRIMARY' AND q.leg = 'MFT' AND q.status = 'SUCCESS') > 0
          AND COUNT(DISTINCT q.ref) FILTER (
              WHERE q.lane = 'PRIMARY' AND q.leg = 'NEI' AND q.status = 'SUCCESS') > 0
              THEN 'D1_PAID_ON_BOTH_RAILS'
         WHEN COUNT(DISTINCT q.ref) FILTER (
              WHERE q.lane = 'PRIMARY' AND q.leg = 'MFT' AND q.status = 'SUCCESS') > 1
              THEN 'D2_DOUBLE_MFT_TRANSFER'
         WHEN COUNT(DISTINCT q.ref) FILTER (
              WHERE q.lane = 'PRIMARY' AND q.leg = 'NEI' AND q.status = 'SUCCESS') > 1
              THEN 'D3_DOUBLE_NEFT_STAGE2'
         WHEN COUNT(DISTINCT q.ref) FILTER (
              WHERE q.lane = 'PRIMARY' AND q.leg = 'MFT') > 1
              THEN 'D4_MFT_UNKNOWN_THEN_NEW_REF'
         ELSE 'OK' END                                                                  AS verdict,
    COUNT(DISTINCT q.ref) FILTER (
        WHERE q.lane = 'PRIMARY' AND q.leg = 'MFT' AND q.status = 'SUCCESS')            AS mft_paid,
    COUNT(DISTINCT q.ref) FILTER (
        WHERE q.lane = 'PRIMARY' AND q.leg = 'MFT' AND q.status = 'UNKNOWN')            AS mft_unknown,
    COUNT(DISTINCT q.ref) FILTER (
        WHERE q.lane = 'PRIMARY' AND q.leg = 'NEF' AND q.status = 'SUCCESS')            AS neft_stage1_attempts,
    COUNT(DISTINCT q.ref) FILTER (
        WHERE q.lane = 'PRIMARY' AND q.leg = 'NEI' AND q.status = 'SUCCESS')            AS neft_paid,
    COUNT(DISTINCT q.ref) FILTER (
        WHERE q.lane = 'REINIT' AND q.leg IN ('MFT', 'NEI') AND q.status = 'SUCCESS')   AS reinit_paid_not_flagged,
    COUNT(*) FILTER (WHERE q.leg = 'CB')                                                AS neft_callbacks,
    COUNT(DISTINCT q.bank_ref) FILTER (WHERE q.bank_ref_primary)                        AS distinct_bank_refs,
    STRING_AGG(DISTINCT q.bank_ref, ', ') FILTER (WHERE q.bank_ref_primary)             AS bank_refs,
    MIN(q.system_date)                                                                  AS first_seen,
    MAX(q.system_date)                                                                  AS last_seen
FROM q
GROUP BY q.pay_id
HAVING COUNT(DISTINCT q.ref) FILTER (
           WHERE q.lane = 'PRIMARY' AND q.leg = 'MFT' AND q.status = 'SUCCESS') > 1
    OR COUNT(DISTINCT q.ref) FILTER (
           WHERE q.lane = 'PRIMARY' AND q.leg = 'NEI' AND q.status = 'SUCCESS') > 1
    OR (COUNT(DISTINCT q.ref) FILTER (
            WHERE q.lane = 'PRIMARY' AND q.leg = 'MFT' AND q.status = 'SUCCESS') > 0
        AND COUNT(DISTINCT q.ref) FILTER (
            WHERE q.lane = 'PRIMARY' AND q.leg = 'NEI' AND q.status = 'SUCCESS') > 0)
    OR COUNT(DISTINCT q.ref) FILTER (
           WHERE q.lane = 'PRIMARY' AND q.leg = 'MFT') > 1
ORDER BY 4, last_seen DESC;
