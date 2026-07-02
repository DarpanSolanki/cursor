# Workspace state — analysis-ready

**Last refreshed:** 2026-06-10.

## Branch snapshot

> **Live authority = `claude/kg/bin/kg watermark`** (per-repo `branch@sha`, auto-stamped into `kg/data/stats.json` on every `build.sh`) — it also flags feature/WIP branches and drift. The table below is **point-in-time**; if it disagrees with `kg watermark` or the snapshot command, **the live state wins.** Run one of these at session start — do not assume "all 17 on 3.2.8.4.1":

```bash
claude/kg/bin/kg watermark   # branch@sha the KG knowledge reflects vs live HEAD (+ WIP/drift flags)
# or raw live:
for d in /home/darpan/darpan/novopay-* /home/darpan/darpan/trustt-*; do [ -d "$d/.git" ] && printf "%-42s %s\n" "$(basename "$d")" "$(git -C "$d" rev-parse --abbrev-ref HEAD)"; done
```

| Repo | Branch (2026-06-10) | Notes |
|---|---|---|
| `novopay-mfi-los` | **`feature/neft-v2-payment-reinit-qa`** | ⚠ WIP feature branch — knowledge PROVISIONAL |
| `novopay-platform-accounting-v2` | **`feature/delayed_payment_interest`** | ⚠ WIP — DPIC v1 work; not the release train |
| `novopay-platform-actor` | `mfi_integration_v3.3.1.1` | release train (drifted up) |
| `novopay-platform-api-gateway` | `mfi_integration_v3.2.8.4.1` | release train |
| `novopay-platform-approval` | `mfi_integration_v3.2.8.4.1` | release train |
| `novopay-platform-audit` | `mfi_integration_v3.2.8.4.1` | release train |
| `novopay-platform-authorization` | **`feature/authz-reference-cache`** | ⚠ WIP feature branch — PROVISIONAL |
| `novopay-platform-batch` | `mfi_integration_v3.3.1.0.0` | release train |
| `novopay-platform-dms` | `mfi_integration_v3.2.8.4.1` | release train |
| `novopay-platform-initial-setup` | **`feature/delayed_payment_interest`** | ⚠ WIP — DPIC v1 |
| `novopay-platform-lib` | **`feature/authz-reference-cache`** | ⚠ WIP feature branch — PROVISIONAL |
| `novopay-platform-masterdata-management` | `mfi_integration_v3.3.1.0.0` | release train |
| `novopay-platform-notifications` | `mfi_integration_v3.3.1.0.0` | release train |
| `novopay-platform-payments` | `mfi_integration_v3.3.1.0.0` | release train |
| `novopay-platform-task` | `mfi_integration_v3.3.1.0.0` | release train (dirty working tree) |
| `novopay-platform-webapp` | **`sli_dpic`** | ⚠ WIP feature branch — PROVISIONAL |
| `trustt-platform-reporting` | `mfi_integration_v3.2.8.4.1` | release train |

**Spread (2026-06-10):** 6 repos on `mfi_integration_v3.2.8.4.1`, 5 on `v3.3.1.0.0`, 1 on `v3.3.1.1`, and **6 on feature/WIP branches** (`los`, `accounting-v2`, `authorization`, `initial-setup`, `lib`, `webapp`). Cross-service code searches must factor the mixed branches; **flows touching the WIP repos reflect in-development code — apply the WIP-vs-stable gate (`feedback_keep_knowledge_current`) before trusting/citing them.** Always confirm the branch the **affected environment** runs before fixing.

## Code reference paths

For all analysis going forward, **read directly from the `/home/darpan/darpan/` checkouts** (do not read from `/home/aitdp/workspace/Trustt_*/...` — those are older snapshots).

| Service | Path |
|---|---|
| LOS | `/home/darpan/darpan/novopay-mfi-los/` |
| Accounting (LMS) | `/home/darpan/darpan/novopay-platform-accounting-v2/` |
| Actor | `/home/darpan/darpan/novopay-platform-actor/` |
| API Gateway | `/home/darpan/darpan/novopay-platform-api-gateway/` |
| Approval | `/home/darpan/darpan/novopay-platform-approval/` |
| Audit | `/home/darpan/darpan/novopay-platform-audit/` |
| Authorization | `/home/darpan/darpan/novopay-platform-authorization/` |
| Batch | `/home/darpan/darpan/novopay-platform-batch/` |
| DMS | `/home/darpan/darpan/novopay-platform-dms/` |
| Initial Setup | `/home/darpan/darpan/novopay-platform-initial-setup/` |
| Platform Lib (infra) | `/home/darpan/darpan/novopay-platform-lib/` |
| Master Data | `/home/darpan/darpan/novopay-platform-masterdata-management/` |
| Notifications | `/home/darpan/darpan/novopay-platform-notifications/` |
| Payments (LCS) | `/home/darpan/darpan/novopay-platform-payments/` |
| Task | `/home/darpan/darpan/novopay-platform-task/` |
| Webapp (Angular) | `/home/darpan/darpan/novopay-platform-webapp/` |
| Reporting | `/home/darpan/darpan/trustt-platform-reporting/` |

## Quick start for a new analysis session

```bash
# 1. Confirm branch + SHA + dirty state across all 17 repos
for d in /home/darpan/darpan/*/; do [ -d "$d/.git" ] && printf "%-42s %-32s %s dirty=%s\n" \
  "$(basename "$d")" \
  "$(git -C "$d" rev-parse --abbrev-ref HEAD)" \
  "$(git -C "$d" rev-parse --short=10 HEAD)" \
  "$(git -C "$d" status --porcelain | wc -l)"; done

# 2. Read claude/ brain docs FIRST (per feedback_brain_first_then_code memory)
#    Don't grep service code until the brain doc is silent on what you need.
$EDITOR /home/darpan/darpan/claude/README.md
$EDITOR /home/darpan/darpan/claude/onboarding.md
$EDITOR /home/darpan/darpan/claude/accounting/INDEX.md      # accounting work
$EDITOR /home/darpan/darpan/claude/engines/disbursement-engine.md  # disbursement / NEFT v2

# 3. Cross-service grep when brain doc references a symbol you need to inspect:
grep -rn "<symbol>" /home/darpan/darpan/novopay-platform-*/src/main/java
```

## Known caveats

- The 4 repos on `3.3.1.0.0` and `initial-setup` on `feature/dpic-v1` are NOT race-fix-eligible by the work on `3.2.8.4.1`. Don't assume a fix landed in accounting on `3.2.8.4.1` exists in payments/masterdata/notifications/batch — those branches diverge.
- **Boundary rule active** — no writes outside `/home/darpan/darpan/`, no shared-KG mutations. KG / KB scoped to darpan content only (and currently the KG has only QDE projects — useless for accounting work; brain docs are the substrate).
- The `claude/changelog/` is now a single `CHANGELOG.md` (no per-entry files). Detail goes to `git show <sha>`.
