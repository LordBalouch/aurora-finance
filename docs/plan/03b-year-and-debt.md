# Phase 3b — Year & debt (added 2026-11-23, owner's wish)

**Goal:** the yearly picture the bank cannot show — gross income, tax, interest, wealth and debt
at 31 December — and a payoff plan built from it plus the loan payments in the bank data.
**Done when:** tax years can be entered and compared, the debt page shows a payoff plan with an
"extra per month" what-if, and the maths has unit tests.

## Tasks
- [x] B.1 `TaxYear` (key lines of the Skatteoppgjør, `help_text` names the Norwegian line) and
  `DebtBalance` (lender, date, balance, rate, payment, merchant key, source).
- [x] B.2 `insights/debt.py`: `years_table` (effective rate = interest / average debt, interest
  and tax as % of income, changes), `payoff` (checked against the annuity formula), `plan`
  (several loans, extra to the highest rate first, freed payments roll over), `loan_payments`.
- [x] B.3 `/years/`: comparison table + charts; form to add/edit a year.
- [x] B.4 `/debt/`: key figures, payoff plan with HTMX "extra per month", bank loan payments,
  balances per lender (form + remove).

## As built
- Without balances per lender the plan treats all debt as one loan at the effective rate from
  the latest tax year and the total loan payments in the bank. Balances per lender (e.g. from
  gjeldsregisteret.no) switch it to a plan per loan.
- Real tax figures live only in the local database (entered via shell/form), never in git.

## Later
- Import from gjeldsregisteret.no (export) instead of typing balances.
- Match each `DebtBalance.merchant` automatically to the bank payments.
