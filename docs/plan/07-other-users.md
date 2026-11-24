# Phase 7 — For other users

**Goal:** someone who is not a developer can download Aurora, point it at their own bank files
and use it, with all data on their own machine.
**Done when:** a Mac or Windows user installs it with a double-click, imports files from at
least the four largest Norwegian banks, and can pick Claude, another AI, or no AI.

## Principles
- **Local only.** No server, no account, no telemetry. The database is one file in a folder
  the user picks (`DB_PATH`), and backing it up is the user's own responsibility. We never
  process anyone's data, so we are never their data processor.
- **AI is optional.** Every feature except the AI buttons works from CSV and Excel files
  alone. We recommend Claude, but the user can choose any provider or none.
- **Never guess a bank format silently.** An unknown file gets a mapping step, never a
  best-effort import.

## Tasks
- [x] 7.1 Other banks: today one generic importer finds columns by name and is tested on DNB
      only. Collect the real export layouts of Nordea, SpareBank 1, Handelsbanken and
      Storebrand, add synonyms or a bank-specific importer where needed, and add a test
      fixture of synthetic rows for each format.
- [x] 7.2 "Teach a new bank": when no importer matches, the user picks the date, amount and
      text columns once; the mapping is saved and reused.
- [x] 7.3 Any AI: an "OpenAI-compatible" provider (base URL + key + model) next to Claude
      and Ollama. That covers OpenAI, Gemini, Mistral, LM Studio and most others.
- [x] 7.4 Settings page: AI provider, model, language and data folder in the app instead of
      `.env`. Keys stay in a local file, never in the database export.
- [x] 7.5 Desktop package: one app for macOS and one for Windows that starts the server and
      opens the browser (evaluate Briefcase, PyInstaller or a small Tauri shell). Signing
      needs an Apple Developer account (99 USD/year); without it macOS warns on first start.
- [x] 7.6 First-run guide: pick a data folder, import a first file, choose AI or no AI.
- [ ] 7.7 Norwegian UI (Django i18n), with English kept. **Postponed (2026-11-24):** about
      500 strings in templates, views and chart labels, plus month names from `strftime`
      that must move to Django's date filters. A half-translated UI is worse than an English
      one, so it is a piece of its own. The AI already answers in Norwegian. Do it before
      the app is offered to Norwegian users who are not developers.
- [x] 7.8 Backup and move: export and import the whole database as one file.

## 7.1/7.2 as built (2026-11-24)
- The generic importer now also knows the column names of Nordea, SpareBank 1, Bank
  Norwegian and Revolut, dates with a time, and skips pending ("Reservert") rows. The test
  fixtures are synthetic rows in each layout as far as we know it: **check with a real
  export from each bank** before telling users it works.
- Unknown columns open a step where the user picks date, text and amount (or in/out); the
  choice is saved as a `BankFormat` for that header and used automatically next time. Saved
  layouts are listed on the Import page and can be forgotten.

## 7.5 as built (2026-11-24)
- `desktop/launcher.py`: picks the user's data folder, runs migrate and the built-in
  categories, starts waitress on 127.0.0.1 (DEBUG off, a per-install secret key, static files
  through whitenoise), warms up the first page and then opens the browser. A second start
  opens the running app instead of starting another. "Quit Aurora" in the menu stops it.
- `desktop/aurora.spec` (PyInstaller, one folder, about 135 MB): built and tested on macOS
  (arm64). `.github/workflows/desktop.yml` builds macOS and Windows, starts each once as a
  smoke test, and attaches zips to a release for a `v*` tag.
- Not signed: macOS needs right-click → Open the first time, Windows SmartScreen may warn.

## Not planned
- Mobile app. The web UI already works in a phone browser against your own machine; a
  separate app would mean a second codebase.
- Live bank connections (PSD2 aggregators). They need a company, an agreement and a server,
  which is the opposite of local only.

## Landscape (research 2026-11-24)
- **Self-hosted classics** (Firefly III, Actual Budget, GnuCash) import CSV/OFX and can sync
  through aggregators, but need a server or Docker and have no built-in analysis or AI.
- **App Store budget apps** (MoneyWiz, My Budget Book, BalanceTrackr and many more) import
  CSV, but are closed source, often subscriptions, and not built around Norwegian bank
  formats or merchants.
- **Local AI finance projects** (FinSight, Kist Finance, Vaulted Money, several tutorials)
  are mostly young GitHub projects or blog demos.
- **Gap Aurora fills:** local, open source, Norwegian banks and merchants out of the box,
  real analysis (recurring payments, robust anomalies, debt payoff) and optional AI with a
  choice of provider.
