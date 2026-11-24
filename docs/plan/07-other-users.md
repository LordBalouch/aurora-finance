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
- [ ] 7.1 Other banks: today one generic importer finds columns by name and is tested on DNB
      only. Collect the real export layouts of Nordea, SpareBank 1, Handelsbanken and
      Storebrand, add synonyms or a bank-specific importer where needed, and add a test
      fixture of synthetic rows for each format.
- [ ] 7.2 "Teach a new bank": when no importer matches, the user picks the date, amount and
      text columns once; the mapping is saved and reused.
- [ ] 7.3 Any AI: an "OpenAI-compatible" provider (base URL + key + model) next to Claude
      and Ollama. That covers OpenAI, Gemini, Mistral, LM Studio and most others.
- [ ] 7.4 Settings page: AI provider, model, language and data folder in the app instead of
      `.env`. Keys stay in a local file, never in the database export.
- [ ] 7.5 Desktop package: one app for macOS and one for Windows that starts the server and
      opens the browser (evaluate Briefcase, PyInstaller or a small Tauri shell). Signing
      needs an Apple Developer account (99 USD/year); without it macOS warns on first start.
- [ ] 7.6 First-run guide: pick a data folder, import a first file, choose AI or no AI.
- [ ] 7.7 Norwegian UI (Django i18n), with English kept.
- [ ] 7.8 Backup and move: export and import the whole database as one file.

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
