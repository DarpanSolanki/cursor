---
description: "No comments in persistence/repository layer — use knowledge docs or SQL"
globs: ["**/src/main/java/**/repository/**/*.java"]
alwaysApply: false
---

# Repository layer — no comments

When editing files under `**/repository/**` (Spring Data repositories, `*Repository.java`, `*DAOService.java` in that package):

- **Do not** add Javadoc on methods, block comments, or explanatory line comments. Names + `@Query` / SQL text are the documentation.
- Put performance, index usage, EXPLAIN notes, and schema rationale in **`.cursor/skills/accounting-knowledge/`** (accounting) or **comments in Flyway SQL** / workspace docs — not in Java repository classes.

Existing file-level headers that predate this rule are left as-is unless a change explicitly removes them.
