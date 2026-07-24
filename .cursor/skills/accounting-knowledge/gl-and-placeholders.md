<!-- Relocated verbatim from .cursor/rules/accounting.mdc / accounting-module-knowledge.mdc. Edit these skill topic files; thin accounting.mdc only routes here. -->

## Child vs parent `gl_code` shape (postTransaction / force-bill)

| Account | Stored `transaction_partition_details.gl_code` | Notes |
|---------|-----------------------------------------------|-------|
| Child loan | `CG` + base code (e.g. `CG13336`) | `is_child_account` → `ChildGeneralLedgerEntity.CHILD_GL_CODE_PREFIX`; never display as parent GL name |
| Parent loan | base code only (e.g. `13336`) | May resolve `general_ledger.name` (e.g. REG EMI / AIR) |

SoT: `ExecuteTransactionRulesProcessor` + brain `08-gl-posting-engine.md` display rule. Memory: `feedback_child_cg_gl_vs_parent_named.md`.

## GL posting reference codes (additional_amount_details)

| Code | Context key source | Meaning |
|------|--------------------|---------|
| PRIN_AMT | prin_amt | Overdue/billed principal |
| INT_AMT | int_amt | Overdue/billed interest |
| POS | pos | Principal outstanding (future principal) |
| BPI_AMT | bpi_amount | Broken period interest |
| PENAL_AMT | penal_amount | Penal interest |
| FEE_AMT | fee_amount | Fees |
| LOSSES_INT_WAIVED | losses_int_waived | Interest waived (loss) |
| LOSSES_INT_WAIVED_AIR | losses_int_waived_air | Interest waived AIR (accrual reversal) |
| EXCESS_INCOME_INT | extra_int_paid | Extra interest paid (income) |
| EXCESS_ACCOUNT_INC | extra_int_paid | Extra interest to excess account |
| ADV_PRIN_AMT, ADV_INT_AMT, etc. | adv_prin_amt, adv_int_amt | Advance/excess-sourced portions |
| ROUND_UP_AMT / ROUND_DOWN_AMT | rounding factor | Rounding adjustment |

