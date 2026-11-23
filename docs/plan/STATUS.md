# Status

**Current phase:** 6 done, repo public → 5.5 next (`05-ai.md`)
**Next task:** owner tries the AI buttons with an API key; then 5.5 (ask-your-data) or 5.2

| Phase | File | State |
|---|---|---|
| 0 Foundation + design system | 00-foundation.md | done |
| 1 Import | 01-import.md | done |
| 2 Categorize | 02-categorize.md | done |
| 3 Analysis + dashboard | 03-analysis.md | done (3.11 → phase 6) |
| 3b Year & debt | 03b-year-and-debt.md | done |
| 4 Budget | 04-budget.md | done |
| 5 AI tips | 05-ai.md | core done (5.2, 5.5 open) |
| 6 Portfolio polish | 06-portfolio.md | done, public |

## Open questions for the owner
Private notes about the owner's own finances live in `data/owner-notes.md` (gitignored), never in git.

## Log (newest first, one line each)
- 2026-11-23 Published: fresh public repo (one commit); old history archived privately as aurora-finance-private.
- 2026-11-23 Notebook 3.11: analysis walkthrough on demo data (robust vs. naive z, median budget, payoff).
- 2026-11-23 Phase 6.1–6.5: demo data (`make demo`), screenshots, README, coverage 97 % in CI, decisions.md; real names removed from tests.
- 2026-11-23 Phase 5 core: 'Ask AI' on every analysis card + story of the month, cached, fake-client tests.
- 2026-11-23 Phase 4: budget per group (from history / copy), pacing, forecast, burndown, year heatmap, goals.
- 2026-11-23 Phase 3b: tax years 2024–2025 entered locally, Years and Debt pages, payoff plan with extra-payment what-if.
- 2026-11-23 Phase 3.4–3.10: recurring payments, anomalies, forecast, patterns, Sankey, Insights page, drill-down.
- 2026-11-23 Phase 3.3: Trends page (stacked groups per month, fixed vs. variable, small multiples on one scale).
- 2026-11-23 Phase 3.1–3.2: `transactions_df`, monthly summary, KPIs vs. previous month and 12-mo average; dashboard on real data.
- 2026-11-23 Inbox done (all rows categorized); 'Friends & family' one netted category; 'Other › Miscellaneous'.
- 2026-11-23 Phase 2 core: categories, rules, inbox; 69 % of rows / 85 % of money out auto-categorized.
- 2026-11-23 Real data imported (1 637 rows, DNB CSV+XLSX); `make import`, xlsx support.
- 2026-11-23 Phase 1 built: models, generic importer, dedup, import/preview/undo, transactions page (58 tests).
- 2026-11-23 Phase 0 done: shell, design tokens, chart helper, sample dashboard, CI.
- 2026-11-23 Plan written.
