# Loan transaction map (generated — do not hand-edit)

`python3 scripts/testing/transaction_map.py` regenerates this from the orchestration,
the shipped JTF templates and the KG. These flows run in production; this is what they
are, not what they should be.

**Control fields are headers**, never body: `function_code`, `function_sub_code`,
`run_mode`. Sent in the body the gateway answers `11008 Invalid run_mode`.

## disburseLoan

- **Orchestration:** `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml:580`
- **Request template:** `trustt-platform-accounting/deploy/application/templates/request/mfi/disburseLoan_requestTemplate.json`
- **Headers:** `function_code=DEFAULT`, `function_sub_code=DEFAULT`, `run_mode=TRIAL`
- **Mandatory:** `account_number`, `application_id`, `client_reference_number`
- **Calls other services:** `submitApplication`
- **Internal APIs:** `getLoanAccountDetails`, `postTransaction`, `submitApplication`
- **Writes:** `client_request_response_log`, `file_staging_post_disbursement_insurance`, `loan_account`, `loan_account_events_queue`, `loan_account_insurance_details`, `loan_account_nominee_details`, `loan_account_tax_details`, `loan_disbursement_charge_details`, `loan_disbursement_mode_details`, `loan_disbursement_transaction`, `loan_due_details`, `loan_installment_details` (+3 more)
- **Error codes:** 11008, 11012, 11013, 130008, 130015, 130121, 130199, 130202, 130216, 130474, 130475, 132010
- **Processors (35):** `populateUserDetails`, `validateLoanDisbursementDetailsProcessor`, `getMakerCheckerEnabledForUseCaseProcessor`, `populateCurrentDateProcessor`, `dummyProcessor`, `dummyProcessor`, `populateCurrentDateProcessor`, `populatePerformedDateProcessor`, `dummyProcessor`, `dummyProcessor` …
- **Branches:** ${function_code} = RESUBMIT; ${function_code} = DEFAULT; ${maker_checker_enabled} = 0; ${maker_checker_enabled} = 1; ${run_mode} = TRIAL; ${function_code} = APPROVE

## childLoanDisbursement

- **Orchestration:** `trustt-platform-accounting/deploy/application/orchestration/group_mfi_orc.xml:613`
- **Writes:** `loan_account`, `loan_account_events_queue`, `loan_account_tax_details`, `loan_disbursement_charge_details`, `loan_disbursement_mode_details`, `loan_disbursement_transaction`, `loan_due_details`, `loan_installment_details`
- **Processors (2):** `populateDataForChildLoanBookingProcessor`, `bookChildLoanProcessor`

## loanDisbursementCancellation

- **Orchestration:** `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml:3918`
- **Request template:** `trustt-platform-accounting/deploy/application/templates/request/product/loanDisbursementCancellation_requestTemplate.json`
- **Headers:** `function_code=DEFAULT`, `function_sub_code=DEFAULT`, `run_mode=REAL`
- **Mandatory:** `depositor_name`
- **Internal APIs:** `postTransaction`
- **Writes:** `client_request_response_log`, `disbursement_cancellation_insurance_staging_details`, `document`, `document_file`, `interest_accrual_details`, `loan_account`, `loan_account_events_queue`, `loan_account_payments_details`, `loan_account_servicing_document_events`, `loan_account_tax_details`, `loan_disbursement_cancellation_charge_details`, `loan_disbursement_cancellation_details` (+6 more)
- **Error codes:** 11008, 11012, 11013, 13012, 130132, 130279, 130280, 130281, 130320, 130321, 130322, 130323
- **Processors (82):** `populateUserDetails`, `setCommonAttributesProcessor`, `dummyProcessor`, `dummyProcessor`, `dummyProcessor`, `dummyProcessor`, `dummyProcessor`, `dummyProcessor`, `dummyProcessor`, `dummyProcessor` …
- **Branches:** ${function_sub_code} = DEFAULT; ${paid_by} = OTHERS; ${payment_mode} = NEFT|IFT; ${payment_mode} = CHEQUE; ${function_sub_code} = COLLECTED; ${function_sub_code} = DEFAULT

