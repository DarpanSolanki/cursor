# `novopay-platform-authorization` — Roles, permissions, usecase-based access

> Manages role definitions, role hierarchy, role↔permission map, user↔role mapping. Validates whether a user can hit a given Request via the **usecase** model. The actual enforcement happens upstream at the API gateway via `AuthorizationCheckFilter`.

## Identity

| Field | Value |
|---|---|
| Java root package | `in.novopay.authorization` |
| DB schema | `mfi_authorization` |
| Repo | [`novopay-platform-authorization/`](../../novopay-platform-authorization/) |
| Service .cursorrules | [`trustt-platform-authorization/.cursorrules`](../../trustt-platform-authorization/.cursorrules) |

## API surface

`ServiceOrchestrationXML.xml` (~40 Requests, lines 4-40):

`createOrUpdateRole`, `getRoleDetailsByUserId`, `getRoleDetailsByUserIdList`, `getRoleList`, `getRoleHierarchy`, `checkPermissionByUsecase`, plus permission/usecase/epic/feature/userstory CRUDs.

## Kafka

None. Producer is configured but no-op. No consumers.

## Outbound HTTP

- actor (`getUserDetails`)
- approval (`submitApplication` for role-change maker-checker)

## Inbound — the gateway is the primary caller

[`AuthorizationCheckFilter.java`](../../trustt-platform-api-gateway/src/main/java/in/novopay/apigateway/filter/AuthorizationCheckFilter.java) calls `checkPermissionByUsecase` on every request to validate the user's role grants the usecase before forwarding.

## DB clusters

| Cluster | Tables |
|---|---|
| Roles | `role`, `role_hierarchy` (parent-child inheritance) |
| Permissions | `permission`, `role_permission_map` |
| Users | `user_role_mapping` (corporate-scoped) |
| UI catalogue | `epic`, `feature`, `userstory`, `usecase` (matches the front-end navigation tree) |
| Org | `role_department`, `category` |

## Concepts

- **Role** — named bundle of permissions, scoped to corporate.
- **Role hierarchy** — parent role's permissions inherited by children.
- **Permission** — atomic capability tied to a usecase.
- **Usecase** — a logical action (e.g. `LOAN-DISB-UC001`). Mapped to one or more API Requests via `api_usecase_mapping` in the **gateway** schema (`mfi_api_gateway`).
- **JWT/session** — *not* owned here. Session validation is at gateway; authorization is post-auth permission check only.

## Known gotchas

1. **Permission check is per-Request via usecase** — adding a new Request requires a `api_usecase_mapping` row (gateway schema) and a `usecase` + `permission` setup here.
2. **Role hierarchy is inheritance, not OR** — child role *gets* parent permissions; a permission removed from parent disappears from child too.
3. **No Kafka** — purely sync. Latency in this service slows every gateway request.
