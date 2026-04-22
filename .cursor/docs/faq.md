# Frequently Asked Questions

## Q: How do I create a new API?
**A:** Follow the Service Orchestration Framework:
1. Create request template JSON in `deploy/application/templates/request/`
2. Create response template JSON in `deploy/application/templates/response/`
3. Define validators and processors in `ServiceOrchestrationXML.xml`
4. Create processor class extending `AbstractProcessor`
5. Create service methods if needed (with normal method parameters)
6. Add API configuration to `ServiceOrchestrationXML.xml`

## Q: How do I handle errors?
**A:** 
- Use `NovopayFatalException` for fatal errors that should stop processing
- Use `NovopayNonFatalException` for recoverable errors
- Always use error codes in format: `SERVICE-XXXX` (e.g., `LOS-5095`)
- Define error codes as constants, never hardcode
- Provide clear, actionable error messages

## Q: How do I pass data between processors?
**A:** 
- Within the same API call: Use `ExecutionContext.put()` and `getValue()`
- Between processors in same service: Use `ExecutionContext` (sharedMap)
- Between microservices: Use `putAPIResponse()` and `getAPIResponse()`

## Q: How do I pass data to service methods?
**A:** 
- Use normal method parameters (NOT ExecutionContext)
- Extract data from ExecutionContext in processor
- Pass extracted values as method parameters to service

## Q: How do I query by village?
**A:** 
- For tasks: Use EXISTS subquery with `task_extension` table
- For other entities: Join with village-related tables or use `vtc_id` field
- Always filter by `is_deleted = false`

Example:
```java
@Query("SELECT t FROM TaskEntity t WHERE EXISTS " +
       "(SELECT 1 FROM TaskExtensionEntity te WHERE te.taskId = t.id AND te.vtcId IN :villageIds) " +
       "AND t.isDeleted = false")
List<TaskEntity> findByVillageIds(@Param("villageIds") List<Long> villageIds);
```

## Q: How do I implement soft delete?
**A:**
- Add `is_deleted` boolean field to entity
- Set `is_deleted = true` instead of deleting
- Always filter by `is_deleted = false` in queries
- Use `@Where` annotation on entity class for automatic filtering (optional)

## Q: How do I add audit fields?
**A:**
- Extend base entity class (e.g., `AbstractIntegerBaseEntity`)
- Base entities include: `created_by`, `created_on`, `updated_by`, `updated_on`
- Set `performed_by` and `performed_on` in processors from ExecutionContext

## Q: How do I call another microservice API?
**A:**
- Use `PopulateUserDetails.callInternalAPI()` utility method
- Or use `ServiceGateway` for external service calls
- Store response using `putAPIResponse(apiIdentifier, responseMap)`
- Retrieve using `getAPIResponse(apiIdentifier)` or `getValueFromAPIResponse()`

**⚠️ IMPORTANT - Transaction Boundaries:**
- Each microservice API call operates in a **separate transaction boundary**
- If MS A calls MS B, MS B commits/rolls back **independently** of MS A
- Design for **partial failures**: if one service commits but another fails, the committed changes cannot be rolled back
- Consider **idempotency** and **compensating transactions** for complex multi-service operations
- See `Infra-Navigation-Library-Deep-Analysis.md` → **Transaction Management and Boundaries** for complete details

## Q: How do I write custom queries?
**A:**
- Use JPA repository methods (findBy, save, etc.) when possible for simple queries
- For custom queries, always use native queries (`nativeQuery = true`) for better YugabyteDB performance
- Avoid JPA @Query with JPQL - use native SQL queries instead
- Use `@Query` annotation with `nativeQuery = true` in repository interface
- Use `@Param` for named parameters
- Always include soft delete filter: `AND is_deleted = false`

## Q: How do I test processors?
**A:**
- Writing unit test cases is optional unless explicitly requested by the user (via command or in LLD/UD/TRD)
- When writing tests:
  - Mock `ExecutionContext` using Mockito
  - Mock service dependencies
  - Set up expected values in ExecutionContext
  - Verify `context.put()` calls for response
  - Test both success and failure scenarios