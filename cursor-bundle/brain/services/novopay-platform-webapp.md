# `novopay-platform-webapp` — Angular 20 admin SPA

> The operator-facing web UI. Single-project Angular 20 app with ~65 lazy-loaded feature modules. Talks to the backend exclusively through the API gateway. **Not a backend service** — included here because it owns several end-to-end UX flows that touch every backend service.

## Identity

| Field | Value |
|---|---|
| Framework | Angular **20.3.16** (per `package.json`; .cursorrules says 19 — package.json is authoritative) |
| Structure | Single project (not Nx/monorepo); all features under `src/app/` |
| Repo | [`novopay-platform-webapp/`](../../novopay-platform-webapp/) |
| Service .cursorrules | [`trustt-platform-webapp/.cursorrules`](../../trustt-platform-webapp/.cursorrules) |

## Top-level feature areas

Under [`src/app/`](../../novopay-platform-webapp/src/app/), grouped by domain:

| Domain | Modules (representative) |
|---|---|
| Loans | `loan-application`, `loan-disbursement`, `loan-repayment` (~20+ modules) |
| Product | `loan-product`, `savings-product` |
| Customer | `customer-onboarding`, `customer-360`, `group-360` |
| Finance / accounting | `accounting/finance` (GL, trial balance, JE) |
| Operations | `agent-management`, `organisation`, `geo-tracker`, `payment-reinitiation`, `allocations` |
| Collections | `collection-dashboard`, `credit-underwriting` |
| Dashboards | `dashboard`, `dashboards-and-reports` |

## Backend communication

- All HTTP via [`src/app/service-module/np-http/np-http.service.ts`](../../trustt-platform-webapp/src/app/service-module/np-http/np-http.service.ts) (`NpHttpService` wrapper).
- API endpoints in [`src/app/services/resource-factory.constants.ts`](../../trustt-platform-webapp/src/app/services/resource-factory.constants.ts).
- Three HTTP interceptors:
  - `WhitelistInterceptorService` — URL allow-list
  - `ErrorInterceptorService` — global error handling
  - `AddHttpHeaderInterceptorService` — session token, tenant
- Promise-based async (minimal `Observable`).
- Idle timeout: 15 min default via `IdleExpiryService`.

## State management

**No NgRx / Akita.** Custom lightweight `AppState` key-value store (service-based). Holds: tenant code, user ID, login response, permissions, business date, employee ID.

## Build / deploy

- Dev server: `ng serve` on port **4000**.
- Prod: `npm run build:prod` with base href `/portal/`.
- Bundle budget: 2 MB warn, 5 MB error.
- CommonJS allowed for `highcharts`, `moment`, `lodash`, `rxjs`.

## When you'll touch this

- A UX flow that "doesn't quite work" — start by tracing the `NpHttpService` call against the backend Request; cross-link to the relevant service brain doc.
- New module → register in lazy-route map, add to `AppState` if cross-cutting state is needed.
- Permission denied at UI vs. backend — UI uses `AppState.permissions`; backend uses gateway `checkPermissionByUsecase`. Check both.
