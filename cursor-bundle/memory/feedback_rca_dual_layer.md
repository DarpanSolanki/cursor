---
name: feedback_rca_dual_layer
description: "Dual RCA — Layer 1 QA RCA (internal, clear, first); Layer 2 Bank RCA (diplomatic, curated, TechOps→bank). Deploy/SQL only in Special notes + JIRA Pre/Post."
metadata:
  node_type: memory
  type: feedback
---

## Two layers (always both — in this order)

| Layer | Audience | Where | Voice |
|-------|----------|-------|-------|
| **1. QA RCA** | QA, dev, release internal | Release mail **§1**; JIRA **comment** on handoff | Clear functional cause — QA can retest without reading code |
| **2. Bank RCA** | TechOps → bank | Release mail **§2**; JIRA **`customfield_11137`** | Diplomatic institutional prose — forward as-is |

**Agent workflow:** Write **QA RCA first** (pinpoint truth in plain language), then **distill** Bank RCA (same facts, curated opacity + diplomacy). Never write Bank RCA before QA RCA.

**Special notes (§5 release / Pre-Post JIRA):** Release steps + SQL only — not in either RCA layer.

---

## Layer 1 — QA RCA (internal)

**Goal:** QA knows *what broke*, *why*, *what changed*, *what to verify* — without class names or file paths.

**Include (plain language OK):**

- Named **product flow** — e.g. death-foreclosure insurance batch, document re-upload path, task workflow update
- **Symptom** — stuck disposition (Pending for FR), partial state, batch chunk failure, service slowness during cycle
- **Cause** — functional chain: batch processing same records while workflow triggers a second update on those records → extended wait → timeout → rollback → retry leaves inconsistent disposition
- **Fix summary** — decouple batch-driven workflow from synchronous return path; separate commit steps; per-record failure isolation; eligibility widened for confirmed inbound with pending review; indexing for selection performance (one line — detail in Special notes)
- **QA retest hint** — which cycle to run, sample LAN, expected disposition after fix (no SQL in QA RCA — point to Pre/Post / Special notes)

**Still exclude:** Java class, apiName, processor, Redis/Kafka, Flyway version, full DDL, branch, commit SHA.

**Structure:** 3–4 short paragraphs OR symptom → cause → fix → retest. Clearer and **more concrete** than Bank RCA.

---

## Layer 2 — Bank RCA (diplomatic curation)

**Goal:** TechOps forwards to the bank **without editing**. Same underlying facts as QA RCA; **reframed**.

### Curation techniques (apply deliberately)

| Technique | Example |
|-----------|---------|
| **Nominalization** | “extended reconciliation latency” not “timeout after 3 minutes” |
| **Passive / systemic framing** | “processing duration was observed to exceed the permitted interval” |
| **Lifecycle / disposition language** | “pending-for-further-review disposition” not “claim_status column” |
| **Platform-neutral components** | “operational workflow orchestration” not “task service callback” |
| **Rare intersection** | “atypical pairing of document re-submission with an already-advanced closure milestone” |
| **Alignment not defect** | “processing sequencing refined”, “disposition rules extended”, “behaviour realigned” |
| **Shared accountability tone** | “concurrent reconciliation on the same case reference” — no “our batch bug” |
| **Controlled opacity** | enough structure to sound complete; avoid step-by-step mechanistic detail |
| **Forward-looking close** | recommend post-rollout observation of daily cycle — not “QA must retest LAN X” |

### Bank RCA must NOT contain

- Pre/Post scripts, DDL, Flyway, checksum, branch, repo names
- Batch job Java name, locks, callbacks, flags, indexes by name
- “Bug”, “gap”, “missed testing”, blame on QA or bank
- Deploy coordination list (→ Special notes)

**Structure:** Exactly **3 paragraphs** — (1) observable ops/business symptom, (2) cause in process language, (3) resolution outcome + monitoring recommendation.

---

## Release mail section order

1. **QA RCA**
2. **Bank RCA**
3. Impact analysis
4. Dev scenarios tested
5. Special notes (numbered release steps + SQL)

## JIRA mapping

| Content | JIRA destination |
|---------|------------------|
| Bank RCA | `customfield_11137` |
| QA RCA | **Comment** on ticket at handoff (`addCommentToJiraIssue`, markdown, heading `QA RCA (internal)`) |
| Pre/Post DDL summary | `customfield_11336` |
| Impact, Dev, MICRO, owners | existing fields |

If user forbids JIRA comment, paste QA RCA only in release mail §1.

## Checklist

- [ ] QA RCA written first — would QA know how to retest?
- [ ] Bank RCA is a **distillation**, not a copy-paste of QA RCA with adjectives
- [ ] Bank RCA readable aloud — TechOps comfortable sending to bank?
- [ ] Zero deploy/SQL in both RCA layers
- [ ] Special notes hold release steps

Skills: `.cursor/skills/jira-fix-update/SKILL.md`, `.cursor/skills/release-details/SKILL.md`, `.cursor/skills/fix-rca-email/SKILL.md`

Legacy alias: `feedback_rca_bank_forward_tone.md` → points here.
