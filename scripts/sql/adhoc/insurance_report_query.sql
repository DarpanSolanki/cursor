WITH contact_detail_one_per_actor AS (
    SELECT acdm.actor_id, MAX(acdm.contact_detail_id) AS contact_detail_id
    FROM mfi_actor.actor__contact_detail__mapping acdm
    WHERE acdm.is_deleted = false
    GROUP BY acdm.actor_id
),
filtered_loan_accounts AS (
    SELECT la.account_id, la.filler_3, la.parent_loan_account_id, la.has_child_accounts,
           la.external_ref_number, la.term_unit, la.term, la.expected_disbursement_date,
           a.account_number, a.office_id
    FROM mfi_accounting.loan_account la
    INNER JOIN mfi_accounting.account a ON la.account_id = a.id
    WHERE la.expected_disbursement_date >= '2026-02-01 00:00:00.000'
        AND la.expected_disbursement_date <= '2026-02-13 23:59:59.999'
        AND la.is_deleted = false
        AND la.disbursement_status = 'COMPLETED'
),
group_sum_assured_precalc AS (
    SELECT la.filler_3, COALESCE(SUM(laid.sum_assured), 0) AS group_sum_assured
    FROM filtered_loan_accounts la
    LEFT JOIN mfi_accounting.loan_account_insurance_details laid ON la.account_id = laid.loan_account_id 
        AND laid.is_deleted = false
    WHERE la.filler_3 IS NOT NULL
    GROUP BY la.filler_3
)
SELECT DISTINCT ON (laid.id)
    o.description AS "Region",
    fla.account_number AS "Loan Account No",
    CASE 
        WHEN fla.has_child_accounts = true THEN fla.account_number
        WHEN fla.parent_loan_account_id IS NOT NULL THEN 
            COALESCE(parent_a.account_number, fla.account_number)
        ELSE fla.account_number
    END AS "Parent LAN number",
    gd.formatted_id AS "Group ID",
    gd.group_name AS "Group name",
    COALESCE(loan_app.loan_product_code, '') AS "Loan Product",
    ip_product.name AS "Insurance_Product_Name",
    COALESCE(fspdi.reference_number, laid.policy_number, '') AS "UNIQUE_REF_NO",
    laid.applicable_for AS "Relationship with Borrower",
    laid.insured_name AS "Name",
    CASE 
        WHEN laid.insured_dob IS NOT NULL 
        THEN TO_CHAR(laid.insured_dob, 'DD-Mon-YYYY')
        ELSE ''
    END AS "Date of Birth",
    laid.insured_gender AS "Gender",
    COALESCE(
        CASE WHEN laid.applicable_for IN ('SPOUSE', 'BORROWER_SPOUSE') THEN
            COALESCE(addr_borrower.address_line_1, '') || ' ' ||
            COALESCE(addr_borrower.address_line_2, '') || ' ' ||
            COALESCE(addr_borrower.pincode::text, '')
        ELSE
            COALESCE(addr.address_line_1, '') || ' ' ||
            COALESCE(addr.address_line_2, '') || ' ' ||
            COALESCE(addr.pincode::text, '')
        END,
        ''
    ) AS "Address",
    COALESCE(lapd.occupation, '') AS "Occupation",
    '' AS "Telephone No",
    COALESCE(cd_ins.mobile_number, laid.insured_mobile_no, '') AS "Mobile No",
    COALESCE(ins_borrower.email_id, '') AS "Email ID",
    CASE 
        WHEN fla.expected_disbursement_date IS NOT NULL 
        THEN TO_CHAR(fla.expected_disbursement_date, 'DD-Mon-YYYY')
        ELSE ''
    END AS "Disbursal Date",
    laid.sum_assured AS "Sum Assured Rs.",
    COALESCE(gsa.group_sum_assured, 0) AS "Group sum assured",
    laid.premium_amount AS "Premium",
    CASE 
        WHEN term_calc.term_months BETWEEN 1 AND 12 THEN 1
        WHEN term_calc.term_months BETWEEN 13 AND 24 THEN 2
        WHEN term_calc.term_months > 24 THEN 3
        ELSE NULL
    END AS "Term",
    term_calc.term_months AS "Tenure in months",
    land.nominee_name AS "Nominee Name",
    CASE 
        WHEN land.date_of_birth IS NOT NULL 
        THEN TO_CHAR(land.date_of_birth, 'DD-Mon-YYYY')
        ELSE ''
    END AS "Nominee DOB",
    land.gender AS "Gender",
    laad.appointee_full_name AS "Appointee Name",
    '' AS "Appointee Address",
    CASE 
        WHEN laad.appointee_date_of_birth IS NOT NULL 
        THEN TO_CHAR(laad.appointee_date_of_birth, 'DD-Mon-YYYY')
        ELSE ''
    END AS "Appointee DOB",
    laad.appointee_gender AS "Gender",
    laad.appointee_relationship AS "Relationship to nominee",
    COALESCE(UPPER(ins_borrower.fatca_city_of_birth_code), o.name, '') AS "Place",
    COALESCE(
        CASE WHEN laid.applicable_for IN ('SPOUSE', 'BORROWER_SPOUSE') AND lafd_spouse.id IS NOT NULL THEN
            (SELECT kdd.kyc_number FROM mfi_los.kyc_document_details kdd
             WHERE kdd.entity_type_id = lafd_spouse.id
               AND kdd.entity_type = 'FAMILY_MEMBER'
               AND kdd.document_type = 'KYC' AND kdd.kyc_type = 'VOTER_ID'
               AND kdd.loan_app_id = loan_app.id AND kdd.is_deleted = false
             ORDER BY kdd.id DESC LIMIT 1)
        ELSE
            (SELECT kdd.kyc_number FROM mfi_los.kyc_document_details kdd
             WHERE kdd.entity_type_id = ins_borrower.id
               AND kdd.entity_type IN ('BORROWER', 'CO-BORROWER')
               AND kdd.document_type = 'KYC' AND kdd.kyc_type = 'VOTER_ID'
               AND kdd.loan_app_id = loan_app.id AND kdd.is_deleted = false
             ORDER BY kdd.id DESC LIMIT 1)
        END,
        CASE WHEN laid.applicable_for IN ('SPOUSE', 'BORROWER_SPOUSE') AND lafd_spouse.id IS NOT NULL THEN
            (SELECT kdd.kyc_number FROM mfi_los.kyc_document_details kdd
             WHERE kdd.entity_type_id = lafd_spouse.id
               AND kdd.entity_type = 'FAMILY_MEMBER'
               AND kdd.document_type = 'OTHER' AND kdd.kyc_type = 'VOTER_ID'
               AND kdd.loan_app_id = loan_app.id AND kdd.is_deleted = false
             ORDER BY kdd.id DESC LIMIT 1)
        ELSE
            (SELECT kdd.kyc_number FROM mfi_los.kyc_document_details kdd
             WHERE kdd.entity_type_id = ins_borrower.id
               AND kdd.entity_type IN ('BORROWER', 'CO-BORROWER')
               AND kdd.document_type = 'OTHER' AND kdd.kyc_type = 'VOTER_ID'
               AND kdd.loan_app_id = loan_app.id AND kdd.is_deleted = false
             ORDER BY kdd.id DESC LIMIT 1)
        END,
        ''
    ) AS "Voter ID",
    COALESCE(fspdi.primary_agr_number, fla.account_number) AS "Primary Agr No",
    COALESCE((
        SELECT 
            COALESCE(
                MAX(CASE WHEN he.hierarchy_level_id = 2 THEN he.name END),
                MAX(CASE WHEN he2.hierarchy_level_id = 2 THEN he2.name END),
                MAX(CASE WHEN he3.hierarchy_level_id = 2 THEN he3.name END),
                MAX(CASE WHEN he4.hierarchy_level_id = 2 THEN he4.name END)
            )
        FROM mfi_actor.office__address__mapping oam
        LEFT JOIN mfi_actor.address oad ON oad.id = oam.address_id
        LEFT JOIN mfi_actor.hierarchy_element he ON he.id = oad.geo_element_id
        LEFT JOIN mfi_actor.hierarchy_element he2 ON he2.id = he.parent
        LEFT JOIN mfi_actor.hierarchy_element he3 ON he3.id = he2.parent
        LEFT JOIN mfi_actor.hierarchy_element he4 ON he4.id = he3.parent
        WHERE oam.office_id = o.id 
            AND oam.is_deleted = false
    ), '') AS "State",
    o.external_branch_code AS "BRANCHID",
    o.formatted_id AS "Novopay Branch code",
    COALESCE(e.formatted_id, '') AS "SM/RM CODE",
    laid.applicable_for AS "Member/Spouse"
