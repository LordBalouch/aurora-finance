# CLAUDE.md — Aurora Finance

Personal finance analysis app. Two goals, equal weight:
1. **Portfolio** on GitHub that shows data-analysis skill (Python, SQL, pandas, tests).
2. **A tool the owner actually uses** for overview, categories, budget and AI tips.

## How to work (token budget matters)
- Read `docs/plan/STATUS.md` first. Then read ONLY the phase file it points to.
- Do not read other phase files or `docs/design.md` unless the task needs them.
- Update `STATUS.md` (one line) and the phase checkboxes when a task is done.
- The owner is a data analyst, not a programmer: give copy-paste commands and expected output.
- One finished, tested unit = one commit. Never push unless asked.

## Locked decisions
- Runs **locally only** (one user, no login, no server). Can move online later; not planned.
- Django 5.2 + HTMX + hand-written CSS on design tokens (no build step) + Apache ECharts. SQLite. pandas for analysis.
- Python venv in `.venv`; pytest + pytest-django; ruff.
- Code, comments and docs in English. UI text in English.
- Money is `Decimal` (never float). Dates are local dates (Europe/Oslo).

## Privacy rules (never break)
- Real bank files and the real database live in `data/` and are **gitignored**. Check before every commit.
- Screenshots, README and tests use **synthetic data only** (`manage.py make_demo_data`).
- Real data may be used freely for analysis, by the app's AI and by Claude Code in sessions
  (owner's decision 2026-11-23). It must never end up online: not in git, GitHub, README,
  screenshots, issues or CI logs.
- No secrets in git; API key in `.env` (gitignored).

## Layout (target)
- `config/` settings · `ledger/` models, importers, categorizer · `insights/` pure analysis
  functions (pandas, no Django imports, unit tested) · `web/` views, templates, charts
- `docs/plan/` phases · `docs/design.md` visual design system
