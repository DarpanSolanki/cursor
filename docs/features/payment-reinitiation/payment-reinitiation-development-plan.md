# Payment reinitiation — database (CRR only)

This file documents **only** what changes in **`mfi_accounting.client_request_response_log`** (CRR) for **payment reinitiation**.

**Product scope (important):** **NEFT disburse only** (other-bank-account / NEFT v2 path). **MFT is not in scope:** CASA / ACCTWB MFT is **synchronous**; there is **no** payment-reinitiation CRR lane, `transaction_type` split, or reference-series change for **`DISBURSEMENT_MFT`**.

Stakeholder email: `email-stakeholder-short.md`.

---

## Local database (used for this note)

- **Host:** `127.0.0.1` **Port:** `5433` **User:** `yugabyte` **Database:** `yugabyte` (schemas under `mfi_accounting`, etc.)
- **Table:** `mfi_accounting.client_request_response_log`
- **Live sample rows:** query for recent disburse-related `transaction_type` values returned **0 rows** on this machine (empty or no matching data). Column definitions below come from `psql \d mfi_accounting.client_request_response_log` on that database (2026-04-13).

### Table definition (local psql describe)

```text
Table "mfi_accounting.client_request_response_log"
         Column          |            Type             | Nullable | Default
-------------------------+-----------------------------+----------+--------
 id                      | bigint                      | not null | nextval('mfi_accounting.client_request_response_log_id_seq')
 partner                 | character varying(64)       | not null |
 client_reference_number | character varying(128)      | not null |
 request                 | text                        | not null |
 response                | text                        | not null |
 status                  | character varying(32)       | not null |
 uri                     | character varying(512)    |          | NULL
 http_header             | character varying(512)    |          | NULL
 eligible_for_retry      | boolean                     |          | false
 retry_count             | bigint                      |          |
 system_date             | timestamp without time zone |          |
 updated_on              | timestamp without time zone |          |
 loan_account_number     | character varying(24)     |          | NULL
 transaction_type        | character varying(64)     |          | NULL
 business_date           | timestamp without time zone |          |

Indexes: PRIMARY KEY (id HASH); index on client_reference_number
```

---

## What changes in the database (behaviour)

### Source of truth for CRR `transaction_type` (MFI `disburseLoan` bank leg)

The same orchestration file sets **`transaction_type` more than once** for different purposes. That is why **`LOAN_DISBURSEMENT`** is easy to confuse with what lands in CRR:

- **`LOAN_DISBURSEMENT`** is set on a `dummyProcessor` inside **populate_data_for_post_transaction** (e.g. CASA / OTHBACCT branches) for **posting / GL / narrative** context. It is **not** the value passed into **`callBankAPIForDisbursementProcessor`** for the bank call.
- The **bank** step passes **`DISBURSEMENT`** into `callBankAPIForDisbursementProcessor` (see `mfi_orc.xml`: `callBankAPIForDisbursementProcessor` with `transaction_type` = **`DISBURSEMENT`**, scope `local`).

`CallBankAPIForDisbursementProcessor` reads that context base and appends leg suffixes (`_MFT`, `_NEFT_NEF`, then `_NEFT_NEI` for stage 2). So **persisted CRR** `transaction_type` values for this path are built from **`DISBURSEMENT`**, not `LOAN_DISBURSEMENT`.

**Today (NEFT, no reinit lane) — persisted `transaction_type`:**

| Stage | Persisted `transaction_type` |
|-------|------------------------------|
| NEFT v2 stage 1 (ST_NEF) | `DISBURSEMENT_NEFT_NEF` |
| NEFT v2 stage 2 (ST_NEI) | `DISBURSEMENT_NEFT_NEI` |

(MFT rows `DISBURSEMENT_MFT` still exist for CASA flows; **they are unchanged** and **outside** payment reinitiation work.)

Reinit that **reuses** the same `DISBURSEMENT_NEFT_*` strings as the first attempt **collides** in CRR (callback / inquiry attaches to the wrong row).

**After the reinit change (NEFT only):**  
Reinit gets a **separate** `transaction_type` discriminator for NEF/NEI legs (exact suffix in code after merge). **Original** `DISBURSEMENT_NEFT_NEF` / `DISBURSEMENT_NEFT_NEI` rows stay historical; **new** rows carry the reinit-specific types for the same parent `loan_account_number`.

**Net effect on rows:**

- **Original** NEFT CRR: unchanged types.
- **Reinit** NEFT CRR: **additional** rows with reinit-discriminated `transaction_type`.
- **SHG parent reinit** with child bank off: **no new** child-LAN CRR rows from that path.

---

## `client_reference_number` — same **03** NEFT series

Leg prefixes are centralized in **`BankExternalRefPrefixes`** (`novopay-platform-accounting-v2/.../BankExternalRefPrefixes.java`):

