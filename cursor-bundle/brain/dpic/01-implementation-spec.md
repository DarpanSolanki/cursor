# DPIC v1 — Implementation Specification (WIP)

> **Branch base:** `upstream/mfi_integration_v3.3.2`
> **Feature branch (local):** `feature/dpic-v1` in `novopay-platform-accounting-v2` and `novopay-platform-initial-setup`
> **UD reference:** `/home/darpan/darpan/UDs/UD_LMS_Delayed Payment Interest v1.3.docx` + accompanying `Sample Calculation and Accounting Entries of DPI v 1.3.xlsx`
> **Status:** WIP — full accrual / booking / billing pipeline + Loan 360 surfacing + 10 perf optimisations done. Remaining items (lifecycle handlers, push-to-collection, write-off) gated on Q-list confirmations from Vasanthi (Product) and Rohit (Loan Product / Product Scheme).
> **Companion docs:** [`00-overview.md`](00-overview.md) (one-page summary), [`05-open-questions.md`](05-open-questions.md) (live Q-list).

---

## 1. Executive Summary

DPI = **Delayed Payment Interest** — a 5th loan component (alongside Principal / Interest / Penalty / Fee) that accrues on `(overdue_principal + overdue_interest)` for EMIs past their grace window, billed on the **next** EMI due date, and settled via the same repayment pipeline as the existing four components.

This branch implements:

- A new appropriation slot for DPI (3rd in queue, between Interest and Penalty per UD §5.2).
- A standalone `DPICalculationService` that owns the formula `(overdue_P + overdue_I) × rate × days / days_in_year`.
- A new `dpi_accrual_details` staging table mirroring `penal_interest_accrual_details`.
- Three new batch jobs — `dpiAccrualCalculation`, `dpiAccrualBooking`, `dpiBilling` — each a tuned clone of the existing `interestAccrualCalculation` / `penalInterestAccrualBooking` / `loanAccountBilling` patterns.
- Loan 360 Summary tab surfacing for the 7 DPI sub-fields (Original / Accrued / Paid / Waived / Written Off / Outstanding / Overdue).
- 4 product-level masterdata seeds (`APPROPRIATION_LOGIC` row + `DPI_APBL` + `DPI_GO_LIVE_DATE` × 3 product types).
- 10 cross-cutting performance optimisations over the verbatim cloned pattern.

What's **not** in this WIP (deferred; gated on Q1-Q6 in the dependency mail):

- Lifecycle handlers for Foreclosure / Part Prepayment / Auto Closure / Restructuring / Death Foreclosure.
- Push-to-collection backend (DPI in payload + Total Outstanding recompute).
- DPI write-off path.
- The per-frequency child table that Rohit's "Product Scheme – Interest & DPI" task creates (Q4) — current resolver reads scheme-level fields and is designed to swap implementations without calc-side changes.
- The `loan_product_asset_criteria.sequence_5` schema add (Q3) — current appropriation processor injects DPI position dynamically into the in-memory map and works against the existing 4-slot data.

---

## 2. Branch + Commit State

### `novopay-platform-accounting-v2`

| SHA | Title | Author | Files | Net Δ |
|---|---|---|---|---|
| `86be1ae3d` | DPIC v1 WIP: appropriation + calc service scaffolding | Claude session | 7 | +297 / -7 |
| `0ffb460bf` | DPIC v1 WIP: accrual + booking + billing batch jobs, Loan 360 surfacing, orchestration wiring | Claude session | 30 | +1267 / -2 |
| `4d516a14f` | DPIC v1 WIP: 10 cross-cutting perf improvements over the cloned penal/interest pattern | Claude session | 13 | +177 / -143 |
| `d7a9d93da` | DPIC v1 WIP: setup-driven DPI appropriation sequence (replace hardcoded after-INT injection) | Claude session | 1 | +42 / -24 |
| `2f3c7e25a` | DPIC: pass DPI split in loanRepayment posting | **Darpan (manual)** | 1 | +8 |
| `456b4d34e` | DPIC: post GL entries in DPI booking and billing batches | **Darpan (manual)** | 8 | +164 / -13 |
| `0d0376b85` | WIP DPIC: DPD base includes DPI component | **Darpan (manual)** | 3 | +18 / -2 |
| `1f71a8b9c` | WIP DPIC: include DPI in derived totals and reversals | **Darpan (manual)** | 8 | +51 / -4 |

### `novopay-platform-initial-setup`

| SHA | Title | Author | Files | Net Δ |
|---|---|---|---|---|
| `22639bb0` | DPIC v1 WIP: code-master seed (APPROPRIATION_LOGIC + DPI_APBL + DPI_GO_LIVE_DATE) | Claude session | 1 | +50 |
| `8d52aae0` | DPIC v1 WIP: dpi_accrual_details table + composite/partial indexes | Claude session | 1 | +44 |
| `716a4bd4` | DPIC: align DPI flyway scripts to product V000 series | **Darpan (manual)** | 3 | +74 / -62 |
| `aacfc99f` | WIP DPIC: add dpi_amount columns for repayments and reversals | **Darpan (manual)** | 1 | +3 |
| `234241a7` | DPIC: set dpi_amount default to 0 | **Darpan (manual)** | 1 | +2 / -2 |

Authorship: every commit `DarpanSolanki <darpan@novopay.in>` (memory rule).
Build: `./gradlew compileJava` BUILD SUCCESSFUL on every commit.

---

## 3. Architecture & Design Decisions

### 3.1 What sits inside accounting-v2 vs upstream task owners

```
┌─────────────────────────── novopay-platform-accounting-v2 (mine) ───────────────────────────┐
│                                                                                              │
│  ┌──────────────────────┐    ┌────────────────────┐    ┌─────────────────────────┐          │
│  │ DPICalculationService│───▶│ Accrual Calc batch │───▶│ dpi_accrual_details     │          │
│  │ (formula + grace +   │    │ (daily, monthly)   │    │ (accrual_posting_date=  │          │
│  │  overdue base + rate)│    │                    │    │  null marker)           │          │
│  └──────────────────────┘    └────────────────────┘    └─────────────────────────┘          │
│            ▲                                                       │                         │
│            │ resolve(loanId)                                       │ becomes eligible       │
│            │                                                       ▼                         │
│  ┌─────────┴───────────────┐                            ┌─────────────────────────┐         │
│  │ DpiSchemeConfigResolver │                            │ Accrual Booking batch   │         │
│  │ (interface; swappable)  │                            │ (posts INTEREST/        │         │
│  └─────────┬───────────────┘                            │  DPI_NORMAL_ACCRUAL GL) │         │
│            │                                            └─────────────────────────┘         │
│            ▼                                                       │ (sets accrual_posting   │
│  ┌─────────────────────────────────────┐                          ▼  date)                  │
│  │ DefaultDpiSchemeConfigResolver      │                ┌─────────────────────────┐         │
│  │ (v1 stub: scheme-level fields)      │                │ DPI Billing batch       │         │
│  │ swap once Q4 lands                  │                │ (on EMI date: creates   │         │
│  └─────────────────────────────────────┘                │  loan_due_details DPI   │         │
│                                                          │  row + posts BILLING/   │         │
│                                                          │  DPI_NORMAL_BILLING GL) │         │
│                                                          └─────────────────────────┘         │
│                                                                    │                         │
│  ┌───────────────────────────────────────────────┐                │                         │
│  │ RepaymentApproppriationProcessor              │◀───────────────┘ (next repayment        │
│  │ (DPI as 3rd component, dynamic position       │                  knocks off DPI rows    │
│  │  insertion after INT)                         │                  per asset_criteria     │
│  └───────────────────────────────────────────────┘                  liquidation order)     │
│                                                                                              │
│  ┌───────────────────────────────────────────────┐                                          │
│  │ GetDpiAccrualDetailsProcessor                 │  (Loan 360 Summary tab; one aggregate   │
│  │ → 7 EC fields                                 │   query for all 7 sub-fields)           │
│  └───────────────────────────────────────────────┘                                          │
│                                                                                              │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
                                  ▲                                ▲
                  │ DPI rate + grace + days_in_year     │ component_type literal "DPI"
                  │ via per-frequency table (Q4)        │ matches APP_LOGIC_DPI master
                  ▼                                     ▼
┌──────────────────────────────────────┐  ┌──────────────────────────────────────────────────┐
│ Rohit — Product Scheme - Interest    │  │ Vasanthi — transaction_catalogue +               │
│ & DPI tab (per-frequency table)      │  │ transaction_accounting_rule (28 rows from Excel) │
└──────────────────────────────────────┘  └──────────────────────────────────────────────────┘
```

### 3.2 Why each major decision

**Decision 1: DPI as a 5th `loan_due_details.component_type` value (`"DPI"`)**, not a separate table.
Rationale: every existing repayment / appropriation / DPD-calc / EMI knock-off / Loan 360 path already iterates `loan_due_details` rows by `component_type`. Adding DPI as a 5th value (alongside `PRIN`, `INT`, `PINT`, `FEE`) means:
- Repayments knock off DPI naturally — no special-case code in `RepaymentApproppriationProcessor` beyond the new `else if (componentType.equalsIgnoreCase(DPI))` branch.
- DPD-calc job (`LoanAccountDpdCalcBatchProcessor`) sums all components; DPI joins automatically — **zero code change** to DPD job.
- EMI knock-off (`UpdateLoanInstallmentDetailsProcessor:51-55`) already filters to PRIN+INT only — DPI can stay outstanding without blocking knock-off, exactly as UD §5.5 specifies — **zero code change**.
- Reversal (`reverseTransaction`) is already routed by `(transaction_type, transaction_sub_type)`; DPI postings reverse via the same engine.

**Decision 2: DPI position is setup-driven — read from whatever sequence slot the product configures, with a masterdata-default fallback for legacy rows.**

Rationale: Production data shows products with **varied per-product orderings** (`PRIN→INT` vs `INT→PRIN`, `FEES@3` vs `FEES@4`, etc.). The whole point of `loan_product_asset_criteria.sequence_*` is that the bank decides per-product appropriation order. Hardcoding "DPI always after INT" violates that flexibility.

The processor:

1. **Iterates** every sequence slot returned by the DAO (forward-compatible with 4 slots today and 5 after Q3) — last tuple element is `liquidation_order`.
2. For each slot, looks up `APPROPPRIATION_COMPONENT_TYPE_MAP` and seats the component at slot index + 1.
3. **If DPI is in the configured sequences** (Q3 landed for that product, sequence_5 = `APP_LOGIC_DPI`), DPI sits at exactly the position the product setup chose — same flow as P/I/PINT/FEE.
4. **If DPI is NOT in any slot** (legacy 4-slot row pre-dating Q3), seat DPI at `FALLBACK_DPI_POSITION = 3` (matches masterdata seed V9000758 + UD §5.2 image 2), shifting existing components at slot 3+ by +1.

