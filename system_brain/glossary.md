# Glossary

- **ORC**: Orchestration XML-driven flow executed by `ServiceOrchestrator` (infra-navigation).
- **ExecutionContext**: Stringly-typed, mutable contract shared across processors in a request flow.
- **postTransaction**: Accounting-v2 core ledger write orchestration request that persists ledger artifacts.
- **GL / internal accounts**: Master ledger definitions (`general_ledger`, `internal_account_definition`, `internal_account`) used by the transaction rule engine.
- **CRR**: Client request/response log (`client_request_response_log`) used for bank call idempotency and lifecycle tracking.
- **Kafka contract**: The payload fields (and message format) that downstream consumers treat as mandatory keys.
- **Redis lock/in-flight marker**: A cache entry used to avoid duplicate processing for at-least-once delivery.