## childLoanDisbursementCancellation

- **Orchestration:** `trustt-platform-accounting/deploy/application/orchestration/group_mfi_orc.xml:475`
- **Internal APIs:** `postTransaction`
- **Writes:** `interest_accrual_details`, `loan_account`, `loan_account_payments_details`, `loan_due_details`, `loan_installment_details`, `waiver__loan_due_details`
- **Processors (13):** `setCommonAttributesProcessor`, `populateChildLoanDisbursementCancellationDataProcessor`, `checkLoanAccountInterestAccrualCalculationProcessor`, `checkLoanAccountInterestAccrualBookingProcessor`, `dummyProcessor`, `populateAdditionalAmountAndAccountDetailsForCancellationProcessor`, `populateAdditionalTaxAmountAndAccountDetailsFromChargeDetails`, `dummyProcessor`, `createLoanAccountPaymentsDetailsProcessor`, `updateLoanDueDetailsDataProcessor` …

## loanRepayment

- **Orchestration:** `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml:958`
- **Request template:** `trustt-platform-accounting/deploy/application/templates/request/product/loanRepayment_requestTemplate.json`
- **Headers:** `function_code=DEFAULT`, `function_sub_code=DEFAULT`, `run_mode=TRIAL`
- **Mandatory:** `account_number`, `client_reference_number`, `repayment_amount`, `repayment_mode`, `value_date`
- **Calls other services:** `getNotificationMessageByNotificationCode`
- **Internal APIs:** `getNotificationMessageByNotificationCode`, `postTransaction`, `getLoanAccountDetails`
- **Writes:** `client_request_response_log`, `loan_account`, `loan_account_closure_details`, `loan_account_events_queue`, `loan_account_payments_details`, `loan_due_details`, `loan_installment_details`
- **Error codes:** 11008, 11012, 11013, 130015, 130121, 130157, 130158, 130159, 132031, 132037, 132161, 132181
- **Processors (71):** `populateUserDetails`, `setCommonAttributesProcessor`, `setUserStoryForResponseProcessor`, `validateLoanAccountNumberAndStatusForRepayProcessor`, `validateLoanRepaymentData`, `autoPopulateChildLoansForRepaymentProcessor`, `validateChildLoansRepaymentDataProcessor`, `receiptNumberDedupProcessor`, `validateRoutingTypeValueProcessor`, `dummyProcessor` …
- **Branches:** ${repayment_mode} = NET_BANKING; ${repayment_mode} = NET_BANKING; ${repayment_mode} = CASH; ${repayment_mode} = DIRDR; ${repayment_mode} = ACH; ${repayment_mode} = UPI

## childLoanRepayment

- **Orchestration:** `trustt-platform-accounting/deploy/application/orchestration/group_mfi_orc.xml:33`
- **Writes:** `loan_account`, `loan_account_closure_details`, `loan_account_payments_details`, `loan_due_details`, `loan_installment_details`
- **Processors (33):** `populateChildLoanAccountDataProcessor`, `dummyProcessor`, `dummyProcessor`, `dummyProcessor`, `dummyProcessor`, `dummyProcessor`, `dummyProcessor`, `dummyProcessor`, `getOfficeIdFromAccountNumberProcessor`, `checkEligibleForRepaymentAppropriationProcessor` …
- **Branches:** ${repayment_mode} = CASH; ${repayment_mode} = DIRDR; ${repayment_mode} = ACH; ${repayment_mode} = UPI; ${repayment_mode} = DIGITAL; ${repayment_mode} = NET_BANKING

## loanPrepayment

