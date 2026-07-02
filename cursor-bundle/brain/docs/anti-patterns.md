# Anti-Patterns to Avoid

## ExecutionContext

```java
// ❌ Using put() for transient/API-call data
executionContext.put("bank_request_field", value); // Leaks to downstream processors
// ✅ Use putLocal() for transient data
executionContext.putLocal("bank_request_field", value);

// ❌ No null check before use
String accountNumber = executionContext.getStringValue("account_number");
daoService.findByAccountNumber(accountNumber); // NPE if null
// ✅ Validate before use
String accountNumber = executionContext.getStringValue("account_number");
if (StringUtils.isBlank(accountNumber)) {
    throw new NovopayFatalException("132247");
}

// ❌ Overwriting shared keys accidentally
executionContext.put("account_number", childAccountNumber); // Overwrites parent's account_number
// ✅ Use a distinct key or putLocal
executionContext.put("child_account_number", childAccountNumber);
```

## Error Handling

```java
// ❌ Hardcoded error codes
throw new NovopayFatalException("132247", "Account not found");
// ✅ Use constants
throw new NovopayFatalException(AccountingConstants.ERROR_ACCOUNT_NOT_FOUND);

// ❌ Silent exception swallowing
catch (Exception e) { log.error("error", e); } // Flow continues with bad state
// ✅ Fail or rethrow
catch (Exception e) { log.error("error", e); throw new NovopayFatalException("ACCT-0001", e.getMessage()); }

// ❌ Using RuntimeException
throw new RuntimeException("Error");
// ✅ Use framework exceptions
throw new NovopayFatalException("ACCT-0001", "Error description");
```

## Database Queries

```java
// ❌ JPQL (poor YugabyteDB performance)
@Query("SELECT la FROM LoanAccountEntity la WHERE la.accountNumber = :num")
// ✅ Native query
@Query(nativeQuery = true, value = "SELECT * FROM loan_account WHERE account_number = :num AND is_deleted = false")

// ❌ Missing soft delete filter
@Query(nativeQuery = true, value = "SELECT * FROM loan_account WHERE account_number = :num")
// ✅ Always include is_deleted = false
@Query(nativeQuery = true, value = "SELECT * FROM loan_account WHERE account_number = :num AND is_deleted = false")

// ❌ N+1 in a loop
for (String acc : accounts) { repo.findByAccountNumber(acc); }
// ✅ Bulk query
repo.findByAccountNumberIn(accounts);

// ❌ Accessing Object[] by magic index
return (String) result[0]; // What is index 0? Breaks if query changes column order
// ✅ Use interface projection or named mapping
```

## Kafka Consumers

```java
// ❌ No idempotency check
public void consumeMessage(String message, String topic, String tenant) {
    // Processes every message, even duplicates
}
// ✅ Check status before processing
if ("ACTIVE".equals(account.getStatus())) {
    log.info("Already processed, skipping");
    return;
}

// ❌ Swallowing all exceptions
catch (Exception e) { log.error("Error", e); }
// ✅ Classify and handle
catch (CannotAcquireLockException e) { throw e; } // Retry
catch (NovopayFatalException e) { publishToFailureTopic(e); }
```

## API Contracts

```java
// ❌ Changing existing response semantics
// Was: charges_details always had at least one entry (placeholder)
// Changed to: charges_details is empty when no config
// → Breaks LOS KFS which assumes non-empty

// ✅ Additive only
response.put("charges_details", chargesList); // Keep existing behavior
response.put("charges_configured", hasRealCharges); // Add new flag

// ❌ Returning null for collection fields
return null; // Callers do .size() or .get(0) → NPE
// ✅ Return empty list
return Collections.emptyList();
```

## Financial Calculations

```java
// ❌ Using loan_amount (includes insurance) as base for net disbursement
BigDecimal net = loanAmount.subtract(charges);
// ✅ Use approved_amount
BigDecimal net = approvedAmount.subtract(charges);

// ❌ No validation of derived amounts
// net could be negative if charges > approved_amount
// ✅ Validate
if (net.compareTo(BigDecimal.ZERO) < 0) {
    throw new NovopayFatalException("ACCT-XXXX", "Negative net disbursement");
}

// ❌ Using double for money
double amount = 1234.56; // Precision loss
// ✅ Use BigDecimal
BigDecimal amount = new BigDecimal("1234.56");
```

## Processors

```java
// ❌ Fat processor doing everything
public class DoEverythingProcessor extends AbstractProcessor {
    // Validates, calls 3 services, updates DB, sends Kafka, formats response
}
// ✅ Focused processor — one responsibility
public class ValidateLoanAccountProcessor extends AbstractProcessor { ... }
public class CreateLoanAccountProcessor extends AbstractProcessor { ... }

// ❌ @Transactional in service methods
@Transactional
public void processLoan(...) { ... } // Orchestration owns transactions
// ✅ Let orchestration XML manage transactions
// Only use @Transactional(REQUIRES_NEW) when framework explicitly needs it
```