The fallback is **dead code** once every product's asset_criteria row has been migrated to include sequence_5 (Rohit's Q3 task migration step + UI for new products). The processor does **not** need a code change when Q3 lands — it just starts seeing DPI in the iterated sequences and skips the fallback.

This is the only DPI-sequence policy in code: *trust the setup; fall back to masterdata-default when setup is incomplete*.

**Decision 3: Three separate batch jobs (calc / booking / billing) instead of one combined.**
Rationale: matches the existing pattern (`interestAccrualCalculation` + `interestAccrualPosting` + `loanAccountBilling`). Allows independent scheduling, retry semantics, and operational debugging. Calc runs daily (cheap, all monthly overdue loans); booking runs daily but only posts when `accrual_posting_date IS NULL`; billing runs daily but only fires when the linked installment's due date has passed.

**Decision 4: `DpiSchemeConfigResolver` interface + `DefaultDpiSchemeConfigResolver` stub.**
Rationale: Q4 (per-frequency table) is owned by Rohit. v1 stub reads scheme-level columns and assumes monthly. When the per-frequency table lands, swap the resolver implementation — calc service and batch jobs unchanged. Single point of integration.

**Decision 5: `dpi_accrual_details` mirrors `penal_interest_accrual_details` shape but adds `accrual_posting_date` + `billing_posting_date` separately.**
Rationale: penal collapses accrual + booking into one `accrual_posting_date`; DPI needs separate tracking because UD §5.7 requires DPI to be **billed on the next EMI date** independently of when it was accrued/posted. So we track both events.

**Decision 6: GL post via `postTransaction(type, sub_type)` not via direct ledger writes.**
Rationale: matches existing convention. The engine resolves `(type, sub_type)` → `transaction_catalogue.id` → `transaction_accounting_rule` rows → resolved Dr/Cr GLs via `placeholder_master`. Product team owns the rule rows + GL setup (Q1, Q2). Our code passes the right `(type, sub_type)` literals. Reversal flow Just Works™ via the same engine.

---

## 4. Schema Changes

### 4.1 New table — `dpi_accrual_details` (V000186 in `accounting/sql/product/`)

```sql
CREATE TABLE IF NOT EXISTS dpi_accrual_details (
    id                              bigserial,
    loan_account_id                 bigint NOT NULL,
    installment_id                  bigint NOT NULL,
    overdue_date                    timestamp without time zone NOT NULL,
    base_amount                     decimal(20,6) NOT NULL,      -- snapshot; recomputed each calc cycle
    start_date                      timestamp without time zone NOT NULL,
    end_date                        timestamp without time zone NOT NULL,
    dpi_annual_rate                 decimal(9,6) NOT NULL,        -- snapshot at calc time
    days_in_year                    integer NOT NULL,             -- 360 / 365 / 364 / actual at calc time
    total_accrued_amount            decimal(20,6) NOT NULL,
    accrual_posting_date            timestamp without time zone,  -- null until accrual booking posts GL
    accrual_transaction_ref_number  varchar(32),
    billing_posting_date            timestamp without time zone,  -- null until billing posts GL + creates loan_due_details DPI row
    billing_transaction_ref_number  varchar(32),
    is_deleted                      boolean DEFAULT false NOT NULL,
    PRIMARY KEY (id)
);
```

### 4.2 Indexes — workload-tuned

| Index | Predicate | Used by |
|---|---|---|
| `idx_dpi_accrual_details_loan_account_id_end_date` | `(loan_account_id, end_date)` | `findMaxEndDateByLoanAccountId` (window-start lookup in calc batch) |
| `idx_dpi_accrual_details_installment_id` | `(installment_id)` | Per-installment lookups (foreclosure, part-prepayment, Loan 360) |
| `idx_dpi_accrual_details_unposted_by_loan` | **PARTIAL** `(loan_account_id) WHERE accrual_posting_date IS NULL AND is_deleted = false` | Booking reader's `BETWEEN account_id` range scan with predicate baked into the index |
| `idx_dpi_accrual_details_unbilled_by_loan` | **PARTIAL** `(loan_account_id, installment_id) WHERE billing_posting_date IS NULL AND accrual_posting_date IS NOT NULL AND is_deleted = false` | Billing reader hits this exact predicate shape |

Why partial indexes: the unposted-and-unbilled rows are a tiny fraction of total `dpi_accrual_details`. Partial indexes are a fraction of the size of full indexes and stay hot in cache.

Why composite over single-column: Postgres planner uses `(loan_account_id, end_date)` for `MAX(end_date) WHERE loan_account_id = ?` as an index-only scan; without the composite, MAX requires sorting all rows for a loan.

### 4.3 Code-master seeds (V9000758 in `masterdata/sql/product/` — product-level, applies across all tenants)

**(a) `APPROPRIATION_LOGIC / LOANS` masterdata** — DPI inserted at position 3:
```sql
-- Shift existing entries to make room
UPDATE code_master_details SET position = 5 WHERE code = 'APP_LOGIC_FEES' AND ...;
UPDATE code_master_details SET position = 4 WHERE code = 'APP_LOGIC_PNLT' AND ...;
-- Insert DPI at position 3
INSERT INTO code_master_details (..., position, code, value, ...)
VALUES ((SELECT id FROM code_master WHERE data_type='APPROPRIATION_LOGIC' AND data_sub_type='LOANS'),
        3, 'en-in', 'APP_LOGIC_DPI', 'Delayed Payment Installment', ...);
```
Position is the UI display order; the code values (runtime keys) are unchanged.

**(b) `DPI_APBL / DEFAULT`** — boolean dropdown (Yes/No) for product scheme UI:
```sql
INSERT INTO code_master ('DPI_APBL', 'DEFAULT', 'DPI Applicable', ...);
INSERT INTO code_master_details ('DPI_APBL/DEFAULT', 1, 'YES', 'Yes', ...);
INSERT INTO code_master_details ('DPI_APBL/DEFAULT', 2, 'NO',  'No',  ...);
```

**(c) `DPI_GO_LIVE_DATE / {JLGDL, INDL_LOAN, SHGDL}`** — per-product go-live date master rows. Date values seeded by Bank ops via webapp (not in this migration).

---

## 5. Constants & Type System Changes

### 5.1 `AssetsConstants.java`

```java
public static final String APPROPPRIATION_DPI_COMPONENT = "APP_LOGIC_DPI";
public static final String DPI = "DPI";

// Inside APPROPPRIATION_COMPONENT_TYPE_MAP static initialiser:
modifiableMap.put(APPROPPRIATION_DPI_COMPONENT, DPI);
```

The `APPROPPRIATION_COMPONENT_TYPE_MAP` is an immutable map keyed on the masterdata code (e.g. `APP_LOGIC_DPI`) returning the runtime `component_type` literal (e.g. `"DPI"`). Adding the entry is what lets `RepaymentApproppriationProcessor` translate a DPI-bearing asset-criteria slot into a sortable component.

### 5.2 `AccountingConstants.java`

```java
public static final String PRODUCT_SCHEME_DPI_APPLICABLE = "product_scheme_dpi_applicable";
public static final String DPI_AMOUNT = "dpi_amount";              // EC field name
public static final String DPI_APBL_DATATYPE = "DPI_APBL";          // code_master.data_type
public static final String DPI_APBL_VALUE_YES = "YES";
public static final String DPI_APBL_VALUE_NO = "NO";
public static final String DPI_GO_LIVE_DATE_DATATYPE = "DPI_GO_LIVE_DATE";
```

These are the canonical strings used everywhere DPI configuration is read/written.

---

## 6. Repayment Appropriation Logic

### 6.1 Files modified

`src/main/java/in/novopay/accounting/loan/repayment/processor/RepaymentApproppriationProcessor.java`

### 6.2 Changes

**(a) `RepaymentComponents` inner class** — added `dpiAmount` accumulator:
```java
public class RepaymentComponents {
    private BigDecimal principalAmount;
    private BigDecimal interestAmount;
    private BigDecimal penaltyAmount;
    private BigDecimal feeAmount;
    private BigDecimal dpiAmount;          // NEW
    private BigDecimal amountRemaining;
    // ... constructor initialises all to ZERO
}
```

**(b) `process()` body** — DPI now passes through to EC + total_settled_amount:
```java
executionContext.put("dpi_amount", String.valueOf(repaymentComponents.dpiAmount));
// ...
executionContext.put("total_settled_amount",
    repaymentComponents.principalAmount
        .add(repaymentComponents.interestAmount)
        .add(repaymentComponents.penaltyAmount)
        .add(repaymentComponents.feeAmount)
        .add(repaymentComponents.dpiAmount));
```

**(c) `doAppropriation()` switch** — DPI as a recognised component type:
```java
String componentType = loanDueDetailsEntity.getComponentType();
if      (componentType.equalsIgnoreCase(PRINCIPAL))  repaymentComponents.principalAmount = ...add(currentPaidAmount);
else if (componentType.equalsIgnoreCase(INTEREST))   repaymentComponents.interestAmount  = ...add(currentPaidAmount);
else if (componentType.equalsIgnoreCase(PENALTY))    repaymentComponents.penaltyAmount   = ...add(currentPaidAmount);
else if (componentType.equalsIgnoreCase(DPI))        repaymentComponents.dpiAmount       = ...add(currentPaidAmount);  // NEW
else                                                 repaymentComponents.feeAmount       = ...add(currentPaidAmount);
```

**(d) `parseLoanDueDetailsList()` — DPI rides with Principal+Interest in the installment-side bucket** for `LIQ_INSTL_CHRG_COMP` mode (UD §5.2: P → I → DPI horizontal; Penal/Fee on charge side):
```java
public void parseLoanDueDetailsList(...) {
    for (LoanDueDetailsEntity en : loanDueDetailsEntityList) {
        if (en.getComponentType().equalsIgnoreCase(PRINCIPAL)
                || en.getComponentType().equalsIgnoreCase(INTEREST)
                || en.getComponentType().equalsIgnoreCase(DPI)) {       // NEW
            installmentList.add(en);
        } else if (en.getComponentType().equalsIgnoreCase(PENALTY) || en.getComponentType().equalsIgnoreCase(FEE)) {
            chargeList.add(en);
        }
    }
}
```

**(e) Setup-driven sequence reading** — replaces the prior hardcoded 4-slot reads:

```java
// Last element in the tuple is the liquidation_order string.
int liquidationOrderIdx = assetCriteriaDetails.length - 1;
String liquidationOrder = (String) assetCriteriaDetails[liquidationOrderIdx];

// Iterate every sequence slot. Forward-compatible with both:
//   - today's 4-slot data (seq_1..seq_4 + liquidation_order = 5 elements)
//   - post-Q3 5-slot data (seq_1..seq_5 + liquidation_order = 6 elements)
for (int i = 0; i < liquidationOrderIdx; i++) {
    String code = (String) assetCriteriaDetails[i];
    if (code == null) continue;
    String componentType = APPROPPRIATION_COMPONENT_TYPE_MAP.get(code);
    if (componentType != null) {
        approppriationSequenceMap.put(componentType, i + 1);
    }
}

// Fallback: if the product's asset_criteria row pre-dates Q3 (no APP_LOGIC_DPI in any slot),
// seat DPI at the masterdata-default position so repayment can proceed.
if (!approppriationSequenceMap.containsKey(DPI)) {
    seatDpiAtFallbackPosition();
}
```

