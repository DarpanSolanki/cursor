---
description: "Auto-loads when editing batch service or batch-shaped Spring Batch artifacts"
globs:
  - "**/novopay-platform-batch/**/*.java"
  - "**/*BatchConfig*.java"
  - "**/*JobConfig*.java"
  - "**/*Tasklet*.java"
  - "**/*Writer*.java"
  - "**/*Reader*.java"
  - "**/*Processor*.java"
alwaysApply: false
---

# Batch Module — Active Intelligence

## Before any edit

1. Read `.cursor/multinode-batch.md` — scheduler vs Spring Batch multi-node distinction
2. Check `.cursor/scheduler-registry.md` — what runs and on what cadence
3. Check `gaps-and-risks.md` for batch / scheduler / writer rows

## Never forget these active themes (confirm in `gaps-and-risks.md`)

- Multi-instance **scheduler** safety: distributed leader/lock, dependency visibility
- **Time-based** `client_reference_number` → replay / double-post class of bugs
- Writers that **swallow** or **log-and-continue** on unexpected failures
- Integration test gap: many job beans, few end-to-end job tests (see `.cursor/test-coverage-map.md`)

## Mandatory checks before adding a new money-affecting batch job

1. Idempotency: safe on re-run? chunk restart?
2. `client_reference_number` (or equivalent): deterministic where posting dedupe relies on it?
3. Writer: fail-fast vs swallow — which is correct for this staging model?
4. Multi-instance: who must not run twice?
5. Cross-service calls: partial failure and compensation?

## After any batch / scheduler edit

- Update `.cursor/scheduler-registry.md` if `@Scheduled`, cron metadata, or new job surfaces
- Update `.cursor/multinode-batch.md` if multi-node / partition / manager-worker behaviour changes
- Append `.cursor/changelog.md`
