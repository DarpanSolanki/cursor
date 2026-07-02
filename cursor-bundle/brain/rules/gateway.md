---
description: "Auto-loads when editing novopay-platform-api-gateway"
globs:
  - "**/novopay-platform-api-gateway/**/*.java"
  - "**/novopay-platform-api-gateway/**/*.xml"
alwaysApply: false
---

# API Gateway — Active Intelligence

## Single ingress for most external traffic

Mistakes here can cause **outage**, **auth bypass**, or **data leakage**. Cross-check `gaps-and-risks.md` and `system_brain/edge_cases/api-gateway-edge-cases.md`.

## Active gaps to treat as hot (IDs in `gaps-and-risks.md`)

- **GAP-054:** permission path when `api_usecase_mapping` row missing — permission call skipped; treat as **fail-open** ingress risk; any fix must be tested for deny/allow semantics
- **GAP-055:** `/forward/*` trust boundary and logging — filter bypass class of issues
- **GAP-059 / GAP-060:** lack of automated tests on `AuthorizationCheckFilter` and `RequestForward*` paths

## Before any edit to auth, filters, session, or forward

1. Does this change permission check or mapping resolution?
2. Does this change `/forward/*` or forward URL cache (`redis-key-registry.md`)?
3. Add or extend tests where gaps exist

## After any edit

- Append `.cursor/changelog.md` with **security / ingress** impact note when behaviour changes
- Update `gaps-and-risks.md` if a documented gap is resolved or a new one is introduced