FROM filtered_loan_accounts fla
INNER JOIN mfi_accounting.loan_account_insurance_details laid ON fla.account_id = laid.loan_account_id 
    AND laid.is_deleted = false
INNER JOIN mfi_actor.office o ON fla.office_id = o.id
LEFT JOIN LATERAL (
    SELECT CASE 
        WHEN fla.term_unit = 'MONTH' THEN fla.term
        WHEN fla.term_unit = 'YEAR' THEN fla.term * 12
        WHEN fla.term_unit = 'WEEK' THEN fla.term / 4.0
        WHEN fla.term_unit = 'DAY' THEN fla.term / 30.0
        ELSE fla.term
    END AS term_months
) term_calc ON true
LEFT JOIN mfi_accounting.account parent_a ON fla.parent_loan_account_id = parent_a.id
LEFT JOIN mfi_los.group_details gd ON fla.filler_3 = gd.id::text AND gd.is_deleted = false
LEFT JOIN mfi_accounting.product ip_product ON laid.insurance_product_code = ip_product.code 
    AND ip_product.is_deleted = false
LEFT JOIN mfi_accounting.file_staging_post_disbursement_insurance fspdi ON fspdi.loan_account_insurance_details_id = laid.id 
    AND fspdi.is_deleted = false
LEFT JOIN mfi_accounting.loan_account_nominee_details land ON laid.id = land.insurance_id 
    AND land.is_deleted = false
