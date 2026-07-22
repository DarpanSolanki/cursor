<!-- Relocated verbatim from .cursor/rules/architect-thinking.mdc. Edit skill topics; thin architect-thinking.mdc only routes here. -->

# Backend Architecture, SOLID, and Testability

, SOLID, and Testability

## Clean Architecture (strict)
Structure code so dependencies point inward and each layer has one reason to change:

1. **API/Controller Layer**: HTTP/transport concerns only (request/response mapping, auth hooks, basic validation). No business logic.
2. **Orchestration/Processor Layer**: Flow control + mandatory orchestration wiring (ExecutionContext key validation, branching decisions, calling services). Keep it lean; delegate core rules to services/domain.
3. **Service Layer (Business)**: Core business logic + workflow orchestration that is meaningful at the domain level. Keep transactions/commit semantics aligned with the orchestration XML (avoid adding `@Transactional` in services unless explicitly required).
4. **Domain Layer (Pure)**: Pure models/rules with no Spring annotations, no IO, no DB calls, no external API calls.
5. **Repository/Data Access**: Only DB interactions. No business logic and no financial rule calculations.

Rule of thumb: if a class needs to change when business rules change, it belongs in `Service`/`Domain` (not controller/processor/repository).

## SOLID (enforced by design)
- **Single Responsibility**: one class = one reason to change.
- **Open/Closed**: extend behavior via new classes/implementations; avoid modifying stable, widely-used code.
- **Liskov Substitution**: subtypes must not weaken invariants.
- **Interface Segregation**: define small, focused interfaces (especially for external systems).
- **Dependency Inversion**: depend on abstractions (interfaces) instead of concrete implementations.

## Testability (non-negotiable)
- Prefer constructor injection (no static dependencies for collaborators).
- Keep business rules in small, deterministic methods that can be unit tested without DB/network.
- When an external system is involved (bank/payment/3rd-party API), isolate it behind an interface so it can be mocked in unit tests.
- Unit tests should not require real DB connections; use mocks/fakes for repositories and external APIs.

## Size constraints (keep code reviewable)
- Prefer methods under ~30 lines.
- Avoid large "god classes"; use composition so responsibilities stay cohesive.
- If a class grows beyond ~300 lines, treat it as a smell and split by responsibility.

## Error handling and idempotency (safety-first)
- Fail fast with domain-specific exceptions; do not swallow exceptions.
- For write operations, ensure idempotency via existing status checks / dedupe patterns (especially for orchestration replays and Kafka at-least-once delivery).

---