| Constant | Digit | Use (disburse context) |
|----------|-------|-------------------------|
| `MFT_PAYMENT` | **02** | MFT payment / counter line for CASA (synchronous; **not** part of payment reinitiation). |
| `NEFT_PAYMENT` | **03** | **NEFT** payment / counter line — used for both NEF and NEI when building refs in **`CallBankAPIForDisbursementProcessor`** via **`ExternalReferenceNoUtil.computeDeterministicExternalReferenceNo`** with leg prefix **`BankExternalRefPrefixes.NEFT_PAYMENT`**. |
| `MFT_STATUS_INQUIRY_SESSION` | **06** | MFT status inquiry session ref (not NEFT). |

**Shape (today):** `referenceBase` + **leg prefix** + **zero-padded counter** (counter format **`%02d`** in `CallBankAPIForDisbursementProcessor`). Normally `referenceBase` is the **loan account number** unless overridden.

**Example (illustrative):** loan `LAN123456`, first NEFT payment attempt, counter `1` → `LAN123456` + `03` + `01` → **`LAN1234560301`** (same **03** series for NEFT payment attempts).

**Requirement for payment reinitiation:** Reinit must **stay on the NEFT payment series `03`**, i.e. **do not** switch reinit refs to another leg digit (e.g. not `02` MFT). The **numeric counter** must still follow **`ExternalReferenceNoUtil`** rules (last CRR for the **lookup `transaction_type`**, bump only on definitive **FAIL**, etc.). When reintroducing a **new** `transaction_type` for reinit, implementation must ensure the util / lookup still **continues the same `03` counter progression** the bank and STP already expect for that loan’s NEFT payment line (not reset to `…0301` as if history disappeared). Exact merge behaviour: **verify in code** that reinit types participate in the same deterministic line the product wants.

---

## Sample rows — **NEFT only** (illustrative)

**Parent loan account:** `LAN123456`. **Partner:** `Hdfc` (confirm per environment).

### Row A / B — first NEFT attempt (unchanged today)

| Column | Row A (NEF) | Row B (NEI) |
|--------|-------------|-------------|
| loan_account_number | `LAN123456` | `LAN123456` |
| transaction_type | `DISBURSEMENT_NEFT_NEF` | `DISBURSEMENT_NEFT_NEI` |
| client_reference_number | e.g. `LAN1234560301` | e.g. `LAN1234560302` (illustrative; actual counters from util) |
| partner | `Hdfc` | `Hdfc` |

### Row C / D — **reinit** NEFT (new after change; type suffix illustrative)

| Column | Row C (reinit NEF) | Row D (reinit NEI) |
|--------|--------------------|--------------------|
| loan_account_number | `LAN123456` | `LAN123456` |
| transaction_type | `DISBURSEMENT_NEFT_NEF_REINIT` | `DISBURSEMENT_NEFT_NEI_REINIT` |
| client_reference_number | **Still `03` series** — e.g. `LAN1234560303` (must follow merged counter rules; **not** a new non-03 prefix) | Next in same series per util + bank |

**QA check:** Reinit adds **new** CRR rows with reinit **`transaction_type`**, while **`client_reference_number`** values remain in the **`03`** NEFT payment family for that `referenceBase`. Callbacks update the row whose **`transaction_type`** matches the **reinit** leg.

---

## SQL — run on local DB (`yugabyte` database)

```sql
-- Inspect table (parent LAN)
SELECT id, loan_account_number, transaction_type, client_reference_number, status, partner, business_date, updated_on
FROM mfi_accounting.client_request_response_log
WHERE loan_account_number = 'LAN123456'
ORDER BY id DESC;

-- NEFT disburse CRR types for a LAN (payment reinitiation scope)
SELECT transaction_type, client_reference_number, status, updated_on
FROM mfi_accounting.client_request_response_log
WHERE loan_account_number = 'LAN123456'
  AND transaction_type LIKE 'DISBURSEMENT_NEFT%'
ORDER BY id DESC;
```

---

## Important columns for this feature

| Column | Why it matters for reinit |
|--------|---------------------------|
| **transaction_type** | **Only** place that separates original disburse leg vs reinit leg for bank + callbacks. |
| **loan_account_number** | Parent vs child; parent reinit must not create **child** LAN rows when child bank is off. |
| **client_reference_number** | **NEFT:** must stay in **`03`** payment series (`referenceBase` + `03` + counter). Must align with bank/callback. |
| **status** | Success/failure per row; duplicate Kafka should not leave two **successful** debits for same intent (rule per product). |
| **partner** | Bank routing; unchanged conceptually. |
| **request** / **response** | Audit of payloads; debugging only for most QA. |
| **business_date** / **updated_on** | Ordering and “latest row” for a given type. |

---

*End of document.*