LEFT JOIN mfi_los.loan_app loan_app ON loan_app.id = fla.external_ref_number::bigint
LEFT JOIN mfi_los.borrower borrower_primary ON borrower_primary.loan_app_id = loan_app.id 
    AND borrower_primary.borrower_type = 'BORROWER' AND borrower_primary.is_deleted = false
LEFT JOIN mfi_actor.customer c_borrower ON c_borrower.formatted_id = borrower_primary.formatted_customer_id::text AND c_borrower.is_deleted = false
LEFT JOIN LATERAL (
    SELECT a3.address_line_1, a3.address_line_2, a3.pincode
    FROM mfi_actor.actor__address__mapping aam3
    INNER JOIN mfi_actor.address a3 ON a3.id = aam3.address_id AND a3.is_deleted = false
    WHERE aam3.actor_id = c_borrower.actor_id AND aam3.is_deleted = false
    ORDER BY CASE WHEN a3.type = 'PERMANENT' THEN 1 WHEN a3.type = 'CORRESPONDENCE' THEN 2 ELSE 3 END, a3.id
    LIMIT 1
) addr_borrower ON true
LEFT JOIN mfi_los.borrower ins_borrower ON ins_borrower.loan_app_id = loan_app.id 
    AND ins_borrower.borrower_type = CASE 
        WHEN laid.applicable_for = 'BORROWER' THEN 'BORROWER'
        WHEN laid.applicable_for IN ('SPOUSE', 'BORROWER_SPOUSE') THEN 'SPOUSE'
        WHEN laid.applicable_for = 'CO-BORROWER' THEN 'CO-BORROWER'
        ELSE laid.applicable_for
    END
    AND ins_borrower.is_deleted = false
LEFT JOIN mfi_los.loan_app__family_details lafd_spouse ON lafd_spouse.loan_app_id = loan_app.id 
    AND lafd_spouse.borrower_id = borrower_primary.id 
    AND lafd_spouse.relationship_with_borrower = 'SPOUSE' 
    AND lafd_spouse.is_deleted = false
LEFT JOIN mfi_actor.customer c ON c.formatted_id = ins_borrower.formatted_customer_id::text AND c.is_deleted = false
LEFT JOIN contact_detail_one_per_actor cd_opa ON cd_opa.actor_id = c.actor_id
LEFT JOIN mfi_actor.contact_detail cd_ins ON cd_ins.id = cd_opa.contact_detail_id AND cd_ins.is_deleted = false
LEFT JOIN LATERAL (
    SELECT a2.address_line_1, a2.address_line_2, a2.pincode
    FROM mfi_actor.actor__address__mapping aam2
    INNER JOIN mfi_actor.address a2 ON a2.id = aam2.address_id AND a2.is_deleted = false
    WHERE aam2.actor_id = c.actor_id AND aam2.is_deleted = false
    ORDER BY CASE WHEN a2.type = 'PERMANENT' THEN 1 WHEN a2.type = 'CORRESPONDENCE' THEN 2 ELSE 3 END, a2.id
    LIMIT 1
) addr ON true
LEFT JOIN mfi_los.loan_app_psl_data lapd ON lapd.loan_app_id = loan_app.id AND lapd.is_deleted = false
LEFT JOIN mfi_actor.employee e ON e.id = loan_app.employee_id
LEFT JOIN mfi_los.loan_app__appointee_details laad ON laad.loan_app_id = loan_app.id 
    AND laad.is_deleted = false
LEFT JOIN group_sum_assured_precalc gsa ON fla.filler_3 = gsa.filler_3
WHERE fla.account_id IS NOT NULL
ORDER BY laid.id, fla.expected_disbursement_date, fla.account_number;
