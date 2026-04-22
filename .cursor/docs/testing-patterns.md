# Testing Patterns

**Note**: Writing tests is optional unless explicitly requested by the user or in LLD/UD/TRD.

## Unit Testing Processors

```java
@ExtendWith(MockitoExtension.class)
class ValidateLoanAccountDetailsProcessorTest {

    @Mock
    private LoanAccountDAOService loanAccountDAOService;
    @Mock
    private ExecutionContext executionContext;
    @InjectMocks
    private ValidateLoanAccountDetailsProcessor processor;

    @Test
    void shouldSetAccountEntityWhenFound() {
        when(executionContext.getStringValue("account_number")).thenReturn("LA0001");
        var account = new LoanAccountEntity();
        account.setId(1L);
        when(loanAccountDAOService.findByAccountNumber("LA0001")).thenReturn(account);

        processor.process(executionContext);

        verify(executionContext).put("account_id", 1L);
        verify(executionContext).put("loan_account_entity", account);
    }

    @Test
    void shouldThrowWhenAccountNumberBlank() {
        when(executionContext.getStringValue("account_number")).thenReturn("");

        assertThrows(NovopayFatalException.class, () -> processor.process(executionContext));
    }

    @Test
    void shouldThrowWhenAccountNotFound() {
        when(executionContext.getStringValue("account_number")).thenReturn("LA9999");
        when(loanAccountDAOService.findByAccountNumber("LA9999")).thenReturn(null);

        assertThrows(NovopayFatalException.class, () -> processor.process(executionContext));
    }
}
```

## Unit Testing Services

```java
@ExtendWith(MockitoExtension.class)
class LoanAccountServiceTest {

    @Mock
    private LoanAccountDAOService daoService;
    @InjectMocks
    private LoanAccountService service;

    @Test
    void shouldReturnActiveAccount() {
        var account = new LoanAccountEntity();
        account.setStatus("ACTIVE");
        when(daoService.findByAccountNumber("LA0001")).thenReturn(account);

        var result = service.findActiveAccount("LA0001");

        assertEquals("ACTIVE", result.getStatus());
    }

    @Test
    void shouldThrowWhenAccountNotActive() {
        var account = new LoanAccountEntity();
        account.setStatus("CLOSED");
        when(daoService.findByAccountNumber("LA0001")).thenReturn(account);

        assertThrows(NovopayFatalException.class, () -> service.findActiveAccount("LA0001"));
    }
}
```

## Testing Kafka Consumers

```java
@ExtendWith(MockitoExtension.class)
class LmsMessageBrokerConsumerTest {

    @Mock
    private ServiceOrchestrator serviceOrchestrator;
    @Mock
    private RedisTemplate<String, String> redisTemplate;
    @InjectMocks
    private LmsMessageBrokerConsumer consumer;

    @Test
    void shouldSkipWhenCacheKeyExists() {
        when(redisTemplate.hasKey("disbursement:EXT001")).thenReturn(true);

        consumer.consumeMessage("disburse|{...}|disbursement:EXT001", "topic", "tenant1");

        verifyNoInteractions(serviceOrchestrator);
    }

    @Test
    void shouldRethrowLockException() {
        // CannotAcquireLockException should propagate for Kafka retry
        assertThrows(CannotAcquireLockException.class, () -> { ... });
    }
}
```

## Testing Financial Calculations

```java
@Test
void shouldCalculateCorrectNetDisbursement() {
    BigDecimal approved = new BigDecimal("50000.00");
    BigDecimal charges = new BigDecimal("500.00");
    BigDecimal tax = new BigDecimal("90.00");

    BigDecimal net = approved.subtract(charges).subtract(tax);

    assertEquals(new BigDecimal("49410.00"), net);
    assertTrue(net.compareTo(BigDecimal.ZERO) > 0);
}

@Test
void shouldRejectNegativeNetDisbursement() {
    BigDecimal approved = new BigDecimal("50000.00");
    BigDecimal charges = new BigDecimal("50001.00"); // Charges exceed approved

    BigDecimal net = approved.subtract(charges);

    assertTrue(net.compareTo(BigDecimal.ZERO) < 0, "Should detect negative net disbursement");
}
```

## What to test

| Layer | Test | Mock |
|-------|------|------|
| Processor | Extract → validate → call service → set context | ExecutionContext, Services |
| Service | Business logic, error paths | DAOService, Repository |
| Consumer | Idempotency, error handling, retry vs swallow | Redis, Orchestrator |
| Repository | Only for complex native queries (integration test) | Real DB or H2 |
| Financial | Every formula, edge cases (zero, negative, max) | None (pure logic) |