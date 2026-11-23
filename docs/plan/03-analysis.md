# Phase 3 — Analysis + dashboard (portfolio core)

**Goal:** the analysis a data analyst would be proud to show; every number is explainable.
**Done when:** dashboard + 3 deep-dive pages work on demo data, each `insights` function has unit tests,
and `notebooks/analysis_walkthrough.ipynb` shows the methods on demo data.

## Rule
All calculations are pure functions in `insights/` taking a pandas DataFrame and returning
DataFrames/values. Views only load data → call function → build chart. No math in templates.

Netted categories: "Friends & family" holds money both ways (gifts, shared bills, paying
back) and is never income. Report it as its own net line, not inside income or spending.
Same for "Transfers" (kind transfer): excluded from income/spending.

## Tasks
- [x] 3.1 Data access: one function `transactions_df(filters)` (ORM → DataFrame, typed columns).
- [x] 3.2 KPIs: income, spending, net, savings rate — month vs. previous month and vs. 12-month average.
- [x] 3.3 Category trends: monthly per category, stacked + small multiples; fixed vs. variable split.
- [x] 3.4 Recurring payments / subscriptions detection (same counterparty, similar amount, regular interval) + price-increase flag.
- [x] 3.5 Anomalies: category month vs. its own rolling median (robust z-score / MAD), list with explanation.
- [x] 3.6 Cash-flow: running balance per account; month-end forecast from recurring + average variable spend.
- [x] 3.7 Seasonality: spend by weekday, day of month, month of year (heatmap).
- [x] 3.8 Counterparty ranking + "where did the money go" Sankey (income → categories).
- [x] 3.9 Dashboard page: KPI row, trend chart, top changes, anomalies, subscriptions; global date-range picker (HTMX).
- [x] 3.10 Drill-down: click any chart element → filtered transaction list.
- [ ] 3.11 Notebook walkthrough (portfolio).

## As built
- 3.1 `ledger/frames.py::transactions_df` (only DB touchpoint); amounts float in analysis, Decimal in storage.
- 3.2 `insights/monthly.py`: `flow` (refunds stay spending; transfers and Friends & family apart),
  `monthly_summary`, `complete_months` (drops current month and sparse leading months: late refunds
  keep their purchase date), `compare`, `spending_by_group`, `netted_totals`.
- KPI deltas: income/spending in %, net in kr (relative change of a value that can be negative
  misleads), savings rate in pp; savings-rate average = average net / average income.
- Period links (3M/6M/12M/All) set the chart window; KPIs always show the last complete month.
- 3.3 `insights/trends.py` (`monthly_by_group`, `fixed_and_variable`, `group_overview`) and
  `/trends/`. Small multiples share one y-scale from zero (`y_max` in the chart spec). Change =
  last 3 months vs. the 3 before. Stacked bars: 2px surface gap, only the top segment rounded.
- 3.4 `insights/recurring.py`: regular gaps (±35 % of median, ≥70 %) matching a cadence; one
  merchant with several amount levels (two loans) is split by amount.
- 3.5 `insights/anomalies.py`: robust z (MAD) per group vs. its own last 12 months, ≥3 and ≥500 kr.
- 3.6 `insights/forecast.py`: spent so far + recurring still due + typical other spending for the
  days left. Running balance per account is NOT possible: DNB exports have no balance column.
- 3.7 `insights/patterns.py`: weekday × month heatmap (per calendar day) and day of month,
  variable spending only.
- 3.8 `insights/counterparties.py`: top merchants and a Sankey (income → spending groups, with
  friends & family / own accounts / shortfall as funding when spending is larger).
- 3.9–3.10 `/insights/` page, dashboard cards (forecast, recurring, unusual months); bars, rows and
  anomalies link to the filtered transactions (`?merchant=`, `?category=<group>&from&to`).
- 3.11 moved to phase 6: the notebook needs the synthetic demo data from 6.1.