- **Orchestration:** `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml:1675`
- **Request template:** `trustt-platform-accounting/deploy/application/templates/request/product/loanPrepayment_requestTemplate.json`
- **Calls other services:** `getNotificationMessageByNotificationCode`
- **Internal APIs:** `getNotificationMessageByNotificationCode`, `postTransaction`, `getLoanAccountDetails`
- **Writes:** `client_request_response_log`, `document`, `document_file`, `interest_accrual_details`, `loan_account`, `loan_account_closure_details`, `loan_account_events_queue`, `loan_account_payments_details`, `loan_account_servicing_document_events`, `loan_account_tax_details`, `loan_due_details`, `loan_due_details__loan_account_payments_details` (+8 more)
- **Error codes:** 13012, 132031, 132268, 132281, 132282, 134001, 134002, 134010, 134143, 134144, 134165, 134254
- **Processors (110):** `validateTransactionForLoanAccountProcessor`, `setUserStoryForResponseProcessor`, `setCommonAttributesProcessor`, `valdiateLoanAccountNumberAndStatusProcessor`, `populateUserDetails`, `fetchSuperDataForForeclosureProcessor`, `validateForChildLoanPrepaymentProcessor`, `validateLoanPrepaymentProductProcessor`, `checkLoanAccountInterestAndPenalAccrualProcessor`, `validateLoanPrepaymentDataProcessor` …
- **Branches:** ${function_code} = REJECT; ${function_code} = DEFAULT; ${function_sub_code} = DEFAULT; ${function_code} = APPROVE_TASK; ${function_code} = APPROVE; ${function_code} = DEFAULT

## childLoanForeclosure

- **Orchestration:** `trustt-platform-accounting/deploy/application/orchestration/group_mfi_orc.xml:256`
- **Writes:** `prepayment_details`
- **Processors (1):** `childLoanForeclosureProcessor`

## loanDeathForeclosure

- **Orchestration:** `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml:4948`
- **Request template:** `trustt-platform-accounting/deploy/application/templates/request/product/loanDeathForeclosure_requestTemplate.json`
- **Headers:** `function_code=STAGE_1`, `function_sub_code=DEFAULT`, `run_mode=TRIAL`
- **Mandatory:** `account_number`, `nominee_document_details`, `supporting_document_details`
- **Writes:** `death_foreclosure_appointee_details`, `death_foreclosure_details`, `death_foreclosure_details__document`, `death_foreclosure_insurance_staging_details`, `death_foreclosure_nominee_details`, `death_foreclosure_payment_mode_details`, `document`, `document_file`, `loan_account`, `task_cleanup_detail`
- **Error codes:** 11008, 11012, 11013, 13012, 130207, 130466, 130467, 130468, 130471, 132031, 132381, 134001
- **Processors (107):** `populateUserDetails`, `setCommonAttributesProcessor`, `valdiateLoanAccountNumberAndStatusForTransactionProcessor`, `validateDeathForeclosureDocumentsProcessor`, `validateTransactionForLoanAccountProcessor`, `deathForeclosureDedupCheckProcessor`, `syncDetailsForDeathForeclosureProcessor`, `createOrUpdateDeathForeclosureDetailsProcessor`, `deathForeClosureSMSNotification`, `excessAmountDeathForeclosureDetailsProcessor` …
- **Branches:** ${function_code} = REJECT; ${function_code} = REJECT; ${function_code} = STAGE_1; ${is_nominee_under_age} = true; ${verify_documents} = YES; ${function_code} = STAGE_2

## loanWriteoff

- **Orchestration:** `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml:1388`
- **Request template:** `trustt-platform-accounting/deploy/application/templates/request/product/loanWriteoff_requestTemplate.json`
- **Headers:** `function_code=DEFAULT`, `function_sub_code=DEFAULT`, `run_mode=TRIAL`
- **Mandatory:** `account_number`, `value_date`, `writeoff_amount`
- **Calls other services:** `submitApplication`
- **Internal APIs:** `postTransaction`, `getLoanAccountDetails`, `submitApplication`
- **Writes:** `loan_account`, `loan_account_payments_details`, `loan_due_details`, `loan_installment_details`
- **Error codes:** 11008, 11012, 11013, 130203, 130204, 130205, 130207, 130208, 130209, 130210, 130277, 130279
- **Processors (22):** `validateLoanWriteOffDataProcessor`, `populateUserDetails`, `getMakerCheckerEnabledForUseCaseProcessor`, `dummyProcessor`, `dummyProcessor`, `dummyProcessor`, `populateUserStoryProcessor`, `dummyProcessor`, `prepaymentApproppriationProcessor`, `populateAdditionalAmountDetailsProcessor` …
- **Branches:** ${function_code} = DEFAULT; ${maker_checker_enabled} = 1; ${maker_checker_enabled} = 0; ${function_code} = APPROVE; ${function_code} = RESUBMIT; ${post_transaction} = true

