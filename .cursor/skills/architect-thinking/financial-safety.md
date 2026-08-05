<!-- Relocated verbatim from .cursor/rules/architect-thinking.mdc. Edit skill topics; thin architect-thinking.md only routes here. -->

# Financial safety

## Amount validation

Every financial calculation must be validated before persistence or bank call:

```java
// Validate net disbursement amount
BigDecimal netDisbursedAmount = approvedAmount
    .subtract(crossSellAmount)
    .subtract(taxAmount)
    .subtract(netOffAmount)
    .subtract(chargesAmount);

if (netDisbursedAmount.compareTo(BigDecimal.ZERO) < 0) {
    throw new NovopayFatalException("ACCT-XXXX", "Net disbursed amount cannot be negative: " + netDisbursedAmount);
}
```

### Base amount rules
- **approved_amount**: Use for net disbursement calculations. This is the amount sanctioned to the borrower.
- **loan_amount**: Includes insurance and add-ons. Do NOT use as base for net disbursement.
- **Always clarify which amount** is the base in any formula.

## Precision

- Use `BigDecimal` for all monetary amounts. Never `double` or `float`.
- Set scale explicitly: `amount.setScale(2, RoundingMode.HALF_UP)` for INR.
- Compare with `compareTo()`, never `equals()` (scale-sensitive).

## Charge and fee calculations

- Charges can be fixed or percentage-based. Percentage charges use the correct base amount.
- Tax on charges: calculate tax after charge amount, not on the base loan amount.
- `charge_inclusive_of_tax`: Never return null. Return `false` as default.
- When no charges are configured, still return a placeholder entry (backward compat) and set `charges_configured = false`.

## Audit trail for money movement

Every money movement must be traceable:
- Who initiated it (`performed_by`)
- When (`performed_on`)
- What amount and from/to accounts
- GL entries (debit/credit)
- Status transitions with timestamps

## Idempotency for financial operations

- Disbursement: Check if already disbursed before calling bank API.
- Repayment: Check if receipt already processed before applying.
- Charges: Check if already levied before creating.

## Formula documentation

When implementing a financial formula, state it explicitly:

```java
// Net disbursement = approved_amount - cross_sell - tax - net_off - charges
// All amounts are in INR, 2 decimal places
```

This is one of the few places where a comment adds real value — financial formulas must be unambiguous.

---

