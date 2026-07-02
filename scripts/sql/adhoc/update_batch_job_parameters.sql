-- Update script for batch job parameters
-- Updates force_chunk, force_grid_size, force_async, and is_multi_node for specified batch jobs
-- Jobs: loanAccountDpdCalcJob, loanAccountAssetCriteriaJob, loanAccountAssetClassificationJob,
--       penalInterestAccrualCalculation, penalInterestAccrualBooking, updateBusinessDate,
--       loanAccountClosure, trialBalanceCalculation, generatePostEODReports,
--       interestAccrualCalculation, interestAccrualPosting, loanAccountBillingJob, loanAdvanceRepayment

-- Update force_chunk = '100'
UPDATE batch_job_parameter 
SET param_value = '100' 
WHERE param_name = 'force_chunk' 
  AND job_id IN (
    SELECT id FROM batch_job 
    WHERE LOWER(TRIM(name)) IN (
      'loanaccountdpdcalcjob',
      'loanaccountassetcriteriasjob',
      'loanaccountassetclassificationjob',
      'penalinterestaccrualcalculation',
      'penalinterestaccrualbooking',
      'updatebusinessdate',
      'loanaccountclosure',
      'trialbalancecalculation',
      'generateposteodreports',
      'interestaccrualcalculation',
      'interestaccrualposting',
      'loanaccountbillingjob',
      'loanadvancerepayment'
    )
  );

-- Update force_grid_size = '50'
UPDATE batch_job_parameter 
SET param_value = '50' 
WHERE param_name = 'force_grid_size' 
  AND job_id IN (
    SELECT id FROM batch_job 
    WHERE LOWER(TRIM(name)) IN (
      'loanaccountdpdcalcjob',
      'loanaccountassetcriteriasjob',
      'loanaccountassetclassificationjob',
      'penalinterestaccrualcalculation',
      'penalinterestaccrualbooking',
      'updatebusinessdate',
      'loanaccountclosure',
      'trialbalancecalculation',
      'generateposteodreports',
      'interestaccrualcalculation',
      'interestaccrualposting',
      'loanaccountbillingjob',
      'loanadvancerepayment'
    )
  );

-- Update force_async = 'TRUE'
UPDATE batch_job_parameter 
SET param_value = 'TRUE' 
WHERE param_name = 'force_async' 
  AND job_id IN (
    SELECT id FROM batch_job 
    WHERE LOWER(TRIM(name)) IN (
      'loanaccountdpdcalcjob',
      'loanaccountassetcriteriasjob',
      'loanaccountassetclassificationjob',
      'penalinterestaccrualcalculation',
      'penalinterestaccrualbooking',
      'updatebusinessdate',
      'loanaccountclosure',
      'trialbalancecalculation',
      'generateposteodreports',
      'interestaccrualcalculation',
      'interestaccrualposting',
      'loanaccountbillingjob',
      'loanadvancerepayment'
    )
  );

-- Update is_multi_node = 'TRUE'
UPDATE batch_job_parameter 
SET param_value = 'TRUE' 
WHERE param_name = 'is_multi_node' 
  AND job_id IN (
    SELECT id FROM batch_job 
    WHERE LOWER(TRIM(name)) IN (
      'loanaccountdpdcalcjob',
      'loanaccountassetcriteriasjob',
      'loanaccountassetclassificationjob',
      'penalinterestaccrualcalculation',
      'penalinterestaccrualbooking',
      'updatebusinessdate',
      'loanaccountclosure',
      'trialbalancecalculation',
      'generateposteodreports',
      'interestaccrualcalculation',
      'interestaccrualposting',
      'loanaccountbillingjob',
      'loanadvancerepayment'
    )
  );

-- Verification query: Check updated parameters
SELECT 
    bj.id as job_id,
    bj.name as job_name,
    bjp.param_name,
    bjp.param_value
FROM batch_job bj
LEFT JOIN batch_job_parameter bjp ON bj.id = bjp.job_id 
    AND bjp.param_name IN ('force_chunk', 'force_grid_size', 'force_async', 'is_multi_node')
WHERE LOWER(TRIM(bj.name)) IN (
    'loanaccountdpdcalcjob',
    'loanaccountassetcriteriasjob',
    'loanaccountassetclassificationjob',
    'penalinterestaccrualcalculation',
    'penalinterestaccrualbooking',
    'updatebusinessdate',
    'loanaccountclosure',
    'trialbalancecalculation',
    'generateposteodreports',
    'interestaccrualcalculation',
    'interestaccrualposting',
    'loanaccountbillingjob',
    'loanadvancerepayment'
)
ORDER BY bj.name, bjp.param_name;