## loanAccountReopening

- **Orchestration:** `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml:3475`
- **Request template:** `trustt-platform-accounting/deploy/application/templates/request/product/loanAccountReopening_requestTemplate.json`
- **Headers:** `function_code=DEFAULT`, `function_sub_code=DEFAULT`
- **Mandatory:** `account_number`, `document_details`, `reason`
- **Writes:** `account_entry`, `client_request_response_log`, `document`, `document_file`, `interest_accrual_details`, `loan_account`, `loan_account_closure_details`, `loan_account_events_queue`, `loan_account_payments_details`, `loan_account_reopening__document`, `loan_account_reopening_details`, `loan_account_tax_details` (+7 more)
- **Error codes:** 11012, 11013, 130121, 130132, 130302, 130303, 130304, 130305, 130341, 130342, 130343, 130348
- **Processors (39):** `validateDataForLoanAccountReopeningProcessor`, `validateDocumentDataForGenericDocumentProcessor`, `populateUserDetails`, `setCommonAttributesProcessor`, `dummyProcessor`, `dummyProcessor`, `dummyProcessor`, `populateUserDetails`, `createLoanAccountReopeningDetailsProcessor`, `getLoanAccountByAccountNumberProcessor` …
- **Branches:** reason = OTHERS; ${function_code} = REJECT; ${function_code} = DEFAULT; ${function_code} = APPROVE; ${function_code} = REJECT; ${create_task} = true

## childLoanReopening

- **Orchestration:** `trustt-platform-accounting/deploy/application/orchestration/group_mfi_orc.xml:210`
- **Writes:** `account_entry`, `interest_accrual_details`, `loan_account`, `loan_account_closure_details`, `loan_due_details`, `loan_installment_details`, `penal_interest_accrual_details`, `transaction_details`, `transaction_master`, `transaction_partition_details`, `waiver_details`
- **Error codes:** 130121, 132161, 134071, 334
- **Processors (14):** `setCommonAttributesProcessor`, `populateChildLoanReopeningAccountDataProcessor`, `initiateClosureReversalProcessor`, `reverseTransactionProcessor`, `updateLoanAccountClosureDetailsProcessor`, `updateLoanAccountStatusProcessor`, `populateCurrentDateProcessor`, `populateEODJobDataAfterReversalProcessor`, `checkLoanAccountInterestAndPenalAccrualProcessor`, `checkLoanAccountInterestAccrualBookingProcessor` …

## loanAccountRestructuring

- **Orchestration:** `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml:5825`
- **Request template:** `trustt-platform-accounting/deploy/application/templates/request/product/loanAccountRestructuring_requestTemplate.json`
- **Headers:** `function_code=DEFAULT`, `function_sub_code=DEFAULT`, `run_mode=TRIAL`
- **Mandatory:** `bpi_amount`, `due_amount`, `existing_roi`, `is_roi_changed`, `loan_account_number`, `new_emi`, `new_roi`, `new_tenure`, `old_emi`, `old_tenure`, `overdue_amount`, `reason`, `rescheduling_effective_date`, `restructuring_impact`
- **Writes:** `loan_account`, `loan_account_events_queue`, `loan_account_reschedule_details`, `loan_account_restructuring_details`
- **Error codes:** 11008, 11012, 11013, 130132, 130381, 1303813, 130382, 130384, 130385, 130386, 130387, 130388
- **Processors (37):** `populateUserDetails`, `setCommonAttributesProcessor`, `dummyProcessor`, `dummyProcessor`, `dummyProcessor`, `dummyProcessor`, `dummyProcessor`, `dummyProcessor`, `validateDataForLoanAccountRestructuring`, `validateMaturityDateProcessor` …
- **Branches:** ${restructuring_impact} = UPDATE_EMI; ${restructuring_impact} = UPDATE_TENURE; ${is_roi_changed} = true; ${function_sub_code} = DEFAULT; ${function_code} = DEFAULT; ${run_mode} = TRIAL

