---
description: "Auto-loads when editing any file in novopay-platform-lib"
globs:
  - "**/novopay-platform-lib/**/*.java"
  - "**/novopay-platform-lib/**/*.xml"
alwaysApply: false
---

# Platform-Lib — Active Intelligence

## This is the framework. Every change here affects all dependent services.

Never make a change here without understanding blast radius. See `.cursor/platform-lib.md`, `.cursor/service-dependency-graph.md`, and `.cursor/service-contracts.md`.

## Before any edit

1. Read `.cursor/platform-lib.md` — what this module/class does
2. Check `.cursor/service-dependency-graph.md` — which services route through this?
3. Check `.cursor/service-contracts.md` — contract / HTTP / Kafka impact?
4. Check `.cursor/gaps-and-risks.md` — active gap on this path?

## Global injections you must not break casually

- `ServiceGatewayController` — HTTP entry pattern for SOF services
- `RequestProcessorImpl` — request dispatch into orchestration
- `ServiceOrchestrator` / `ProcessorOrchestrator` — processor chain and txn boundaries
- `NovopayApiClientConfig` / `NovopayHttpAPIClient` — pooled HTTP client behaviour
- `NovopayCacheConfiguration` — Redis factory layout per DB index
- `ElasticApmTransactionNameFilter` (and related APM filters) — tracing names

Breaking behaviour in these beans can surface as **cross-service** incidents.

## After any edit

- Update `.cursor/platform-lib.md`
- Update `.cursor/service-contracts.md` if contract or defaults change
- Grep / assess impact: which services embed this module or copy patterns?
- Append `.cursor/changelog.md` with: `PLATFORM-LIB CHANGE: [what] | Impact: [services/modules]`
