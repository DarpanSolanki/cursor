---
description: "Auto-loads when editing novopay-platform-payments"
globs:
  - "**/novopay-platform-payments/**/*.java"
  - "**/novopay-platform-payments/**/*.xml"
alwaysApply: false
---

# Payments Module — Active Intelligence

## Critical context

- Collections, rails, and integrations that **allocate** and **sync** with LMS
- `bulk_collection_data_` pipeline: accounting → payments → downstream allocation / task topics (see `event-registry.md`)
- NEFT / disburse-related processors: align with `gaps-and-risks.md` and `system_brain/flows/` where applicable
- Payments is a **hub** for collection state; accounting and task consumers may depend on it

## Before any edit touching collection or allocation flow

1. Double-payment / double-allocate on retry?
2. Kafka poison messages: fail vs skip?
3. Contract alignment with accounting producers (`bulk_collection_data_*`, failed-record return path)

## After any edit

- Update `.cursor/event-registry.md` if topics or semantics change
- Append `.cursor/changelog.md`