## childLoanRestructuring

- **Orchestration:** `trustt-platform-accounting/deploy/application/orchestration/group_mfi_orc.xml:195`
- **Writes:** `account_interest_details`, `loan_account`, `loan_account_restructuring_details`, `loan_due_details`, `loan_installment_details`
- **Processors (3):** `childLoanRestructuringProcessor`, `createChildLoanAccountRestructuringDetailsProcessor`, `loanAdvanceRepaymentProcessor`
- **Branches:** ${function_code} = RESTRUCTURE; ${function_code} = FORECLOSURE

## childLoanTransactionReversal

- **Orchestration:** `trustt-platform-accounting/deploy/application/orchestration/group_mfi_orc.xml:383`
- **Writes:** `account_entry`, `loan_account`, `loan_account_payments_details`, `loan_due_details`, `loan_installment_details`, `transaction_details`, `transaction_master`, `transaction_partition_details`, `waiver_details`
- **Error codes:** 130121, 132161, 134071, 334
- **Processors (9):** `executeTransactionReversalProcessor`, `populateEODJobDataAfterReversalProcessor`, `populateLoanAccountPaymentDetailsDataProcessor`, `reverseTransactionProcessor`, `convertTransactionValueDateProcessor`, `createLoanAccountPaymentsDetailsProcessor`, `loanAccountDpdCalcProcessor`, `loanAccountAssetCriteriaProcessor`, `loanAccountAssetClassificationProcessor`

## waiveLoanAccountCharges

- **Orchestration:** `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml:3279`
- **Request template:** `trustt-platform-accounting/deploy/application/templates/request/product/waiveLoanAccountCharges_requestTemplate.json`
- **Headers:** `function_code=DEFAULT`, `function_sub_code=DEFAULT`, `run_mode=TRIAL`
- **Mandatory:** `document_details`
- **Writes:** `document`, `document_file`, `loan_account_events_queue`, `loan_due_details`, `task_cleanup_detail`, `waiver__document`, `waiver__loan_due_details`, `waiver_details`
- **Error codes:** 11008, 11012, 11013, 130132, 130241, 130278, 130283, 130285, 130286, 130287, 130302, 130303
- **Processors (30):** `validateDataForWaiverChargesProcessor`, `validateDocumentDataForGenericDocumentProcessor`, `populateUserDetails`, `setCommonAttributesProcessor`, `dummyProcessor`, `dummyProcessor`, `dummyProcessor`, `dummyProcessor`, `dummyProcessor`, `dummyProcessor` …
- **Branches:** ${function_code} = DEFAULT; ${run_mode} = TRIAL; ${run_mode} = REAL; ${function_code} = APPROVE; ${run_mode} = TRIAL; ${run_mode} = REAL

## childWaiveLoanAccountCharges

- **Orchestration:** `trustt-platform-accounting/deploy/application/orchestration/group_mfi_orc.xml:186`
- **Writes:** `loan_due_details`, `waiver__loan_due_details`
- **Processors (3):** `populateChildLoanWaiverDataProcessor`, `updateLoanDueDetailsForWaiverProcessor`, `updateWaiverLoanDueDetailsProcessor`

## loanAccountExcessAmountRefund