**(f) `seatDpiAtFallbackPosition()` helper** — fallback only:

```java
// Constant matches the masterdata seed V9000758
// (APPROPRIATION_LOGIC/LOANS/APP_LOGIC_DPI position 3) and UD §5.2 image 2.
// Per-product setup via sequence_5 takes precedence when present.
private static final int FALLBACK_DPI_POSITION = 3;

private void seatDpiAtFallbackPosition() {
    HashMap<String, Integer> shifted = new HashMap<>();
    for (Map.Entry<String, Integer> e : approppriationSequenceMap.entrySet()) {
        Integer pos = e.getValue();
        shifted.put(e.getKey(), pos >= FALLBACK_DPI_POSITION ? pos + 1 : pos);
    }
    shifted.put(DPI, FALLBACK_DPI_POSITION);
    approppriationSequenceMap.clear();
    approppriationSequenceMap.putAll(shifted);
}
```

### 6.3 Why setup-driven (not hardcoded "DPI after INT")

Production data on `loan_product_asset_criteria` (verified on `mfi_qa3`) shows products with **varied orderings** — some `PRIN→INT→PNLT→FEES`, others `INT→PRIN→PNLT→FEES`, others `PRIN→INT→FEES→PNLT`. The whole point of having configurable `sequence_*` columns is that the bank decides per-product appropriation order.

A hardcoded "DPI always after INT" rule **would override the bank's setup decision** — wrong design.

The setup-driven approach:

| Product state | Behaviour |
|---|---|
| Q3 landed, sequence_5 = `APP_LOGIC_DPI` (any slot 1-5) | DPI sits exactly where the product setup says — same flow as P/I/PINT/FEE |
| Q3 landed, sequence_5 = `APP_LOGIC_FEE` (i.e. DPI elsewhere, e.g. sequence_3) | DPI sits at slot 3 |
| Q3 landed, but row not yet migrated to include DPI | Fallback seats DPI at masterdata-default position (3) |
| Q3 not yet landed (current state) | Fallback seats DPI at masterdata-default position (3) |

The processor does **not** need a code change when Q3 lands. It already reads whatever number of sequence slots the DAO returns. Once Rohit's task migrates existing rows + the DAO query is extended to project `sequence_5`, DPI flows through naturally as a configured component.

The fallback is **dead code** once every product has been migrated.

---

## 7. DPI Calculation Service

### 7.1 Files (new package `loan/dpi/calculation/`)

| File | Purpose |
|---|---|
| `DpiSchemeConfig.java` | POJO holding (dpiApplicable, dpiAnnualRate, gracePeriodDays, daysInYear) |
| `DpiSchemeConfigResolver.java` | Interface; one method `resolve(loanAccountId)` |
| `DefaultDpiSchemeConfigResolver.java` | v1 stub (reads scheme-level fields, gates monthly only) — `@Cacheable` |
| `DPICalculationService.java` | Pure calc engine; window + grace + base + days × rate |

### 7.2 `DefaultDpiSchemeConfigResolver` — v1 stub

```java
@Service
public class DefaultDpiSchemeConfigResolver implements DpiSchemeConfigResolver {

    private static final String DPI_RATE_PROPERTY = "novopay.accounting.dpi.default.annual.rate";
    private static final BigDecimal DEFAULT_DPI_ANNUAL_RATE = new BigDecimal("0.24");
    private static final int DEFAULT_DAYS_IN_YEAR = 365;

    @Override
    @Cacheable(value = "dpi_scheme_config", key = "#loanAccountId", cacheManager = "accountingCacheManager")
    public DpiSchemeConfig resolve(Long loanAccountId) {
        LoanAccountEntity loanAccount = loanAccountDAOService.findOneByLoanAccountId(loanAccountId);
        ProductSchemeEntity scheme = productSchemeDAOService.getProductSchemeDetails(loanAccount.getLaProductSchemeId());

        boolean dpiApplicable = AssetsConstants.REPAYMENT_FREQ_MONTHLY.equalsIgnoreCase(loanAccount.getRepaymentFrequency());
        int gracePeriod = scheme != null && scheme.getGracePeriod() != null ? scheme.getGracePeriod() : 0;
        int daysInYear = resolveDaysInYear(scheme);   // from product_scheme.interest_calculation_days_in_year
        BigDecimal rate = resolveDpiAnnualRate();      // System.getProperty fallback to 0.24 default

        return new DpiSchemeConfig(dpiApplicable, rate, gracePeriod, daysInYear);
    }
}
```

**Swap path** when Q4 (per-frequency table) lands:
1. Add a new `PerFrequencyDpiSchemeConfigResolver` implementation reading from the new table for the loan's `repayment_frequency`.
2. Make Spring pick it via `@Primary` or profile-based wiring.
3. Calc service code unchanged. Batch services unchanged. Cache key unchanged.

### 7.3 `DPICalculationService.calculate()` — pure formula

```java
@Service
public class DPICalculationService {

    /**
     * Variant accepting a pre-resolved DpiSchemeConfig — used by the accrual-calc batch
     * service which already resolved the config to gate the loan in/out. Avoids a second
     * resolver call (cache lookup + serialization) per loan.
     */
    public BigDecimal calculate(Long loanAccountId, Date accrualStartDate, Date accrualEndDate, DpiSchemeConfig preResolved) {
        DpiSchemeConfig config = preResolved != null ? preResolved : dpiSchemeConfigResolver.resolve(loanAccountId);
        if (!config.isDpiApplicable()) return BigDecimal.ZERO;

        Date effectiveStart = applyGracePeriod(accrualStartDate, config.getGracePeriodDays());
        if (effectiveStart.after(accrualEndDate)) return BigDecimal.ZERO;

        // Single SQL aggregate — sums (due - paid - waived) over PRIN+INT overdue rows in one trip.
        BigDecimal overdueBase = nz(dpiAccrualDetailsDaoService.getOverdueBaseAmount(loanAccountId, effectiveStart));
        if (overdueBase.signum() <= 0) return BigDecimal.ZERO;

        Calendar startCal = toCalendar(effectiveStart);
        Calendar endCal = toCalendar(accrualEndDate);
        int days = interestCalculationUtil.getNumberOfDaysBetweenTwoCalendars(startCal, endCal);
        if (days <= 0) return BigDecimal.ZERO;

        BigDecimal accrued = interestCalculationUtil.computeInterest(
                overdueBase, config.getDpiAnnualRate(), config.getDaysInYear(), days);

        return accrued.setScale(2, RoundingMode.HALF_UP);
    }
}
```

**Key behavioural rules embedded:**
- Grace period is added to the start date — DPI accrues only after the grace window.
- Base = `(overdue_principal + overdue_interest)` only; **never on outstanding DPI itself** (no compounding — UD §5.4 + sample-calc rows confirmed).
- Formula `base × rate × days / days_in_year` reuses existing `InterestCalculationUtil.computeInterest()` so the math matches normal interest accrual exactly.
- Two calling forms: `calculate(loanId, start, end)` (resolves config) and `calculate(loanId, start, end, preResolvedConfig)` (skips resolve — used by calc batch which already has the config).

### 7.4 `getOverdueBaseAmount` — the load-bearing query

```java
@Query(value =
    "SELECT COALESCE(SUM(due_amount - paid_amount - waived_amount), 0) " +
    "FROM loan_due_details " +
    "WHERE loan_account_id = :loanAccountId " +
    "  AND component_type IN ('PRIN', 'INT') " +
    "  AND due_date <= :asOnDate " +
    "  AND is_deleted = false " +
    "  AND (due_amount - paid_amount - waived_amount) > 0",
    nativeQuery = true)
BigDecimal getOverdueBaseAmount(Long loanAccountId, Date asOnDate);
```

Hits `loan_due_details_loan_account_id_due_date_component_type_idx` (verified on QA3 — already indexed). Single roundtrip per loan per calc cycle.

---

## 8. DPI Accrual Calculation Batch Job

Path: `batchnew/dpi/dpiaccrualcalculation/`

| File | Role |
|---|---|
| `DpiAccrualCalculationBatchConfigService.java` | Spring Batch job setup (cron `0 0 18 * * ?`, grid 10, group LMS-EOD-BOD) |
| `DpiAccrualCalculationBatchProcessor.java` | Orchestration entry point — partitions accounts, runs parallel job |
| `DpiAccrualCalculationItemReader.java` | Cursor reader — picks active monthly loans with `past_due_days > 0` |
| `DpiAccrualCalculationItemProcessor.java` | Per-row processor, returns Vo or null if skipped |
| `DpiAccrualCalculationBatchService.java` | The actual work — calls `DPICalculationService` and stages an entity |
| `DpiAccrualCalculationItemWriter.java` | Persists `DpiAccrualDetailsEntity` rows in chunks via `JpaItemWriter` |
| `DpiAccrualCalculationVo.java` | Carrier between processor and writer |
| `DpiAccrualCalculationFailureEntityMapper.java` | Maps failed rows to `batch_failure_audit.context_value` |

### Reader query

```sql
SELECT la.account_id, a.currency, a.account_number, la.repayment_frequency,
       la.la_product_scheme_id, la.npa_ageing_start_date, la.sec_npa_tagging_date, la.past_due_days
FROM loan_account la
  JOIN account a ON a.id = la.account_id
WHERE la.loan_status = 'ACTIVE'
  AND la.past_due_days > 0
  AND la.repayment_frequency = 'MONTHLY'
  AND la.account_id BETWEEN :minValue AND :maxValue
  AND NOT EXISTS (SELECT 1 FROM batch_failure_audit bfa
                   WHERE bfa.context_value = la.account_id::text
                     AND bfa.group_code = 'LMS-EOD-BOD'
                     AND bfa.sub_group_code = 'LMS-EOD'
                     AND bfa.business_date = DATE(:businessDate))
```

### Processor flow (per row)

```
1. Resolve DpiSchemeConfig (cached — first call costs ~2 DB roundtrips, subsequent ~0)
2. If !dpiApplicable → skip
3. Fetch latest unsettled installment entity (single query — combined fetch)
4. resolveWindowStart() → MAX(end_date) from prior dpi_accrual_details rows, fallback to earliest_unsettled
5. If windowStart >= today → skip (nothing new to accrue)
6. Call DPICalculationService.calculate(loanId, windowStart, today, preResolvedConfig)
7. If accrued == 0 → skip
8. Build DpiAccrualDetailsEntity (accrual_posting_date null) and pass to writer
```

### Writer

`JpaItemWriter<DpiAccrualCalculationVo>` — Spring Batch calls `entityManager.merge(entity)` per Vo in the chunk inside one transaction.

---

## 9. DPI Accrual Booking Batch Job

