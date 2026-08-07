# Feature-Development Playbook — UD → implemented feature

> The green-field counterpart to the bug-fix rails (`rca-workflow` / `qa-handoff`). This is the **substrate** the `ud-to-feature` skill drives. It answers: *given a Product UD, how does a new capability physically attach to the novopay-platform framework, and what is the repeatable path from spec → verified design → code → QA?*
>
> Authoritative worked example throughout: **DPI v1 (Delayed Payment Interest)** — [UD](../../UDs/) → [claude/dpic/](../dpic/). Every anatomy step below cites where DPI did exactly that. Framework internals: [rules/novopay-framework-awareness.md](../rules/novopay-framework-awareness.md). Tiering: [rules/tiered-solution-approach.md](../rules/tiered-solution-approach.md).

---

## 0. What "implement from the UD only" actually means

You can reach a **fully verified scope + design + impact map + implementation plan + QA scenarios** from `UD + KG + brain docs` *without opening service code*. The code-writing step then drops to the checkouts (precedence-ladder rung 6) — that is by design. So "UD only" = everything up to the diff is brain/KG-driven; the diff itself is code-anchored and verified against the checkout.

Never skip the verification gate (.cursorrules Rule 5): built green ≠ done; status stays "pushed; awaiting QA retest."

---

## 1. Ingest the UD → a behavioural-rules table (the lock)

A UD is prose + sample-calc sheets. Convert it into an **enumerated, numbered behavioural-rules table** keyed to the UD section, before any design. This is the single source the rest of the work is checked against (enumerate-before-summarize, .cursorrules Rule 7b).

DPI did this — see [dpic/00-overview.md](../dpic/00-overview.md) "Key behavioural rules (locked from UD + sample-calc)": each rule traced to `UD §5.2 / §5.5` and to the sample-calc xlsx. Extract, per rule:

- **Trigger** — when does it fire (event, batch, lifecycle stage)?
- **Formula / decision** — exact arithmetic or branch, reconciled against the sample-calc sheet (the sheet is ground truth where prose is ambiguous).
- **Ordering** — where it sits in an existing sequence (DPI: appropriation position 3, after Interest, before Penalty).
- **Negative space** — what it must NOT do (DPI: never compounds on itself; accrual/billing rows stay `is_reversible=false`).
- **Config surface** — what is parameterised vs hard-coded (DPI: rate/grace/days-in-year at Product Scheme level).

Anything the UD leaves open → an **open-question** with an owner (see §6). Do not guess past it.

---

## 2. Scope against the KG — what exists vs what's new

Before designing, map the feature onto the live system using the **system-kg** skill. This is the "UD only" superpower — you discover the attachment points without grepping:

```
kg search <domain-term>                # find the flows/processors/tables already in this area
kg flow <nearestExistingRequest>       # the processor spine you'll extend (e.g. repayment appropriation)
kg crud <nearestExistingRequest>       # its read-set/write-set — the tables your feature perturbs
kg writes <table>                      # reverse blast radius: who else writes a table you'll touch
kg impact <processor|table> --depth 3  # everything that reaches the node you're about to change
kg cases <flow>  /  kg error <code>    # has anything been fixed here before? (precedent)
kg docs <node>                         # which brain docs already cover this surface
```

Produce a **gap analysis**: for each behavioural rule from §1, is the attachment point (a) reuse-as-is, (b) extend an existing processor/table, or (c) genuinely new? DPI's overview "What's done" table is exactly this gap analysis materialised.

---

## 3. Anatomy of a new feature — the placement matrix

A new capability in this platform attaches at a fixed set of layers. Walk them in order; for each, decide *reuse / extend / new*. (Columns: layer → where it lives → DPI evidence.)

