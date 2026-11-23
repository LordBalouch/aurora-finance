# Phase 4 — Budget

**Goal:** a realistic budget built from history, with live progress through the month.
**Done when:** budget can be generated, edited and tracked; forecast shown; tests for pacing math.

## Model
- `Budget` (month, category, amount) — month-specific, with "copy from last month".
- Optional `Goal` (name, target amount, target date, linked saving category).

## Tasks
- [x] 4.1 Suggest budget from history (median of last 6 months per category), user adjusts.
- [x] 4.2 Progress per category: spent vs. budget vs. expected-by-today (pacing line), color states.
- [x] 4.3 Month-end forecast per category (from phase 3.6) → "on track / at risk / over".
- [x] 4.4 Budget page visuals: progress rings/bars, burndown chart for the month.
- [x] 4.5 Savings goals with projected completion date.
- [x] 4.6 Year view: budget vs. actual per month (heatmap).

## As built
- Budgets are per category group (13 groups, not 41 categories): easier to keep and to read.
- `insights/budget.py`: `suggest` (median of the 6 months before, months without spending count
  as 0, rounded up to 100 kr), `progress` (expected = budget × share of the month gone;
  forecast = spent + recurring still due in the group + typical other spending for the rest),
  `burndown`, `actual_vs_budget`, `goal_projection`.
- `/budget/`: month switcher (defaults to the latest month with data), create from history or
  copy last month, editable amounts, bars with an even-pace marker, status with icon + label,
  burndown, budget vs. actual heatmap (diverging, 100 % = neutral), savings goals.
- Goals are entered by hand: savings sit in the savings account, which is not imported.