Path: `batchnew/dpi/dpiaccrualbooking/`

Same 8-file shape as calculation. Differences:

> **Note (corrects a major earlier gap):** the initial WIP from this Claude session staged the entity update only — the writer called `dao.save()` but **never invoked `postAccrualToGl`**. As a result the GL leg was missing entirely. This was fixed in commit `456b4d34e` (manual): the writer now calls `dpiAccrualBookingBatchService.postAccrualToGl(exec, vo)` BEFORE `dao.save()`, using the `BatchExecutionContextHolder` pattern to access the orchestration `ExecutionContext` from the writer thread. Without this, the entire booking batch posted nothing to GL.

### Reader query

```sql
SELECT da.id, da.loan_account_id, da.installment_id, da.overdue_date, da.base_amount,
       da.start_date, da.end_date, da.dpi_annual_rate, da.days_in_year, da.total_accrued_amount,
       la.account_id, a.currency, a.account_number, a.office_id,
       la.npa_ageing_start_date, la.sec_npa_tagging_date
FROM dpi_accrual_details da
  JOIN loan_account la ON la.account_id = da.loan_account_id
  JOIN account a ON a.id = da.loan_account_id
WHERE da.accrual_posting_date IS NULL
  AND da.is_deleted = false
  AND la.loan_status IN ('ACTIVE', 'FORECLOSURE_FREEZE')
  AND la.account_id BETWEEN :minValue AND :maxValue
  AND NOT EXISTS (SELECT 1 FROM batch_failure_audit bfa WHERE ...)
```

Hits `idx_dpi_accrual_details_unposted_by_loan` partial index.

### `DpiAccrualBookingBatchService` — postTransaction call site (current code)

```java
public static final String POST_TRANSACTION = "postTransaction";
public static final String TRANSACTION_TYPE = "INTEREST";
// Defaults are v1 literals pending Q1 confirmation; can be overridden by JVM system properties at runtime.
private static final String SUBTYPE_NORMAL_ACCRUAL_PROPERTY = "novopay.accounting.dpi.txn.subtype.normal.accrual";
private static final String SUBTYPE_NPA_ACCRUAL_PROPERTY = "novopay.accounting.dpi.txn.subtype.npa.accrual";
public static final String TRANSACTION_SUB_TYPE_NORMAL_ACCRUAL = "DPI_NORMAL_ACCRUAL";
public static final String TRANSACTION_SUB_TYPE_NPA_ACCRUAL = "DPI_NPA_ACCRUAL";

// VO-driven variant — used by the writer; carries account_number/currency/office/npa from the
// reader row tuple so we don't re-fetch.
public String postAccrualToGl(ExecutionContext exec, DpiAccrualBookingVo vo) throws NovopayFatalException {
    var entity = vo.getDpiAccrualDetailsEntity();
    populateAccountDetails(exec, vo.getAccountNumber());
    exec.putLocal("transaction_type", TRANSACTION_TYPE);
    exec.putLocal("transaction_sub_type", resolveAccrualSubType(vo.isNpa()));
    // Deterministic client_reference_number — stable across retries/replays for the same row.
    exec.putLocal("client_reference_number", entity.getLoanAccountId() + "_DPI_ACCRUAL_" + entity.getId());
    exec.putLocal("currency", vo.getCurrency());
    exec.putLocal("amount", entity.getTotalAccruedAmount().toPlainString());
    exec.putLocal("value_date", String.valueOf(entity.getEndDate().getTime()));
    exec.putLocal("originating_office_id", vo.getOfficeId());
    exec.putLocal("receipt_number", null);

    apiClient.callInternalAPI(exec, POST_TRANSACTION, "v1", POST_TRANSACTION, -1, -1, false);
    Map<String, Object> resp = exec.getAPIResponse(POST_TRANSACTION);
    String txnRef = resp != null ? (String) resp.get("transaction_reference_number") : null;
    entity.setAccrualTransactionRefNumber(txnRef);
    vo.setTransactionRefNumber(txnRef);
    return txnRef;
}

// Helper resolving sub-type with system-property override. Until Q1 confirms the canonical literal,
// production can override via -Dnovopay.accounting.dpi.txn.subtype.normal.accrual=... without a redeploy.
private static String resolveAccrualSubType(boolean isNpa) {
    String key = isNpa ? SUBTYPE_NPA_ACCRUAL_PROPERTY : SUBTYPE_NORMAL_ACCRUAL_PROPERTY;
    String configured = System.getProperty(key);
    if (configured != null && !configured.isBlank()) return configured;
    return isNpa ? TRANSACTION_SUB_TYPE_NPA_ACCRUAL : TRANSACTION_SUB_TYPE_NORMAL_ACCRUAL;
}

// NPA inferred from the reader row tail (npa_ageing_start_date, sec_npa_tagging_date).
private static boolean isNpa(Object[] row) {
    if (row.length <= 14) return false;
    Object npaAgeingStart = row[14];
    Object secNpaTagging = row.length > 15 ? row[15] : null;
    return npaAgeingStart != null || secNpaTagging != null;
}
```

### Writer — calls postAccrualToGl, then persists

```java
@Override
public void write(Chunk<? extends DpiAccrualBookingVo> chunk) {
    String key = tenantCode + "-" + DpiAccrualBookingBatchConfigService.JOB_NAME;
    // ... thread-local tenant restore ...
    for (DpiAccrualBookingVo vo : items) {
        try {
            ExecutionContext exec = BatchExecutionContextHolder.getBatchExecutionContextCopy(key);
            dpiAccrualBookingBatchService.postAccrualToGl(exec, vo);   // GL post FIRST
            DpiAccrualDetailsEntity entity = vo.getDpiAccrualDetailsEntity();
            dpiAccrualDetailsDaoService.save(entity);                   // entity update with txnRef set
        } catch (NovopayFatalException e) {
            throw new BatchRuntimeException(e);
        }
    }
}
```

The `BatchProcessor` registers the orchestration EC into `BatchExecutionContextHolder` keyed on `tenant-jobName`, and the `Writer` retrieves it via `getBatchExecutionContextCopy()` because Spring Batch worker threads run with their own contexts.

The 6 GL-posting rules (from Excel `Accounting Rule` sheet):

| transaction_type | transaction_sub_type | Excel rule | Dr | Cr |
|---|---|---|---|---|
| `INTEREST` | `DPI_NORMAL_ACCRUAL` | 1 | AIR ON UNPAID EMI-JLGDL | INT ON UNPAID EMI-JLGDL |
| `BILLING` | `DPI_NORMAL_BILLING` | 2 | INT ON UNPAID EMI REC-JLGDL | AIR ON UNPAID EMI-JLGDL |
| `INTEREST` | `DPI_NPA_ACCRUAL` | 5 | AIR ON UNPAID EMI-JLGDL | INT SUSP AIR ON UNPAID EMI-JLGDL |
| `INTEREST` | `DPI_NPA_ACCRUAL_BOOKING` | 6 | INT SUSP AIR ON UNPAID EMI-JLGDL | INT SUSP ON UNPAID EMI-JLGDL |
| `REGULAR_TO_NPA` | `DPI_INT_INCOME` | 3, 4 | INT ON UNPAID EMI-JLGDL | INT SUSP {ON,AIR ON} UNPAID EMI-JLGDL |
| `NPA_TO_REGULAR` | `DPI_INT_INCOME` | 11, 12 | INT SUSP {ON,AIR ON} UNPAID EMI-JLGDL | INT ON UNPAID EMI-JLGDL |

The Dr/Cr rows are seeded by Vasanthi (Q1) into `transaction_accounting_rule` once GL setup (Q2) is done.

---

## 10. DPI Billing Batch Job

Path: `batchnew/dpi/dpibilling/`

> **Note (corrects a major earlier gap):** the initial WIP staged the `loan_due_details` row + `billing_posting_date` flag but **never invoked `postBillingToGl`**. As a result the BILLING/DPI_NORMAL_BILLING GL leg was missing. Fixed in commit `456b4d34e` (manual): `DpiBillingBatchService.postBillingToGl(...)` was added, and the writer now invokes it before persisting. Same `BatchExecutionContextHolder` pattern as accrual booking.

### Reader query (only fires for installments past their due date)

```sql
SELECT da.id, da.loan_account_id, da.installment_id, da.total_accrued_amount,
       lid.installment_date, la.account_id, a.currency, a.account_number, a.office_id
FROM dpi_accrual_details da
  JOIN loan_account la ON la.account_id = da.loan_account_id
  JOIN account a ON a.id = da.loan_account_id
  JOIN loan_installment_details lid ON lid.id = da.installment_id
WHERE da.billing_posting_date IS NULL
  AND da.accrual_posting_date IS NOT NULL
  AND da.is_deleted = false
  AND la.loan_status IN ('ACTIVE', 'FORECLOSURE_FREEZE')
  AND la.account_id BETWEEN :minValue AND :maxValue
  AND lid.installment_date <= DATE(:businessDate)
  AND NOT EXISTS (SELECT 1 FROM batch_failure_audit bfa WHERE ...)
```

This exact predicate (`billing_posting_date IS NULL AND accrual_posting_date IS NOT NULL AND is_deleted = false`) matches the `idx_dpi_accrual_details_unbilled_by_loan` partial index.

### Service (per row)

```java
public DpiBillingVo processBilling(Object[] row, Calendar nowCal) {
    Long id = (Long) row[0];
    Long loanAccountId = (Long) row[1];
    Long installmentId = (Long) row[2];
    BigDecimal accruedAmount = (BigDecimal) row[3];
    Date installmentDate = (Date) row[4];

    // 1. Create loan_due_details DPI row so the next repayment can knock it off
    LoanDueDetailsEntity due = new LoanDueDetailsEntity();
    due.setLoanAccountId(loanAccountId);
    due.setComponentType(AssetsConstants.DPI);          // "DPI"
    due.setBaseAmount(accruedAmount);
    due.setDueAmount(accruedAmount);
    due.setDueDate(installmentDate);
    due.setOverdueDate(installmentDate);
    due.setPaidAmount(BigDecimal.ZERO);
    due.setWaivedAmount(BigDecimal.ZERO);
    due.setLoanInstallmentDetailsId(installmentId);
    // ... created/updated metadata ...

    // 2. Mark dpi_accrual_details as billed (skip-the-fetch pattern: only id + billing_posting_date)
    DpiAccrualDetailsEntity entity = new DpiAccrualDetailsEntity();
    entity.setId(id);
    entity.setLoanAccountId(loanAccountId);
    entity.setBillingPostingDate(nowCal.getTime());

    // 3. Caller orchestration posts BILLING/DPI_NORMAL_BILLING via postTransaction
    return new DpiBillingVo(due, entity);
}
```

The DPI is now a `loan_due_details` row visible to:
- `RepaymentApproppriationProcessor` — knocks it off when a repayment lands.
- `LoanAccountDpdCalcBatchProcessor` — picks it up automatically since DPD sums all components.
- `getLoanAccountSummaryDetailsProcessor` — Loan 360 reads it via `GetDpiAccrualDetailsProcessor`.

