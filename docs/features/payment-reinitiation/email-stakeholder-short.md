# Email draft — Payment reinitiation

**Subject:** Payment reinitiation — LMS + Accounting alignment (this release + follow-ups)

**Body:**

Hi all,

We are implementing **payment reinitiation** fixes in **Accounting (LMS)** in three clear slices: **orchestration** (parent-only bank on reinit), **async consumer** (stop treating reinit as a no-op), and **bank / CRR / callbacks** (separate audit trail per reinit so inquiries and callbacks land on the right row). **Structural follow-ups** (for example Redis TTL on in-flight keys, broader automated tests) are **planned for a later release**, not bundled here.

**What you should see in production**

- When LOS asks for a **bank-only reinit** after a loan is already in a late disburse stage, Accounting will **actually run** the flow instead of skipping and pretending success.
- **SHG / parent–child:** reinit will **not** fire **child** bank legs again by default, so we avoid duplicate child NEFT and callback clashes.
- **NEFT disburse only (async bank leg):** each reinit attempt gets its own **CRR lane** in **mfi_accounting.client_request_response_log** (new **transaction_type** values for the reinit trail; exact suffix in code after merge). **Client refs stay in the same NEFT payment series (`03` prefix per `BankExternalRefPrefixes.NEFT_PAYMENT`)** with deterministic counter rules — see detailed doc. **MFT (CASA) is synchronous** and is **not** part of this payment-reinitiation CRR/ref change. Duplicate Kafka should still yield **at most one** payment outcome.

**Accounting (`novopay-platform-accounting-v2`) — main work**

- Orchestration (`mfi_orc.xml`): for **REINITIATE_BANK**, parent bank on, **child bank off**.
- `LmsMessageBrokerConsumer`: the "already disbursed" skip rule must **not** block **REINITIATE_BANK**.
- `CallBankAPIForDisbursementProcessor` plus **NEFT** callback/inquiry paths: **reinit-specific** `transaction_type` on CRR rows and routing; **`03`** ref series continuity; idempotent duplicate messages. (MFT callback path unchanged for reinit scope.)

**LOS (`novopay-mfi-los`) — please coordinate**

- **Verify** every async **disburseLoan** used for payment reinitiation sends **function_sub_code = REINITIATE_BANK** (and existing flags such as payment reinitiation update) on the path that reaches the LMS Kafka consumer. Check **individual and group disburse processors**, **account details → accounting context**, **disbursement callback** services that set **REINITIATE**, and **bulk payment reinitiation** batch if it uses the same API.
- If Accounting changes the **sync payload** to LOS, confirm the **consumer contract** (no breaking removals; add **entity_type** where the LOS sync consumer expects it — known cross-team gap).

**Gaps: this release vs later**

| Topic | This release | Later |
|-------|--------------|--------|
| Reinit skipped as already done | **Fixed** (consumer) | — |
| Child bank on parent reinit | **Fixed** (orchestration) | — |
| Wrong CRR / callback mix-up | **Fixed** (processor + callbacks) | — |
| Redis in-flight **no TTL** (Accounting + LOS) | **Not this release** | Dedicated change; support may clear stuck keys per agreed steps |
| **entity_type** on Accounting → LOS sync | Fix if we touch JSON; else ticket | Contract alignment |
| No automated tests on async consumer | **Manual QA** | Add when approved |

**Regression**

- Disbursement surface is **large** (MFT / NEFT v1 / v2, SHG vs non-SHG, callbacks, duplicates, LOS sync). Full sign-off is **multi-day QA**; narrow smoke is smaller.

**Detailed plan** (NEFT-only CRR, **`03`** ref series, sample rows + SQL):  
`docs/features/payment-reinitiation/payment-reinitiation-development-plan.md` (workspace `sliProd`).

Thanks,  
[Name]
