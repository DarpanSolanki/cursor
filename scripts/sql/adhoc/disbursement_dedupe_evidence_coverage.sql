SELECT
    CASE WHEN c.transaction_type ~ '_MFT(_REINIT)?$'                  THEN 'MFT  payment  (money moved on SUCCESS)'
         WHEN c.transaction_type = 'MFT_TRANSACTION_INQUIRY'          THEN 'MINQ MFT status inquiry'
         WHEN c.transaction_type ~ '_NEFT_NE[FI]_CALLBACK(_REINIT)?$' THEN 'CB   NEFT callback (3.4.2.5+ only)'
         WHEN c.transaction_type ~ '_NEFT_NEF(_REINIT)?$'             THEN 'NEF  NEFT stage-1 submit (NOT money)'
         WHEN c.transaction_type ~ '_NEFT_NEI(_REINIT)?$'             THEN 'NEI  NEFT stage-2'
         ELSE 'NINQ NEFT status inquiry' END                      AS leg,
    c.status,
    count(*)                                                      AS rows,
    count(DISTINCT c.loan_account_number)                         AS lans,
    count(*) FILTER (WHERE c.transaction_type LIKE '%\_EXTREF%')   AS child_rows,
    count(*) FILTER (WHERE c.response ~ '(?:referenceno|internalReferenceNumber)"?\s*[:=]')
                                                                  AS rows_with_bank_ref,
    count(*) FILTER (WHERE c.client_reference_number ~ ('^' || c.loan_account_number || '[0-9]*0[26789][0-9]+$'))
                                                                  AS deterministic_refs,
    min(c.system_date)                                            AS first_seen,
    max(c.system_date)                                            AS last_seen
FROM mfi_accounting.client_request_response_log c
WHERE c.partner = 'Hdfc'
  AND c.loan_account_number NOT LIKE '~%'
  AND (c.transaction_type ~ '_MFT(_REINIT)?$'
       OR c.transaction_type = 'MFT_TRANSACTION_INQUIRY'
       OR c.transaction_type ~ '_NEFT_NE[FI](_CALLBACK)?(_REINIT)?$'
       OR c.transaction_type = 'NEFT_TRANSACTION_INQUIRY')
GROUP BY 1, 2
ORDER BY 1, 2;