---

## 10A. Manual additions on top of Claude-session work — what was missed

In four follow-up commits, gaps in the initial Claude-session WIP were corrected. Each is a real correctness or convention issue, not a polish item — important to internalise so the next round of work matches the bar.

### 10A.1 GL posting was not actually wired (commit `456b4d34e`)

The initial booking + billing writers called `dao.save(entity)` only — the entity got `accrual_posting_date` / `billing_posting_date` flagged, but **no postTransaction call ever fired**. Result: every batch run would mark rows "posted" without writing a single GL entry. Critical correctness bug.

Fix: writers now invoke `postAccrualToGl(exec, vo)` / `postBillingToGl(exec, vo)` BEFORE `save`, with the orchestration `ExecutionContext` retrieved via `BatchExecutionContextHolder.getBatchExecutionContextCopy(tenant + "-" + jobName)`. The `BatchProcessor` registers the EC into the holder at orchestration entry; the writer reads it back from worker threads.

### 10A.2 `loanRepayment` orchestration didn't propagate `dpi_amount` (commit `2f3c7e25a`)

Although `RepaymentApproppriationProcessor` populated `dpi_amount` in the EC, the `loanRepayment` Request orchestration never called `populateAdditionalAmountDetailsProcessor` for it — so `dpi_amount` never made it into postTransaction's `additional_amount_details`. Result: `transaction_accounting_rule` rules referencing `${DPI_AMT}` placeholder would resolve to nothing during repayment GL posting.

Fix: two new `populateAdditionalAmountDetailsProcessor` blocks added to the cash and CASA branches of `loanRepayment`, alongside `PRINCIPAL_AMT`/`INTEREST_AMT`/`PENALTY_AMT`/`EXCESS_AMT`:

```xml
<Processor bean="populateAdditionalAmountDetailsProcessor">
    <IParam fieldName="reference_code" value="DPI_AMT" scope="local" />
    <IParam fieldName="amount" value="${dpi_amount}" scope="local" />
</Processor>
```

### 10A.3 DPD base was wrong — included PINT+FEE (commit `0d0376b85`)

Earlier note in this doc claimed "DPD job already includes all components, no code change needed". **That was wrong.** The existing `getLoanAccountDueAmountByDueDate(...)` query summed all 4 components into the DPD base — including penal interest and fees. UD §5.5 specifies DPD base = `(overdue_principal + overdue_interest + overdue_DPI)` only — penal and fees do not contribute to DPD.

Fix: new DAO method + native query:

```java
@Query(nativeQuery = true, value =
    "SELECT COALESCE(SUM(due_amount - paid_amount - waived_amount), 0.00) " +
    "FROM loan_due_details " +
    "WHERE loan_account_id = ?1 AND due_date <= ?2 AND component_type IN (?3) AND is_deleted = false")
BigDecimal getLoanAccountDueAmountByDueDateForComponents(Long accountId, Date asOnDate, List<String> componentTypes);
```

`LoanAccountDpdCalcProcessor` switched to call this with `List.of("PRIN", "INT", "DPI")`. Now DPD goes to zero when only penal/fee residuals remain — matching UD §5.5.

### 10A.4 Flyway version naming + idempotency (commit `716a4bd4`)

Two issues with the original masterdata + DDL migrations:

- **Version numbering**: The product-level masterdata directory mixes `V000xxx` (low) and `V9000xxx` (high) numbers. The original WIP used `V9000758` (high range), but the convention being followed in this branch series is the `V000xxx` continuation. Rename: `V9000758` → `V000117`. Same for `V000186` → `V000187` (slot in DDL alongside the existing V000xxx series).
- **Idempotency**: The original INSERTs would error on second run if rows already existed. Fixed using `DO $$ BEGIN ... END $$;` blocks gated on `IF EXISTS / NOT EXISTS` checks; INSERTs use `INSERT ... SELECT ... WHERE NOT EXISTS (...)` pattern. Migrations now safe to re-run during local dev.

The DDL migration also dropped the verbose comments — keeping flyway scripts terse to match the project convention.

### 10A.5 NPA detection in booking was hardcoded `false`

The initial WIP passed `isNpa=false` literally. Fix: `isNpa(row)` static helper inspects `npa_ageing_start_date` and `sec_npa_tagging_date` columns from the reader row tail — any non-null marks the loan as NPA, swapping `transaction_sub_type` from `DPI_NORMAL_ACCRUAL` to `DPI_NPA_ACCRUAL` (Excel rule 5).

### 10A.6 `client_reference_number` was time-derived — not idempotent

Initial WIP suffix was `+ new Date().getTime()` — every retry produced a new reference, breaking postTransaction's idempotency-by-reference contract. Fix: deterministic `loanAccountId + "_DPI_ACCRUAL_" + entityId` (or `_DPI_BILL_` for billing). Same row → same ref-number across retries/replays.

### 10A.7 Sub-type literals — system property override

Until Q1 confirms the canonical sub-type strings, production can override via JVM properties:

- `novopay.accounting.dpi.txn.subtype.normal.accrual`
- `novopay.accounting.dpi.txn.subtype.npa.accrual`
- `novopay.accounting.dpi.txn.subtype.normal.billing`

Defaults stay as `DPI_NORMAL_ACCRUAL` / `DPI_NPA_ACCRUAL` / `DPI_NORMAL_BILLING`. This is the safest swap path — no redeploy needed if Product Ops decides on different literals.

### 10A.8 `Vo` carries reader-projected fields

To avoid the writer re-fetching loan/account metadata for the postTransaction call, both `DpiAccrualBookingVo` and `DpiBillingVo` were extended to carry `accountNumber`, `currency`, `officeId` (and `npa` flag for booking) from the reader row tuple.

### 10A.9 Loan-account derived-fields batch did not track DPI (commit `1f71a8b9c`)

The Loan 360 surfacing I built (`GetDpiAccrualDetailsProcessor`) reads from `loan_due_details` directly. But the platform also maintains a denormalised `loan_account_derived_fields` table fed by `LADerivedFieldsIProcessor` (in `batchnew/derivedfields/updateloanaccountderivedfieldsjob/`) — that table feeds many other reports, summaries, and downstream queries. **DPI was completely absent from that processor's component-walking logic and from the totals it computed.**

Concretely, missing variables added:

```java
BigDecimal overdueDpi = BigDecimal.ZERO;
BigDecimal totalDpiOutstanding = BigDecimal.ZERO;
BigDecimal totalDueOverdueDpi = BigDecimal.ZERO;
BigDecimal totalPaidDpi = BigDecimal.ZERO;
```

A new `DPI` branch in the per-component switch:

```java
} else if ("DPI".equalsIgnoreCase(componentType)) {
    results.totalDpiOutstanding = results.totalDpiOutstanding.add(outstandingAmount);
    results.totalPaidDpi = results.totalPaidDpi.add(paidAmount);
    if (isOverdue) results.overdueDpi = results.overdueDpi.add(outstandingAmount);
    if (isDueOrOverdue) results.totalDueOverdueDpi = results.totalDueOverdueDpi.add(outstandingAmount);
}
```

Four totals that drive Loan 360 / reporting were updated to include DPI:

| Field | Before | After |
|---|---|---|
| `data.setOverdueAmount(...)` | overduePrincipal + overdueInterest | + **overdueDpi** |
| `data.setLoanOutstanding(...)` | totalPos + overdueInterest − intSuspenseAmt | + **overdueDpi** |
| `data.setLoanOutstandingAmt(...)` | totalPos + totalInterestOutstanding + unpaidTotalCharges | + **totalDpiOutstanding** |
| `data.setTotalDueOverdueAmt(...)` | totalDueOverduePrincipal + totalDueOverdueInterest | + **totalDueOverdueDpi** |

Without this fix, every Loan 360 / report consumer that reads from `loan_account_derived_fields` would have shown wrong totals — outstanding under-stated by the DPI portion, overdue under-stated, etc. Big consistency miss.

### 10A.10 `loan_account_payments_details.dpi_amount` column + entity field (commits `aacfc99f` + `1f71a8b9c`)

Every successful repayment writes a row to `loan_account_payments_details` recording the per-component split (principal/interest/penalty/fee). DPI was missing entirely from this audit/persistence table.