| # | Layer | Where it lives | DPI did exactly this |
|---|---|---|---|
| 1 | **Data model** | new `@Entity` + `@Table` under the service's `entity/`; column added to an existing table | DPI added `loan_due_details.component_type = "DPI"`; new constant `AssetsConstants.DPI` |
| 2 | **Schema migration** | Flyway `Vxxxx__*.sql` in `novopay-platform-initial-setup` (and product-level seeds) | `V9000758__add_dpi_code_master_seed.sql` — code-master rows, appropriation-logic seed @pos3, go-live-date masters |
| 3 | **Constants** | `AccountingConstants` / `AssetsConstants` (string keys are stringly-typed — typos fail at runtime, verify against XML) | `DPI_APBL_*`, `DPI_GO_LIVE_DATE_*`, `DPI_AMOUNT`, `PRODUCT_SCHEME_DPI_APPLICABLE` |
| 4 | **DAO / Repository** | `*DAOService` + repository; read-set/write-set must match what `kg crud` predicted | reads overdue base via `LoanDueDetailsDAOService.getDueDetailsByOverDueDate(...)` for `[PRINCIPAL, INTEREST]` only |
| 5 | **Service (business logic)** | a focused service class; reuse existing util math where possible | `DPICalculationService.calculate(...)` reusing `InterestCalculationUtil.computeInterest(...)`; `DpiSchemeConfigResolver` (swappable stub) |
| 6 | **Processor(s)** | `.../processor/`; one responsibility each; **wired into orchestration XML** `<Request>` | DPI accrual/booking/billing processors wired in `loans_orc.xml:2450/2465/2480` |
| 7 | **Orchestration wiring** | `deploy/application/orchestration/*_orc.xml` — Validators → Processors → API → Controls; `<Control regExp ${function_sub_code}>` for branching; `maker_checker_enabled` for approval path | new `<Request>` blocks + processor ordering |
| 8 | **Batch (if async/periodic)** | Reader / ItemProcessor / Writer / BatchService quad — **plus the activation wiring (easy to drop, fails silently):** `BatchConfigService.buildJobForTenant()` with `group_code`+`cron` in setup params, **wire it into the right `*JobLoader`**, add a `BatchJobPlaceholderConfig` stub bean, add an `api_master` row. See **[system-activation-and-wiring §1-2](../platform/system-activation-and-wiring.md)** + `batch-atlas-lookup`. | `dpiAccrualCalculation → dpiAccrualBooking → dpiBilling` — **initially MISSED the loader wiring + placeholder beans → coded but never registered/ran** (fixed `91a5b7536`); api_master `V000450` |
| 9 | **GL / appropriation / posting** | `transaction_accounting_rule`, `placeholder_master`, appropriation map; use `posting-rule-resolver` | DPI accumulator + `APP_LOGIC_DPI` appropriation entry; DPI bucket in `LIQ_INSTL_CHRG_COMP` |
| 10 | **Reversal + lifecycle** | reversal mapping `(transaction_type, transaction_sub_type)`; Part-Prepayment / Foreclosure / Restructure / Auto-Closure previews | reversal `dpi_amount`; foreclosure force-bill hook `MarkUnbilledDpiAsBilledOnForeclosureProcessor`; remaining lifecycle handlers deferred |
| 11 | **Surfacing** | Loan-360 / API response processors | `GetDpiAccrualDetailsProcessor` |
| 12 | **Events (if cross-service)** | Kafka topic + consumer; [event-registry](../platform/event-registry.md) | n/a for DPI (in-service batch) |

Not every feature touches all 12 — the placement matrix is a checklist so nothing is silently dropped (.cursorrules Rule 7b/c). Cross-service features additionally need `kg deps <service>` and [platform/service-contracts.md](../platform/service-contracts.md).

> **Layer 0 — Activation / wiring (the silent layer that the matrix above does NOT capture by itself).** Correct business code + green build + a `<Request>` + an `api_master` row does **not** mean the feature runs. This platform activates features through **dynamic runtime bean registration + DB-seed rows + orchestration-XML opt-in**, and **most activation misses fail SILENTLY** (no-op / null / fail-open). Before calling any feature done, walk the **[system-activation-and-wiring](../platform/system-activation-and-wiring.md) checklist**: batch → `*JobLoader` wiring + `BatchJobPlaceholderConfig` bean; `api_master` (else `13022`); processor beans by name (else `220000`); Kafka `<Consumer>` + matching bean; cache `@CacheEvict` on **every** write path; tenant propagation on new threads; Flyway right **module + band**; secured API → `api_usecase_mapping` (else the gateway **fails OPEN**); and the `<Audits>` / notification-template / `product_document_master` / `code_master` / `@NovopayConfig` opt-ins. **This is the layer the DPIC EOD jobs fell through** (coded, never wired into `LoanSystemDailyJobLoader` → never registered → never ran).