- **Orchestration:** `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml:4483`
- **Request template:** `trustt-platform-accounting/deploy/application/templates/request/product/loanAccountExcessAmountRefund_requestTemplate.json`
- **Headers:** `function_code=DEFAULT`, `function_sub_code=DEFAULT`
- **Internal APIs:** `postTransaction`
- **Writes:** `client_request_response_log`, `loan_account`, `loan_account_events_queue`, `loan_account_excess_amount_refund_details`, `loan_account_payments_details`
- **Error codes:** 11012, 11013, 130132, 130365, 130366, 130367, 130368, 130369, 130371, 130372, 130373, 130374
- **Processors (36):** `setCommonAttributesProcessor`, `validateTransactionForLoanAccountProcessor`, `validateDataForLoanAccountExcessAmountRefundProcessor`, `setPaymentModeProcessor`, `populateUserDetails`, `dummyProcessor`, `dummyProcessor`, `dummyProcessor`, `populateUserDetails`, `createLoanAccountExcessAmountRefundDetailsProcessor` …
- **Branches:** ${refund_mode} = TO_CAPTURE_BANK_ACCT|TO_NEW_BANK_ACCT; ${payment_mode} = OTHBACCT; ${refund_mode} = TO_NEW_BANK_ACCT; ${reason} = OTHER; ${function_code} = REJECT; ${function_code} = DEFAULT

## proactiveExcessAmountRefund

- **Orchestration:** `trustt-platform-accounting/deploy/application/orchestration/ServiceOrchestrationXML.xml:9531`
- **Request template:** `trustt-platform-accounting/deploy/application/templates/request/product/proactiveExcessAmountRefund_requestTemplate.json`
- **Processors (1):** `proactiveExcessAmountRefundJobProcessor`

## loanAccountClosure

- **Orchestration:** `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml:2572`
- **Request template:** `trustt-platform-accounting/deploy/application/templates/request/product/loanAccountClosure_requestTemplate.json`
- **Processors (1):** `loanAccountAutoClosureBatchProcessor`

## postTransaction

- **Orchestration:** `trustt-platform-accounting/deploy/application/orchestration/product_transaction_orc.xml:3`
- **Request template:** `trustt-platform-accounting/deploy/application/templates/request/product/postTransaction_requestTemplate.json`
- **Writes:** `account_balance`, `account_entry`, `client_reference_number`, `transaction_details`, `transaction_master`, `transaction_metadata`, `transaction_partition_details`
- **Error codes:** 11008, 11012, 11013, 132160, 134065, 134066, 134069, 134070, 134077, 134094, 134182, 134207
- **Processors (23):** `validateTransactionDataProcessor`, `populateAdditionalInformationProcessor`, `populateAndValidateAccountDetailsProcessor`, `populateAdditionalAmountProcessor`, `clientReferenceNumberDedupProcessor`, `getTransactionCatalogueIdProcessor`, `getTransactionRuleListProcessor`, `executeTransactionRulesProcessor`, `populateLimitRequestProcessor`, `validateActorAccountBalanceProcessor` …
- **Branches:** ${run_mode} = TRIAL; ${run_mode} = REAL

## reverseTransaction

- **Orchestration:** `trustt-platform-accounting/deploy/application/orchestration/product_transaction_orc.xml:80`
- **Request template:** `trustt-platform-accounting/deploy/application/templates/request/product/reverseTransaction_requestTemplate.json`
- **Headers:** `function_code=DEFAULT`, `function_sub_code=DEFAULT`, `run_mode=REAL`
- **Writes:** `account_entry`, `transaction_details`, `transaction_master`, `transaction_partition_details`
- **Error codes:** 11008, 11012, 11013, 130121, 132161, 134071
- **Processors (1):** `reverseTransactionProcessor`

## loanRecurringPaymentBatchApi

- **Orchestration:** `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml:3245`
- **Request template:** `trustt-platform-accounting/deploy/application/templates/request/product/loanRecurringPaymentBatchApi_requestTemplate.json`
- **Processors (1):** `loanRecurringPaymentBatchProcessor`
- **Branches:** ${function_sub_code} = BATCH

## loanAdvanceRepayment

- **Orchestration:** `trustt-platform-accounting/deploy/application/orchestration/loans_orc.xml:2586`
- **Request template:** `trustt-platform-accounting/deploy/application/templates/request/product/loanAdvanceRepayment_requestTemplate.json`
- **Processors (2):** `loanAdvanceRepaymentProcessor`, `loanAdvanceRepaymentBatchProcessor`
- **Branches:** ${function_sub_code} = DEFAULT; ${function_sub_code} = BATCH

