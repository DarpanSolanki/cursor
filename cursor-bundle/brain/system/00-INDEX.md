# System brain — cross-service map

> If your question crosses two or more services, start here. If it lives in one service, go to [`../services/<service>.md`](../services/).

## Read in this order

1. [`01-system-overview.md`](01-system-overview.md) — what Trustt LMS is, who uses it, the 17 services, the broad architecture
2. [`02-service-map.md`](02-service-map.md) — single-page table: every service, its role, its DB, its Java package, its dependencies
3. [`03-end-to-end-flows.md`](03-end-to-end-flows.md) — the major user journeys mapped to the services they touch (cross-link to [`../flows/`](../flows/))
4. [`04-money-flow-rupee-journey.md`](04-money-flow-rupee-journey.md) — track a single rupee from disbursement bank → repayment back to bank → GL closure
5. [`05-integration-topology.md`](05-integration-topology.md) — every HTTP and Kafka edge in one picture; tells you "who talks to whom and how"
6. [`06-data-architecture.md`](06-data-architecture.md) — every DB schema across services with cross-service logical FKs
7. [`07-batch-atlas.md`](07-batch-atlas.md) — every scheduled batch job in the platform with trigger / output / dependencies
8. [`08-kafka-topology.md`](08-kafka-topology.md) — every Kafka topic with producer/consumer/schema
9. [`09-shared-platform-lib.md`](09-shared-platform-lib.md) — the lib's role + key interfaces every service uses
10. [`10-environments-config.md`](10-environments-config.md) — tenant model, multinode batch, config drift, redis DB indexes
11. [`11-glossary.md`](11-glossary.md) — definitive cross-service vocabulary

## How this folder relates to the rest

| Folder | What it answers |
|---|---|
| `../accounting/` | LMS deep-dive (the heart of the system) |
| `../services/` | One-service mental model |
| `../flows/` | Cross-service journey narratives (built on top of this folder + services) |
| `../runbooks/` | Production debugging playbooks |
| `../platform/` | Older but still authoritative indexes (orchestration map, event registry, etc.) |
| `../engines/` | Older deep narratives on disbursement / repayment / posting |
| `../docs/` | Glossary, FAQ, patterns, anti-patterns, testing patterns |
| `../gaps-and-risks.md` | Known issues with file:line evidence (read for High items before any change) |

## Sources

Every file in this folder is grounded in the same code reads as the rest of the bundle: branch `mfi_integration_v3.2.8.4.1`, all 17 darpan checkouts. Where a doc cites a service-specific file, the path is relative to the darpan root (e.g. `../../novopay-mfi-los/...`).