---

## 4. Design in tiers, respect the safety rails

Apply [tiered-solution-approach.md](../rules/tiered-solution-approach.md): a feature is normally **L2 (schema/config change)** or **L3 (cross-module / new contract)** — present the increment honestly, including the schema-migration and config-deploy cost.

Mandatory rail checks **before** finalising the design (these are the same rails that catch bugs):
- [rules/no-flow-break-impact-check.md](../rules/no-flow-break-impact-check.md) — does inserting a processor / reordering break an existing flow? Cross-check with `kg impact`.
- [rules/multi-path-state-persistence-safety.md](../rules/multi-path-state-persistence-safety.md) + `state-machine-safety` — if the feature writes a multi-writer state column (`disbursement_status`, `loan_status`, event-queue JSON), it must go through CAS; **no in-memory entity mutation after CAS** (.cursorrules Rule 3).
- [rules/api-contract-safety.md](../rules/api-contract-safety.md) — new/changed API contract back-compat.
- [gaps-and-risks.md](../gaps-and-risks.md) — read High items in the touched area before adding to it.

Output of this stage: a **design doc** (the new `dpic/`-equivalent folder) listing, per behavioural rule, the exact layers from §3 it lands in, with file targets named from the KG (`kg flow`/`kg crud` provenance) — still no code opened.

---

## 5. Implement, build, verify

Only now drop to the checkouts (ladder rung 6). For each layer in the placement matrix, write the code matching surrounding style (`feedback_keep_code_simple`; `rules/repository-layer-no-comments.md`). Then:

- Build green: `cd <repo> && ./gradlew build -x test` (Java 17). After first build / `build.gradle` change: `./gradlew eclipse` for IDE classpath.
- **Diff-before-claim** for any state/posting change: paste expected-vs-actual DB-state delta, not just "built green."
- Authorship + changelog + push per .cursorrules Rule 4 (DarpanSolanki, `github-darpan` alias, prepend CHANGELOG in same turn).

---

## 6. Open questions & product hand-off

A UD always has gaps. Track them like DPI did — [dpic/05-open-questions.md](../dpic/05-open-questions.md): a live Q-list with owner + status, and [dpic/03-product-handoff-sheet-corrections.md](../dpic/03-product-handoff-sheet-corrections.md) for sample-calc discrepancies you found. Jira/mail are **external writes (forbidden)** — draft the question block in-boundary and hand it to the user to send.

---

## 7. QA hand-off & keep-knowledge-current

- Run **`qa-handoff`**: functional RCA-equivalent (here: feature behaviour spec) + impact analysis + **simulated scenarios (expected vs actual)** per behavioural rule, drafted for the user to paste.
- **Fold the feature into the brain in the same turn** (`feedback_keep_knowledge_current`): a new `claude/<feature>/` folder (overview / impl-spec / flow / open-questions, the DPI shape), update the .cursorrules topic map, then rebuild the KG (`claude/kg/bin/build.sh`) so `kg flow <newRequest>` / `kg cases` answer for the next session. **WIP gate**: if it's on a feature branch / behind a flag, mark it provisional — don't rewrite stable docs as if shipped.

---

## Quick checklist (pin this)

1. UD → numbered behavioural-rules table (traced to UD § + sample-calc).
2. `kg search/flow/crud/impact/writes/cases` → gap analysis (reuse / extend / new).
3. Placement matrix (§3) → which of the 12 layers each rule lands in.
4. Tiered design + rail checks (no-flow-break, CAS, api-contract, gaps-and-risks) → design doc, no code yet.
5. Implement per matrix → build green → diff-before-claim.
6. Open-questions block (in-boundary) + authorship/changelog/push.
7. `qa-handoff` package → fold into brain + rebuild KG (WIP-gated).
