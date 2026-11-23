# Phase 6 — Portfolio polish

**Goal:** a recruiter understands the project in 60 seconds; a developer can run it in 5 minutes.
**Done when:** public repo with README, screenshots/GIF from demo data, green CI badge, clean history.

## Tasks
- [x] 6.1 `manage.py make_demo_data`: 2 years of realistic synthetic transactions (salary, rent, groceries, subscriptions with a price increase, seasonal travel, a few anomalies). Seeded → reproducible.
- [x] 6.2 README: problem, screenshots, features, architecture diagram, "analysis methods" section, quick start.
- [x] 6.3 Screenshots + short GIF (Playwright script, demo data only).
- [x] 6.4 Test coverage report; aim high on `insights/`.
- [x] 6.5 Docs: `docs/decisions.md` (short list of key choices and why).
- [x] 6.6 Final privacy check: no real data in git history (`git log --all -- data/`), no keys.
- [x] 6.7 MIT license. Published 2026-11-23 as a fresh public repo with one squashed commit; the old history is archived in the private `aurora-finance-private`.

## Findings
- 6.6 (2026-11-23): two real names and one account number from the owner's bank text were in `ledger/categorize.py` and `test_categorize.py`. Replaced in the code; they are still in git history. Owner chose a fresh public repo with one squashed commit; the private repo keeps its history. Owner notes moved to `data/owner-notes.md`.
- 6.3: the app is dark-only, so there are no light screenshots. Light theme is a possible later task.
- Notebook 3.11 done: `notebooks/analysis.ipynb`, built and run by `scripts/build_notebook.py`.

## Note
Do 6.1 early (during phase 1–3) — demo data is needed for development, tests and screenshots anyway.
