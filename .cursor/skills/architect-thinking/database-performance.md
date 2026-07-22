<!-- Relocated verbatim from .cursor/rules/architect-thinking.mdc. Edit skill topics; thin architect-thinking.mdc only routes here. -->

# Database performance (YugabyteDB)

(YugabyteDB)

## Always native queries

```java
// Correct: native SQL
@Query(nativeQuery = true, value = "SELECT * FROM loan_account WHERE account_number = :accountNumber AND is_deleted = false")
LoanAccountEntity findByAccountNumber(@Param("accountNumber") String accountNumber);

// Wrong: JPQL — poor performance on YugabyteDB
@Query("SELECT la FROM LoanAccountEntity la WHERE la.accountNumber = :accountNumber AND la.isDeleted = false")
```

Why: YugabyteDB's query planner works best with native SQL. JPQL adds a translation layer that can produce suboptimal plans.

## N+1 prevention

```java
// Wrong: N+1 loop
for (String accountNumber : accountNumbers) {
    LoanAccountEntity account = repo.findByAccountNumber(accountNumber); // 1 query per item
}

// Correct: bulk query
@Query(nativeQuery = true, value = "SELECT * FROM loan_account WHERE account_number = ANY(CAST(:accounts AS text[])) AND is_deleted = false")
List<LoanAccountEntity> findByAccountNumbers(@Param("accounts") String[] accounts);

// Or for List params:
@Query(nativeQuery = true, value = "SELECT * FROM loan_account WHERE account_number IN (:accounts) AND is_deleted = false")
List<LoanAccountEntity> findByAccountNumberIn(@Param("accounts") List<String> accounts);
```

Why: In fintech, batch jobs process thousands of accounts. N+1 turns a 50ms batch into a 50-second one.

## Bulk writes

```java
// Use saveAll for batch inserts
repository.saveAll(entities); // Single round-trip for all

// For bulk updates, use native query
@Modifying
@Query(nativeQuery = true, value = "UPDATE loan_account SET office_id = :officeId, updated_by = :updatedBy, updated_on = :updatedOn WHERE account_id IN (:accountIds)")
void updateOfficeByAccountIds(@Param("accountIds") List<Long> accountIds, @Param("officeId") Long officeId, ...);
```

## Soft delete everywhere

Every query MUST include `is_deleted = false` unless explicitly querying deleted records for audit.

```java
// Every SELECT
WHERE ... AND is_deleted = false

// Soft delete (never physical DELETE)
UPDATE table SET is_deleted = true, updated_on = now(), updated_by = :user WHERE id = :id
```

## Pagination for list queries

```java
// Native query with pagination
@Query(nativeQuery = true, value = "SELECT * FROM loan_account WHERE office_id = :officeId AND is_deleted = false ORDER BY created_on DESC LIMIT :limit OFFSET :offset")
List<LoanAccountEntity> findByOffice(@Param("officeId") Long officeId, @Param("limit") int limit, @Param("offset") int offset);
```

## Index awareness

Before writing a WHERE clause, consider:
- Is there an index on the filtered column?
- For composite conditions, is there a composite index?
- For ORDER BY, does the index support the sort?
- For JOINs, are foreign keys indexed?

## Projections for read-only queries

When you don't need the full entity, use interface projections or `Object[]` mapping to reduce data transfer:

```java
@Query(nativeQuery = true, value = "SELECT account_number, account_id, status FROM loan_account WHERE office_id = :officeId AND is_deleted = false")
List<Object[]> findAccountSummaryByOffice(@Param("officeId") Long officeId);
```

Architect tip: Interface projections (e.g. `LoanAccountSummaryProjection`) are cleaner than `Object[]` indexing. Prefer named projections for readability.

---