- DDL: `ALTER TABLE loan_account_payments_details ADD COLUMN IF NOT EXISTS dpi_amount numeric(19,6) DEFAULT 0` (V000188).
- Entity: `LoanAccountPaymentsDetailsEntity` adds `private BigDecimal dpiAmount` + getter/setter.
- Processor: `CreateLoanAccountPaymentsDetailsProcessor` now reads `dpi_amount` from EC and persists it (defaults to ZERO if absent so legacy flows don't NPE).

### 10A.11 `transaction_reversal_details.dpi_amount` column + entity field (commits `aacfc99f` + `1f71a8b9c`)

Same gap on the reversal side — every transaction reversal writes a row to `transaction_reversal_details` with the per-component reversed amounts. DPI missing.

- DDL: same migration adds `dpi_amount` column.
- Entity: `TransactionReversalDetailsEntity` + `dpiAmount` field.
- Constants: `TransactionReversalConstants.DPI = "dpi_amount"`.
- Processor: `CreateTransactionReversalDetailsProcessor` reads it from EC and persists.

### 10A.12 Repayment reversal data generator didn't recognise DPI (commit `1f71a8b9c`)

`RepaymentReversalDataGenerator.generate()` walks the `loanDueDetailsEntityList` and reverses paid amounts component-by-component. The original switch only handled PRIN/INT/PENALTY/FEE. DPI rows would either fall through to the unhandled branch or be silently treated as fee — the actual DPI portion of a repayment would not be properly reversed.

Fix:

```java
} else if (loanDueDetailsEntity.getComponentType().equalsIgnoreCase(AssetsConstants.DPI)) {
    reverseDpiPaid = computeReversedAmountAndPopulateVO(reverseDpiPaid, reversalDTOList, loanDueDetailsEntity);
}
```

Plus DPI is now seeded from `loanAccountPaymentsDetailsEntity.getDpiAmount()` at the start of the reversal walk, so the running tally starts from the actually-paid amount.

### 10A.13 EXCESS_AMT reversal calculation excluded DPI (commit `1f71a8b9c`)

When a `LOAN_REPAYMENT/EXCESS_AMT` transaction is reversed, the engine recomputes the total settled amount across all components and adds it to the existing excess. DPI was missing:

```java
BigDecimal totalSettledExcessAmount = loanAccountPaymentsDetailsEntity.getPrincipalAmount()
    .add(loanAccountPaymentsDetailsEntity.getInterestAmount())
    .add(nz(loanAccountPaymentsDetailsEntity.getDpiAmount()))     // NEW
    .add(loanAccountPaymentsDetailsEntity.getFeeAmount())
    .add(loanAccountPaymentsDetailsEntity.getPenaltyAmount());
```

Without this, every excess-refund reversal on a loan with DPI activity would have computed the excess wrong by the DPI amount.

### 10A.14 `LoanAccountPaymentsDetailsReversalProcessor` — copy DPI on reopen (commit `1f71a8b9c`)

When a loan is reopened, payment-detail records are cloned. `dpiAmount` was missed from the clone. Single-line fix:

```java
newEntity.setDpiAmount(originalEntity.getDpiAmount());
```

---

## 11. Loan 360 Surfacing

### File added

`src/main/java/in/novopay/accounting/loan/dpi/accrual/processor/GetDpiAccrualDetailsProcessor.java`

### Single aggregate query

```sql
-- DpiAccrualDetailsRepository.getLoan360DpiSummary
SELECT
  COALESCE((SELECT SUM(total_accrued_amount) FROM dpi_accrual_details d
            WHERE d.loan_account_id = :loanAccountId AND d.is_deleted = false), 0) AS accrued,
  COALESCE(SUM(ldd.due_amount), 0)                                                  AS billed,
  COALESCE(SUM(ldd.paid_amount), 0)                                                 AS paid,
  COALESCE(SUM(ldd.waived_amount), 0)                                               AS waived,
  COALESCE(SUM(GREATEST(ldd.due_amount - ldd.paid_amount - ldd.waived_amount, 0)), 0) AS outstanding,
  COALESCE(SUM(CASE WHEN ldd.due_date <= CURRENT_DATE
                    THEN GREATEST(ldd.due_amount - ldd.paid_amount - ldd.waived_amount, 0)
                    ELSE 0 END), 0)                                                  AS overdue
FROM loan_due_details ldd
WHERE ldd.loan_account_id = :loanAccountId
  AND ldd.is_deleted = false
  AND ldd.component_type = 'DPI'
```

Returns 6 scalars in one trip. `dpi_written_off` is `0` (no write-off path yet).

### Processor populates 7 EC fields

```java
executionContext.put("dpi_original",     billed.toPlainString());
executionContext.put("dpi_accrued",      accrued.toPlainString());
executionContext.put("dpi_paid",         paid.toPlainString());
executionContext.put("dpi_waived",       waived.toPlainString());
executionContext.put("dpi_written_off",  writtenOff.toPlainString());     // 0 for now
executionContext.put("dpi_outstanding",  outstanding.toPlainString());
executionContext.put("dpi_overdue",      overdue.toPlainString());
```

### Wired into `getLoanAccountSummaryDetails` orchestration

```xml
<Processors>
    <Processor bean="setCommonAttributesProcessor" />
    <Processor bean="valdiateLoanAccountNumberProcessor" />
    <Processor bean="getLoanAccountSummaryDetailsProcessor" />
    <Processor bean="getPenalInterestAccrualDetailsProcessor" />
    <Processor bean="getInterestAccrualDetailsProcessor" />
    <Processor bean="getDpiAccrualDetailsProcessor" />     <!-- NEW -->
    <Processor bean="populateUserStoryProcessor"> ... </Processor>
</Processors>
```

---

## 12. Orchestration XML Wiring

### Three new `Request` entries in `loans_orc.xml`

```xml
<Request name="dpiAccrualCalculation">
    <Validators>
        <Validator bean="patternFieldValidator">
            <IParam fieldName="function_code" errorCode="11012" pattern="DEFAULT" />
            <IParam fieldName="function_sub_code" errorCode="11013" pattern="DEFAULT|BATCH" />
        </Validator>
    </Validators>
    <Processors>
        <Control method="regExp" pattern="${function_sub_code}" condition="=" value="BATCH">
            <Processor bean="dpiAccrualCalculationBatchProcessor" />
        </Control>
    </Processors>
</Request>
<!-- dpiAccrualBooking, dpiBilling — same shape -->
```

The `function_sub_code = BATCH` branch fires the `*BatchProcessor` which orchestrates the parallel job. This matches `penalInterestAccrualBooking` exactly so the existing scheduler wiring + monitoring carry over.

### `BatchConfig.java` — three new SynchronizedItemStreamReader beans

```java
@Bean @StepScope
public SynchronizedItemStreamReader<Object[]> dpiAccrualCalculationItemReader(...) {
    return new SynchronizedItemStreamReaderBuilder<Object[]>()
        .delegate(new DpiAccrualCalculationItemReader(...))
        .build();
}
// dpiAccrualBookingItemReader, dpiBillingItemReader — same pattern
```

---

## 13. Performance Improvements (10 detailed)

Every improvement is a measurable reduction in DB roundtrips, cache cost, or planner cost. Each lands in commit `4d516a14f` (+ index reshape in `8d52aae0`).

### PERF-1: Single-query MAX(end_date)
- **Before:** `findAllByLoanAccountId().forEach(maxEnd)` — full row scan in Java
- **After:** `findMaxEndDateByLoanAccountId` JPQL — single MAX
- **Win:** O(n) → O(1) in DB cost; for a loan with 100 historical accrual rows, 100 row fetches → 1 scalar

### PERF-2: Aggregate Loan 360 query
- **Before:** 2 DB calls (sum-accrued + per-component due-list scan) + Java loop reducing N rows
- **After:** 1 native aggregate returning 6 scalars
- **Win:** 2 roundtrips → 1; N-row payload → 6 BigDecimals

### PERF-3: `@Cacheable` on DpiSchemeConfig
- **Before:** `resolve()` reads `loan_account` + `product_scheme` per call (~2 DB queries)
- **After:** Cached on `accountingCacheManager` keyed on `loanAccountId`
- **Win:** EOD batch over N loans: cold cache cost stays at N reads, warm cache is in-memory

### PERF-4: NOT EXISTS + bigint BETWEEN in reader queries
- **Before:** `LEFT JOIN batch_failure_audit ON la.account_id = bfa.context_value::int4 ... WHERE bfa.context_value IS NULL`
- **After:** `WHERE ... AND NOT EXISTS (SELECT 1 FROM batch_failure_audit ...)`
- **Win:** Postgres planner picks an anti-join + bitmap-scan instead of full LEFT JOIN materialisation; bigint range filter (`account_id BETWEEN`) replaces the int4 cast that forced sequential scan in some plans

### PERF-5: Skip findOneById in booking + billing
- **Before:** Per-row `findOneById(id)` re-fetched the entity even though the reader already had every column
- **After:** Entity rebuilt from the row tuple; JpaItemWriter merges
- **Win:** N rows × 1 SELECT per row eliminated

### PERF-6: DISTINCT + ORDER BY in partitioner data queries
- **Before:** `SELECT account_id FROM dpi_accrual_details ...` — duplicates per loan with multiple unposted rows
- **After:** `SELECT DISTINCT la.account_id ... ORDER BY la.account_id`
- **Win:** `CustomBatchIdListPartitioner.partition()` slices a sorted list positionally — duplicates inflate chunks, cause overlapping ranges, skew worker load. DISTINCT + ORDER BY guarantees evenly-sized non-overlapping account_id ranges.

### PERF-7: Single SQL aggregate for overdue base
- **Initial draft:** Used `getPrincipalOutstandingAmountByDueDate` + `getInterestDueAmountByDueDate` — but those query `due_date > ?` (outstanding-future) not `due_date <= ?` (overdue-as-of). Wrong semantics.
- **Final:** Dedicated `getOverdueBaseAmount(loanAccountId, asOnDate)` — `SUM(due_amount - paid_amount - waived_amount)` over PRIN+INT overdue rows.
- **Win:** Correct semantics + single roundtrip; hits existing `loan_due_details_loan_account_id_due_date_component_type_idx` index.

### PERF-8: Pre-resolved DpiSchemeConfig passthrough
- **Before:** Calc batch service resolves config; calls calc service which resolves it again
- **After:** `calculate(loanId, start, end, preResolved)` overload accepts the already-resolved config
- **Win:** Removes the second cache lookup per loan per calc cycle

### PERF-9: Combined installment fetch
- **Before:** `getInstallmentDateForDpdCount(loanId)` → date, then `getLoanInstallmentDetailsEntityByLoanAccountIdAndDueDate(loanId, date)` → entity (2 queries for one row)
- **After:** Single `getLatestLoanInstallmentDetailsEntity(loanId, today)` returns entity directly
- **Win:** Halves installment-lookup roundtrips per calc cycle

### PERF-10: Composite + partial indexes on `dpi_accrual_details`
- **Before (initial draft):** Three single-column indexes (`loan_account_id`, `installment_id`, `accrual_posting_date IS NULL`)
- **After:** Composite `(loan_account_id, end_date)` + partial indexes matching reader predicates exactly
- **Win:** Booking reader's `BETWEEN account_id` scan + `accrual_posting_date IS NULL AND is_deleted = false` predicate hits a tiny partial index. Same for billing reader.

### Aggregate impact estimate (one EOD cycle, N=10,000 monthly overdue loans)

| Concern | Before | After | Reduction |
|---|---|---|---|
| Calc-cycle DB calls per loan | ~7 | ~3 | ~57% |
| Booking-cycle DB calls per loan | ~3 | ~2 | ~33% |
| Loan 360 calls per request | 2-3 + N-row scan | 1 + 6 scalars | ~70% |
| Reader index cost (booking) | seq scan on bfa | partial-index scan | order of magnitude |
| Worker load skew (partitioner) | up to 10× imbalance | even | predictable EOD time |

These are estimates — real measurements need a load test once the sub-types are confirmed.

---

## 14. End-to-End Flow Walkthrough

### Scenario: monthly EMI of ₹10,000 (₹2,000 INT + ₹8,000 PRIN) misses on 5-Jan-26, partial pay 6,000 on 20-Jan-26 (after grace), full pay on 5-Feb-26.

**5-Jan-26** — EMI #1 due. Customer doesn't pay. `loan_due_details` has 2 rows (PRIN ₹8,000 due + INT ₹2,000 due, neither paid). `loan_account.past_due_days` ticks up daily.

**20-Jan-26** (grace = 5 days, so DPI accrual starts 10-Jan-26) — Customer pays ₹6,000. RepaymentApproppriationProcessor:
1. Reads `liquidation_order` for the product (let's say `LIQ_INSTL_CHRG_COMP`)
2. Calls `parseLoanDueDetailsList()` → installment-side has [PRIN, INT]; charge-side empty (no PINT/FEE). DPI not yet billed so not in due_details.
3. Sorts installment-side by (due_date asc, position asc with DPI inserted at INT_position+1)
4. Allocates: ₹2,000 → INT (cleared), ₹4,000 → PRIN (₹4,000 remaining)

**31-Jan-26** (month-end) — `dpiAccrualCalculation` job fires:
- Reader picks the loan (active, past_due_days > 0, monthly)
- Resolver returns `DpiSchemeConfig(applicable=true, rate=0.24, grace=5, days=360)`
- `getLatestLoanInstallmentDetailsEntity()` returns EMI #1
- `resolveWindowStart()` returns 10-Jan-26 (no prior dpi_accrual_details rows; falls back to earliest unsettled + grace)
- `getOverdueBaseAmount(loanId, 10-Jan-26)` returns ₹4,000 (₹4,000 PRIN remaining; INT was cleared)
- Days from 10-Jan-26 to 31-Jan-26 = 21
- Accrued = 4000 × 0.24 × 21 / 360 = ₹56
- Stage row in `dpi_accrual_details` with `total_accrued_amount = 56`, `accrual_posting_date = NULL`

**31-Jan-26 (later same day)** — `dpiAccrualBooking` job fires:
- Reader picks the unposted row
- Builds postTransaction call: `(INTEREST, DPI_NORMAL_ACCRUAL, ₹56, value_date=31-Jan-26)`
- engine resolves rule → AIR ON UNPAID EMI-JLGDL Dr 56 / INT ON UNPAID EMI-JLGDL Cr 56
- Sets `accrual_posting_date = 31-Jan-26`, `accrual_transaction_ref_number = ...`

**5-Feb-26** — EMI #2 due. `dpiBilling` job fires:
- Reader picks the row (accrual_posting_date NOT NULL, billing_posting_date NULL, installment_date 5-Jan ≤ today)
- Service creates `loan_due_details` row: `component_type=DPI`, `due_amount=56`, `due_date=5-Jan-26`, `loan_installment_details_id=EMI#1`
- Posts `(BILLING, DPI_NORMAL_BILLING, ₹56)` → INT ON UNPAID EMI REC-JLGDL Dr 56 / AIR ON UNPAID EMI-JLGDL Cr 56
- Sets `billing_posting_date = 5-Feb-26`

Customer now sees DPI ₹56 in Loan 360 Summary tab (`dpi_billed=56, dpi_outstanding=56, dpi_overdue=56`).

**5-Feb-26 (customer pays full ₹14,056)** — RepaymentApproppriationProcessor:
1. Now `loan_due_details` has 5 rows: EMI#1 PRIN remaining ₹4,000 + DPI ₹56; EMI#2 PRIN ₹8,000 + INT ₹2,000.
2. After sort: [EMI#1 PRIN ₹4,000 (oldest, slot 1), EMI#1 INT ₹0 already cleared, EMI#1 DPI ₹56 (oldest, slot 3), EMI#2 PRIN, EMI#2 INT, EMI#2 DPI=0]
3. Allocation order under `LIQ_INSTL_CHRG_COMP`: first installment-side (P → I → DPI horizontal) — so EMI#1 PRIN ₹4,000, EMI#1 DPI ₹56, EMI#2 INT ₹2,000, EMI#2 PRIN ₹8,000. ₹14,056 covers exactly these.
4. EC carries `dpi_amount=56`, `principal_amount=12000`, `interest_amount=2000`, `total_settled_amount=14056`.

EMI#1 is marked `is_settled=true` because `paid(P+I) >= due(P+I)` (₹10,000 ≥ ₹10,000). The DPI residual was paid, but even if it hadn't been, the EMI knock-off doesn't depend on it.

DPD recalculates to 0 (no overdue components left).

---

## 15. Open Dependencies & How They Slot In

Live Q-list in [`05-open-questions.md`](05-open-questions.md). One-line each:

- **Q1 (Vasanthi)** — Confirms exact `(transaction_type, transaction_sub_type)` literals. Single-edit swap if different from `DPI_NORMAL_ACCRUAL` etc.
- **Q2 (Vasanthi / Product Ops)** — GL setup via webapp. Until done, postTransaction calls fail with "GL not found".
- **Q3 (Rohit)** — `loan_product_asset_criteria.sequence_5` schema. Not blocking — dynamic injection works on existing 4 slots.
- **Q4 (Rohit)** — Per-frequency child table for DPI rate / grace / days-in-year. Until done, `DefaultDpiSchemeConfigResolver` reads scheme-level fields with v1 stub assumptions. Resolver swap is one Spring `@Primary` annotation away.
- **Q5 (Rohit)** — Boundary confirmation between DPI calc service (mine) and product-scheme DPI calculation work (his). Just a confirmation; no code impact.
- **Q6 (Rohit)** — `componentType = "DPI"` confirmation. Mine writes `"DPI"`; his task must write the same string.

### How the WIP code adapts

| When this happens | What changes |
|---|---|
| Q1 lands with different sub-type literals | Edit 4 string constants in `DpiAccrualBookingBatchService` |
| Q2 lands (GLs seeded) | postTransaction calls actually post; nothing in code changes |
| Q3 lands (`sequence_5` added) | DAO query needs to read 5 columns; `RepaymentApproppriationProcessor` reads `assetCriteriaDetails[0..4]` (not [0..3]); shifts `liquidation_order` from index [4] to [5] — small targeted edit |
| Q4 lands (per-frequency table) | Add `PerFrequencyDpiSchemeConfigResolver`, mark `@Primary`; old resolver stays as fallback |
| Q5 confirmed | Documentation update only |
| Q6 confirmed | No change (already aligned) |

---

## 16. Testing & Verification Plan

### Unit tests (to add — not in this WIP)

| Class | Tests |
|---|---|
| `DPICalculationService` | (a) Returns 0 if config not applicable. (b) Returns 0 if window collapses by grace. (c) Returns 0 if no overdue base. (d) Returns rounded BigDecimal for happy path. (e) Pre-resolved config skips resolver call. |
| `RepaymentApproppriationProcessor` | (a) DPI accumulates into `dpiAmount`. (b) DPI routes to installment list in `LIQ_INSTL_CHRG_COMP`. (c) `insertDpiAfterInterest()` shifts later positions correctly. (d) DPI position absent when INT not configured falls through to `size+1`. |
| `GetDpiAccrualDetailsProcessor` | (a) Populates 7 EC fields. (b) Returns 0 for accounts with no DPI. (c) `dpi_overdue` only counts rows where `due_date <= today`. |
| `DpiAccrualCalculationBatchService` | (a) Skips when not applicable. (b) Skips when no installments. (c) Skips when window collapses. (d) Stages entity with correct fields. |

### Integration tests (to add)

| Scenario | Verify |
|---|---|
| Happy path EMI miss → accrue → book → bill → repay | All 4 batch jobs fire in sequence; loan_due_details DPI row created; repayment knocks it off |
| NPA loan accrual | Posts `DPI_NPA_ACCRUAL` not `DPI_NORMAL_ACCRUAL` |
| Multiple unposted rows for one loan | Booking processes all of them in correct chunks |
| Reversal of repayment with DPI | Standard reverseTransaction unwinds DPI portion |
| Loan 360 with DPI rows | All 7 sub-fields populated correctly |

### Manual verification (after push + Q1/Q2 land)

```sql
-- After dpiAccrualCalculation runs:
SELECT count(*) FROM dpi_accrual_details WHERE accrual_posting_date IS NULL;

-- After dpiAccrualBooking runs, expect transaction_master rows:
SELECT count(*) FROM transaction_master WHERE transaction_sub_type = 'DPI_NORMAL_ACCRUAL';

-- After dpiBilling, expect new loan_due_details DPI rows:
SELECT count(*) FROM loan_due_details WHERE component_type = 'DPI' AND is_deleted = false;

-- Loan 360 endpoint test:
curl ... getLoanAccountSummaryDetails ... | jq '.dpi_outstanding, .dpi_accrued, .dpi_paid'
```

### Build verification

`./gradlew compileJava` — currently BUILD SUCCESSFUL. Run before each push.

---

## 17. What's Remaining — Complete Inventory

This is the master "what's left" view. Anything not in §3-§14 (which is what's done) is here.

### 17.1 Summary table — at-a-glance

| # | Item | Status | Blocking input | Est. size | Owner |
|---|---|---|---|---|---|
| R1 | Lifecycle handler — Foreclosure | Not started | Q4 (DPI Till Date formula source) | ~150 LOC + processor edit | Darpan |
| R2 | Lifecycle handler — Loan Part Prepayment | Not started | Q4 | ~80 LOC | Darpan |
| R3 | Lifecycle handler — Auto Closure | Not started | Q4 | ~50 LOC | Darpan |
| R4 | Lifecycle handler — Loan Restructuring | **DONE** (2026-06-12) | — | `CapitaliseAccruedDpiOnRestructureProcessor` | Darpan |
| R5 | Lifecycle handler — Death Foreclosure | Not started | Q4 | ~80 LOC | Darpan |
| R6 | Lifecycle handler — Loan Advance Payment | Not started | None | ~60 LOC | Darpan |
| R7 | Push-to-Collection backend (DPI in payload + Total Outstanding recompute) | **DONE** (verified 2026-06-12) | — | `LoanRecurringPaymentBatchProcessor` | Darpan |
| R8 | DPI write-off path | Not started | Trigger flow design | ~120 LOC + flyway | Darpan |
| R9 | Cache eviction wiring on product-scheme update | Not started | Q4 (so we know which scheme-update path to hook) | ~10 LOC | Darpan |
| R10 | Per-frequency resolver impl (replace v1 stub) | Not started | Q4 (table created) | ~70 LOC | Darpan |
| R11 | Lifecycle handler — Transaction Reversal (verify) | **No code change** | Already works via `reverseTransaction` engine | 0 | — |
| R12 | DPD job update | **No code change** | Already correct | 0 | — |
| R13 | EMI knock-off rule | **No code change** | Already P+I-only in code | 0 | — |
| R14 | Day-Zero handling for pre-go-live overdues | **Parked v1** | Bank confirms policy | ~150 LOC + one-shot job | Darpan |
| R15 | Weekly / Bi-Weekly / Daily DPI frequency support | **Parked v1** | Q4 (rates per frequency) | ~30 LOC (drop monthly filter) | Darpan |
| R16 | Unit tests | Not started | None | ~400 LOC across ~10 test classes | Darpan |
| R17 | Integration tests | Not started | Q1, Q2 (so postTransaction actually posts) | ~200 LOC | Darpan |
| R18 | Batch JDBC update optimisation (vs JPA merge) | Not started — opportunistic | Perf-test signal | ~100 LOC if needed | Darpan |
| R19 | eNACH DPI presentation file | **Out of scope** | Owned by `UD_LMS_Bulk_eNACH Representation v1.1` | — | Other team |
| R20 | Loan Product / Product Scheme UI fields | **Out of scope** | — | — | Webapp / Rohit |
| R21 | `loan_product_asset_criteria.sequence_5` schema | **Out of scope** | Q3 | — | Rohit |
| R22 | Per-frequency `product_scheme_repayment_frequency_details` table | **Out of scope** | Q4 | — | Rohit |
| R23 | `transaction_catalogue` + `transaction_accounting_rule` seeds | **Out of scope** | Q1 | — | Vasanthi |
| R24 | GL master setup (6 GLs) | **Out of scope** | Q2 | — | Product Ops via webapp |

### 17.2 Detail per item

#### R1 — Foreclosure handler

**What:** Surface `Billed DPI` and `DPI Till Date of Foreclosure` in the foreclosure preview API response + roll DPI into the foreclosure GL postings.

**Why:** UD §5.11 + Excel "Loan Foreclosure" sheet (Examples 1+2). Foreclosure preview screen shows two new line items, and the GL posting flow needs to clear out `AIR ON UNPAID EMI` + `INT ON UNPAID EMI REC` accruals at foreclosure time.

**What changes:**
- Edit `ForeclosurePreviewProcessor` (or equivalent) to call `DpiAccrualDetailsDaoService.getLoan360DpiSummary()` and surface `dpi_billed`, `dpi_till_date_of_foreclosure` (computed as `accrued - billed - paid`).
- Edit foreclosure GL flow processors to issue `LOAN_PREPAYMENT/CASH` postings using rules 13-18 from Excel (the `AIR ON UNPAID EMI-JLGDL` and `INT ON UNPAID EMI REC-JLGDL` clearing rules).

**Blocking:** Q4 — exact "DPI Till Date of Foreclosure" formula needs to be confirmed (is it `accrued - billed - paid` or `accrued from last_billing_date till foreclosure_date`?). Excel example shows it as a separate computed value, but formula isn't crisply spelled.

#### R2 — Loan Part Prepayment handler

**What:** Include DPI bucket in the part-prepayment amount calculation + GL postings (Excel rules 19-22).

**What changes:**
- Edit `PopulateAdditionalAmountForPartPrepaymentProcessor` to include DPI in the available outstanding bucket.
- Wire `LOAN_PART_PREPAYMENT/CASH` GL postings via existing engine (sub-types existing).

**Blocking:** Q4 (uses calc service which needs config).

#### R3 — Auto Closure handler

**What:** When a loan auto-closes with residual DPI, write it off to `INT ON UNPAID EMI WOFF-JLGDL` (Excel rule 29).

**What changes:**
- Edit auto-closure processor to detect outstanding DPI and route to write-off.
- Post `AUTO_CLOSURE/LOAN_ACCOUNT` (already an existing sub-type — check Excel rule 29).

**Blocking:** Q4 (knowing if any DPI is outstanding).

#### R4 — Loan Restructuring handler — DONE (2026-06-12)

Product ruling: DPI treated exactly like normal interest — no waiver, no upfront. Billed DPI dues are preserved like billed interest dues (the restructure due-delete is component-agnostic). Accrued-unbilled DPI is capitalised onto the first new installment, mirroring how BPI lands on installment-1.

`CapitaliseAccruedDpiOnRestructureProcessor` (wired after `generateLoanAccountRestructuringRepaymentScheduleProcessor` in `loanAccountRestructuring`): `getUnbilledAccruedAmountTillDate(loanAccountId, effectiveDate)` → create `component_type=DPI` due on the first new installment (`getLatestLoanInstallmentDetailsEntity`, i.e. first installment ≥ effectiveDate) → `markBilledTillDate` to close the source accrual rows. No new GL leg (AIR clears on payment, same as interest BPI / foreclosure fold).

#### R5 — Death Foreclosure handler

**What:** Same as Foreclosure but for death-foreclosure flow (Excel rules 23-28). Write-off variants when insurance shortfall exists.

**Blocking:** Q4.

#### R6 — Loan Advance Payment handler

**What:** When a customer pays in advance of EMI date, ensure DPI is not erroneously billed for the cleared amount.

**What changes:**
- The advance-payment flow already doesn't generate DPI rows because `dpiAccrualCalculation` only runs on overdue loans. So this is mostly a "verify" item — confirm no DPI rows linger after an advance payment fully clears upcoming EMIs.

**Blocking:** None. Can do now.

#### R7 — Push-to-Collection backend — DONE (verified 2026-06-12)

Accounting-side push is already DPI-aware in `LoanRecurringPaymentBatchProcessor` (the recurring/bulk collection push to payments): payload carries `dpi_due` (:178) + `dpi_overdue` (:182); `setAmountMap` treats DPI as a first-class component (:279/:307/:320/:333); `getTotalOverDueAmount` (:423) and `getTotalDueAmount` (:444) both add DPI, so `total_overdue_amount`, `total_due_amount`/`emi_amount`, the component-agnostic `total_outstanding_amount` (:149) and the collection `amount` = overdue+due (:212) all include DPI. Only the Collections-app **UI** DPI column (webapp/collection app, other team) remains — not an accounting change.

Note: the closure-flow `PopulateLoanAccountCollectionRequestProcessor` builds only customer/employee/address (no amounts), so its lack of DPI is expected and irrelevant.

#### R8 — DPI write-off path

**What:** When DPI is waived / written off, post the write-off GL entry (Excel rules 29, 30) and update `loan_due_details.waivedAmount`.

**What changes:**
- New processor `WriteoffDpiProcessor` (or extend existing waiver flow).
- Flyway: nothing (uses existing `WAIVE_FEE_AND_CHARGE/LOAN_ACCOUNT` rule with new GL pair).
- Loan 360: `dpi_written_off` field surfaces the sum.

**Blocking:** Trigger flow design — does waiver come through approval workflow (existing waiver_details table) or auto from auto-closure only?

#### R9 — Cache eviction wiring

**What:** When Rohit's per-frequency product-scheme-update flow lands, it must evict `dpi_scheme_config` cache for the affected loans (or all loans of the affected scheme).

**What changes:**
- Add `@CacheEvict(value = "dpi_scheme_config", allEntries = true)` to whatever Rohit's update method is.
- Or add a targeted eviction by `productSchemeId` reverse-lookup.

**Blocking:** Q4 (need to know which method to annotate).

#### R10 — Per-frequency resolver impl

**What:** Replace v1 stub `DefaultDpiSchemeConfigResolver` with `PerFrequencyDpiSchemeConfigResolver` that reads from Rohit's new table.

**What changes:**
- New implementation class implementing `DpiSchemeConfigResolver`.
- Mark with `@Primary` to override the default.
- Read `(rate, grace, days_in_year)` from `product_scheme_repayment_frequency_details` (or whatever table name lands) for the loan's `repayment_frequency`.

**Blocking:** Q4 (table created, columns confirmed).

#### R11 — Transaction Reversal: NO CODE CHANGE

Verified: `reverseTransaction` engine routes by `(transaction_type, transaction_sub_type)`. Once Vasanthi seeds the rules, DPI accrual/billing reversals work via the same engine. No DPI-specific reversal code needed.

#### R12 — DPD job update: NO CODE CHANGE

Verified: `LoanAccountDpdCalcBatchProcessor` already sums all `loan_due_details` components. Once DPI rows exist, DPD picks them up.

#### R13 — EMI knock-off rule: NO CODE CHANGE

Verified: `UpdateLoanInstallmentDetailsProcessor:51-55` already filters to PRIN+INT only. DPI residuals don't block knock-off.

#### R14 — Day-Zero handling: PARKED

**What:** For loans already overdue when DPI feature goes live, retroactively compute and accrue DPI from the original due date (or some cut-off).

**Blocking:** Bank's policy on retroactivity.

**Likely shape:** One-shot Spring batch job that walks `loan_account` where `past_due_days > 0` AND `loan_status = 'ACTIVE'` AND scheme has DPI enabled, and runs `DPICalculationService.calculate()` for each with start_date = max(scheme.go_live_date, original_overdue_date). Posts accrual + billing in one go.

#### R15 — Weekly / Bi-Weekly / Daily frequencies: PARKED

**Why parked:** UD §5.4 sample-calc and image 3 show different rate/grace/days-in-year per frequency. v1 supports MONTHLY only.

**To unblock:** Drop `repayment_frequency = 'MONTHLY'` filter from `DpiAccrualCalculationItemReader`. Resolver returns config per-frequency (R10). Rates/graces seeded by Rohit per frequency (Q4).

#### R16-R17 — Tests

Unit + integration test coverage. Not blocking but should land before merge to integration branch.

#### R18 — Batch JDBC optimisation

**Opportunistic:** Currently `JpaItemWriter.merge()` per row. For >100k loans EOD this could be slow. Replace with `JdbcTemplate.batchUpdate("UPDATE dpi_accrual_details SET accrual_posting_date = ? WHERE id = ?", batchArgs)` — single statement per chunk.

**Blocking:** Perf-test signal. Don't pre-optimise.

#### R19-R24 — Out of scope

Other teams' tasks per task division (image attached in earlier conversation). Not in our scope.

### 17.3 Critical-path order to "feature complete"

1. **Q1 + Q2** confirmed → R10, R7, R6 unblock simultaneously
2. **Q3 lands** → no blocker but enables a small cleanup of `RepaymentApproppriationProcessor` to read 5 sequences
3. **Q4 lands (per-frequency table)** → R10 first, then R1-R5 in any order, then R8, then R15
4. **R16-R17 tests** parallel with above
5. **R14 day-zero** after main feature is live and stable
6. **R18 batch JDBC** if perf testing flags slowness

Estimated to "feature complete" at ~1000-1200 LOC of further code, mostly mechanical (lifecycle handlers all follow the same pattern of calling existing engines with `dpi_amount` carried through EC).

---

## 18. Glossary

| Term | Definition |
|---|---|
| **DPI** | Delayed Payment Interest — interest charged on the overdue principal+interest base of a missed EMI |
| **DPIC** | Same as DPI; UD title |
| **Grace period** | Days after due date during which DPI does NOT accrue |
| **Accrual** | Recognising DPI as it builds up day-by-day (Dr AIR / Cr Income) |
| **Booking** | Posting the accrued DPI to GL via postTransaction |
| **Billing** | Moving accrued DPI from "accrual receivable" to "billed receivable" on the next EMI date (Dr REC / Cr AIR) + creating loan_due_details row |
| **Knock-off** | Marking an EMI as settled. UD §5.5: requires P+I paid, DPI/PINT/FEE residuals do not block |
| **AIR** | Accrued Interest Receivable (GL category for not-yet-billed accrued amounts) |
| **NPA** | Non-Performing Asset — once a loan crosses NPA criteria, accruals go to suspense GLs instead of income |

---

## 19. References

- **UD:** `/home/darpan/darpan/UDs/UD_LMS_Delayed Payment Interest v1.3.docx`
- **Sample calc + accounting Excel:** `/home/darpan/darpan/UDs/Sample Calculation and Accounting Entries of DPI v 1.3 (1).xlsx`
- **Existing pattern reference:** `batchnew/penal/penalaccrualcalculation/`, `batchnew/penal/penalaccrualbooking/`, `batchnew/loanaccountbilling/`, `batchnew/interest/interestaccrualcalculation/`, `batchnew/interest/interestaccrualbooking/`
- **Live Q-list:** [`05-open-questions.md`](05-open-questions.md)
- **One-page overview:** [`00-overview.md`](00-overview.md)
- **Changelog:** 2026-05-06 DPIC v1 entries in [`../changelog/CHANGELOG.md`](../changelog/CHANGELOG.md) (commits `2f3c7e25a 456b4d34e 0d0376b85 1f71a8b9c` on `feature/dpic-v1`)
