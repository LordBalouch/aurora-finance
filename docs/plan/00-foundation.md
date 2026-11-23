# Phase 0 — Foundation + design system

**Goal:** an empty app that already looks finished: dark, futuristic shell with navigation,
a working chart, tests and CI.
**Done when:** `runserver` shows the shell with a demo ECharts chart, `pytest` and `ruff` are green, CI green.

## Tasks
- [x] 0.1 Skeleton: venv, Django project `config`, apps `ledger`, `insights`, `web`; `.gitignore` (incl. `data/`, `.env`, `*.sqlite3`); `requirements.txt`.
- [x] 0.2 Settings: SQLite at `data/aurora.sqlite3`, `TIME_ZONE=Europe/Oslo`, env via `.env`.
- [x] 0.3 Hand-written CSS on design tokens (`static/css/app.css`, no build step), HTMX + ECharts + fonts vendored in `static/` (no CDN).
- [x] 0.4 Design tokens + base layout per `docs/design.md`: sidebar, top bar, glass cards, KPI tile, empty state.
- [x] 0.5 Chart helper: one Python function builds an ECharts option dict → `json_script` → one small JS file renders all charts with the shared theme.
- [x] 0.6 Tooling: pytest-django, ruff, `Makefile` (`dev`, `test`, `lint`, `fmt`, `migrate`).
- [x] 0.7 GitHub Actions CI: ruff + Django checks + pytest.

## Notes
- Keep `insights/` free of Django imports from day one; it is the portfolio showpiece.
