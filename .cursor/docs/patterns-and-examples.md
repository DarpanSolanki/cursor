# Code Patterns and Examples

## Processor Pattern

```java
@Processor
public class ValidateLoanAccountDetailsProcessor extends AbstractProcessor {

    @Autowired
    private LoanAccountDAOService loanAccountDAOService;

    @Override
    protected void process(ExecutionContext executionContext) {
        // 1. Extract and validate
        String accountNumber = executionContext.getStringValue("account_number");
        if (StringUtils.isBlank(accountNumber)) {
            executionContext.put(NovopayCommonConstants.FIELD_NAME, "account_number");
            throw new NovopayFatalException("132247");
        }

        // 2. Business logic via service (method params preferred)
        LoanAccountEntity account = loanAccountDAOService.findByAccountNumber(accountNumber);
        if (account == null) {
            throw new NovopayFatalException("134139");
        }

        // 3. Set results for downstream processors
        executionContext.put("account_id", account.getId());
        executionContext.put("loan_account_entity", account);
    }
}
```

## Service Pattern

```java
@Service
@Slf4j
@RequiredArgsConstructor
public class LoanAccountService {

    private final LoanAccountDAOService loanAccountDAOService;

    // Method params for simple data passing
    public LoanAccountEntity findActiveAccount(String accountNumber) {
        LoanAccountEntity account = loanAccountDAOService.findByAccountNumber(accountNumber);
        if (account == null || !"ACTIVE".equals(account.getStatus())) {
            throw new NovopayFatalException("134139", "Active loan account not found: " + accountNumber);
        }
        return account;
    }

    // ExecutionContext when inter-service calls or audit context is needed
    public void processWithContext(ExecutionContext context) {
        String accountNumber = context.getStringValue("account_number");
        // inter-service call that needs context...
    }
}
```

## Repository Pattern

```java
@Repository
public interface LoanAccountRepository extends CrudRepository<LoanAccountEntity, Long> {

    // Simple: JPA method naming
    List<LoanAccountEntity> findByOfficeIdAndIsDeletedFalse(Long officeId);

    // Complex: native query
    @Query(nativeQuery = true, value =
        "SELECT * FROM loan_account WHERE account_number = :accountNumber AND is_deleted = false")
    LoanAccountEntity findByAccountNumber(@Param("accountNumber") String accountNumber);

    // Bulk: array param
    @Query(nativeQuery = true, value =
        "SELECT * FROM loan_account WHERE account_number = ANY(CAST(:accounts AS text[])) AND is_deleted = false")
    List<LoanAccountEntity> findByAccountNumbers(@Param("accounts") String[] accounts);

    // Bulk update
    @Modifying
    @Query(nativeQuery = true, value =
        "UPDATE loan_account SET office_id = :officeId, updated_by = :updatedBy, updated_on = :updatedOn " +
        "WHERE account_id IN (:ids) AND is_deleted = false")
    void updateOfficeByIds(@Param("ids") List<Long> ids, @Param("officeId") Long officeId,
                           @Param("updatedBy") Long updatedBy, @Param("updatedOn") Date updatedOn);
}
```

## Kafka Consumer Pattern

```java
public class LmsMessageBrokerConsumer implements NovopayMessageBrokerConsumer {

    @Override
    public void consumeMessage(String message, String topic, String tenant) {
        try {
            ThreadLocalContext.setTenant(new PlatformTenant(tenant));

            String[] parts = message.split("\\|");
            String apiName = parts[0];
            String requestBody = parts[1];
            String cacheKey = parts.length > 2 ? parts[2] : null;

            // Idempotency: check cache/status
            if (cacheKey != null && redisTemplate.hasKey(cacheKey)) {
                log.info("Already processing {}, skipping", cacheKey);
                return;
            }

            // Build context and execute
            ExecutionContext context = contextPopulator.populateExecutionContext(requestBody);
            serviceOrchestrator.executeProcessors(context, apiName);

        } catch (CannotAcquireLockException e) {
            throw e; // Rethrow for Kafka retry
        } catch (Exception e) {
            log.error("Failed to process message from {}: {}", topic, e.getMessage(), e);
        } finally {
            // Clean up Redis lock
        }
    }
}
```

## Inter-Service API Call Pattern

```java
@Override
protected void process(ExecutionContext executionContext) {
    // Prepare params (use putLocal to avoid leaking)
    executionContext.putLocal("source_emp_id", sourceEmpId);
    executionContext.putLocal("destn_emp_id", destnEmpId);

    // Call
    internalAPIClient.callInternalAPI(executionContext, "executeLOSPortfolioTransfer", "v1",
        "los_api_response", -1, -1, false);

    // IMPORTANT: This is a SEPARATE transaction boundary.
    // If this succeeds but the next call fails, this call's changes are committed.

    // Read response
    Long resultId = executionContext.getValueFromAPIResponse("los_api_response", "result_id", Long.class);
}
```

## Bank API Call Pattern

```java
@Override
protected void process(ExecutionContext executionContext) {
    // 1. Check current status (idempotency)
    String currentStatus = executionContext.getStringValue("disbursement_status");
    if ("ACTIVE".equals(currentStatus)) {
        executionContext.put("DO_TRANSACTION", false);
        return;
    }

    // 2. Populate bank request fields (putLocal — don't leak)
    executionContext.putLocal("beneficiary_account", account.getBeneficiaryAccount());
    executionContext.putLocal("amount", netDisbursedAmount.toPlainString());

    // 3. Call bank
    webClientDecorator.callBankService(executionContext, "neftTransfer", "POST", null);

    // 4. Parse response
    String replyCode = executionContext.getStringValue("replyCode");

    // 5. Update status
    if ("00".equals(replyCode)) {
        executionContext.put("disbursement_status", "NEFT_STAGE_2_PENDING");
    } else {
        executionContext.put("disbursement_status", "NEFT_FAILED");
    }
}
```

## Validator Pattern (Orchestration XML)

```xml
<Validator bean="mandatoryFieldValidator">
    <IParam fieldName="account_number" errorCode="132001"/>
</Validator>
<Validator bean="patternFieldValidator">
    <IParam fieldName="account_number" pattern="[A-Z0-9]+" errorCode="132002"/>
</Validator>
<Validator bean="numberValidator">
    <IParam fieldName="loan_amount" minValue="1" maxValue="999999999" errorCode="132003"/>
</Validator>
```

## Orchestration Flow Pattern

```xml
<API id="createLoanAccount" name="createLoanAccount" version="v1">
    <!-- Validators -->
    <Validator bean="mandatoryFieldValidator">
        <IParam fieldName="account_number" errorCode="132001"/>
    </Validator>

    <!-- Processors -->
    <Processor bean="populateCurrentDateProcessor"/>
    <Processor bean="validateLoanAccountDetailsProcessor"/>

    <!-- Control: branch by function_sub_code -->
    <Control method="regExp" pattern="${function_sub_code}" condition="=" value="CREATE">
        <Processor bean="createLoanAccountProcessor"/>
    </Control>
    <Control method="regExp" pattern="${function_sub_code}" condition="=" value="UPDATE">
        <Processor bean="updateLoanAccountProcessor"/>
    </Control>

    <!-- Post-processing -->
    <Processor bean="formatLoanAccountResponseProcessor"/>
</API>
```