# 134207 — missing `product_transaction_catalogue__placeholder__iad`

## Symptom

- **`postTransaction`** / **`disburseLoan`** fails with **134207** and notification text about product transaction catalogue / placeholder / internal account definition.
- Log: `ExecuteTransactionRulesProcessor` — cannot resolve placeholder (**often `PROC_FEE`**) for `product_id` + `transaction_catalogue_id`.

## Cause

For the row in **`product__transaction_catalogue`** linking the loan **product** to **LOAN_DISBURSEMENT** (`transaction_catalogue_id` commonly **1**), **`product_transaction_catalogue__placeholder__iad`** is missing one or more rows required by **`transaction_accounting_rule`** (PROC_FEE, GST placeholders, STAMP_DUTY_AMT, etc.).

## Fix

DB: insert missing `(product_transaction_catalogue_id, placeholder_code, internal_account_definition_id)` rows. Copy **`internal_account_definition_id`** from a **known-good product** in the **same DB** for the same catalogue (e.g. product **1**). Use the SQL patterns in this note below.

## Verified local example (sliProd)

- **product_id 2**, **transaction_catalogue_id 1** → **`product__transaction_catalogue.id` = 7**; added **PROC_FEE** + tax + **STAMP_DUTY_AMT** mappings aligned with product 1.
