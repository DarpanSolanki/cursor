# Callback / new CRR rows — full column + lookup impact (2026-07-19)

**Miss:** NEFT inbound callback CRR ship passed `PROCESSOR_MIRROR_SIM` checking txn_type/request shape only — never asserted `client_reference_number=paymentref` (`persistInboundCallbackCrr` L663). Disbursement was `backlog_domains` so `acceptance_coverage.check_from_pending` skipped all db_asserts.

**Contract (proven):** callback CRR `client_reference_number` = bank `paymentrefno` (same key used to resolve outbound via typed NEF finder). Typed `findOneByClientReferenceNumberAndTransactionType(…, DISBURSEMENT_NEFT_NEF)` is safe; untyped `findOneByClientReferenceNumber` (ORDER BY system_date DESC) can return the newer `*_CALLBACK` row after persist — impact before ship.

**Gate:** `acceptance_coverage_manifest.json` → `db_assert_enforced_on_money_tier: [disbursement]` + `domain_money_table_required_columns.client_request_response_log` including `client_reference_number`. Weak sims without that column FAIL self-test 3c.

**Sim:** `disbursement.neft_crr_exact_audit_callback_sim` must assert client_ref + partner/LAN/txn_type/status/request/response.
